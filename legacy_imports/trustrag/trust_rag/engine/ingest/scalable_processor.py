"""
Scalable Document Processing System for TrustRAG.
Handles large files and parallel processing with fault tolerance.
"""
import os
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import tempfile
import shutil

from trust_rag.config import get_config
from trust_rag.engine.ingest.models import Chunk, IngestResult
from trust_rag.engine.ingest.processor import DocumentProcessor

logger = logging.getLogger(__name__)


@dataclass
class ProcessingTask:
    """Individual file processing task."""
    file_path: str
    doc_id: Optional[str] = None
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class ProcessingResult:
    """Result of processing a single file."""
    task: ProcessingTask
    success: bool
    chunks: List[Chunk] = None
    metadata: Dict[str, Any] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    file_size: int = 0


class LargeFileSplitter:
    """
    Split large files into manageable chunks for processing.
    """

    def __init__(self):
        self.config = get_config().document_processing
        self.max_file_size = self.config.max_file_size_mb * 1024 * 1024

    def should_split(self, file_path: str) -> bool:
        """Determine if file should be split."""
        file_size = os.path.getsize(file_path)

        # Check size threshold
        if file_size > self.max_file_size:
            return True

        # Check file type specific thresholds
        file_ext = Path(file_path).suffix.lower()

        # PDFs over 100MB should be split
        if file_ext == '.pdf' and file_size > 100 * 1024 * 1024:
            return True

        # Videos over 500MB should be split
        if file_ext in ['.mp4', '.avi', '.mov'] and file_size > 500 * 1024 * 1024:
            return True

        return False

    def split_file(self, file_path: str) -> List[str]:
        """Split large file into smaller parts."""
        file_ext = Path(file_path).suffix.lower()

        if file_ext == '.pdf':
            return self._split_pdf(file_path)
        elif file_ext in ['.mp3', '.wav', '.mp4', '.avi']:
            return self._split_audio_video(file_path)
        else:
            # For other files, don't split but log warning
            logger.warning(f"Large file {file_path} cannot be split, processing as-is")
            return [file_path]

    def _split_pdf(self, file_path: str) -> List[str]:
        """Split PDF into smaller PDFs."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            total_pages = len(doc)

            # Aim for chunks of ~50 pages each
            chunk_size = min(50, max(10, total_pages // 4))

            split_files = []
            temp_dir = tempfile.mkdtemp()

            for start_page in range(0, total_pages, chunk_size):
                end_page = min(start_page + chunk_size, total_pages)

                # Create new PDF with page range
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page-1)

                chunk_filename = f"{Path(file_path).stem}_part_{start_page+1}-{end_page}.pdf"
                chunk_path = os.path.join(temp_dir, chunk_filename)
                new_doc.save(chunk_path)
                new_doc.close()

                split_files.append(chunk_path)

            doc.close()

            logger.info(f"Split PDF {file_path} into {len(split_files)} parts")
            return split_files

        except ImportError:
            logger.warning("PyMuPDF not available for PDF splitting")
            return [file_path]
        except Exception as e:
            logger.error(f"PDF splitting failed: {e}")
            return [file_path]

    def _split_audio_video(self, file_path: str) -> List[str]:
        """Split audio/video files into segments."""
        try:
            from pydub import AudioSegment

            # Load audio/video
            if file_path.lower().endswith(('.mp3', '.wav')):
                audio = AudioSegment.from_file(file_path)
            else:
                # For video, we'd need additional processing
                logger.warning(f"Video splitting not fully implemented for {file_path}")
                return [file_path]

            # Split into 10-minute segments
            segment_length = 10 * 60 * 1000  # 10 minutes in milliseconds
            total_length = len(audio)

            split_files = []
            temp_dir = tempfile.mkdtemp()

            for start_time in range(0, total_length, segment_length):
                end_time = min(start_time + segment_length, total_length)
                segment = audio[start_time:end_time]

                segment_filename = f"{Path(file_path).stem}_seg_{start_time//1000}-{(end_time)//1000}.wav"
                segment_path = os.path.join(temp_dir, segment_filename)
                segment.export(segment_path, format='wav')

                split_files.append(segment_path)

            logger.info(f"Split audio {file_path} into {len(split_files)} segments")
            return split_files

        except ImportError:
            logger.warning("pydub not available for audio splitting")
            return [file_path]
        except Exception as e:
            logger.error(f"Audio splitting failed: {e}")
            return [file_path]


class ScalableDocumentProcessor:
    """
    Scalable document processor with parallel processing and fault tolerance.
    """

    def __init__(self, max_workers: int = 4):
        self.config = get_config().document_processing
        self.base_processor = DocumentProcessor()
        self.file_splitter = LargeFileSplitter()
        self.max_workers = max_workers
        self.processing_stats = {
            'total_files': 0,
            'successful_files': 0,
            'failed_files': 0,
            'total_chunks': 0,
            'total_processing_time': 0.0,
            'errors': []
        }

    def process_files_batch(self, file_paths: List[str], doc_ids: Optional[List[str]] = None) -> List[ProcessingResult]:
        """
        Process multiple files in parallel with fault tolerance.
        """
        if doc_ids and len(doc_ids) != len(file_paths):
            raise ValueError("doc_ids length must match file_paths length")

        # Create processing tasks
        tasks = []
        for i, file_path in enumerate(file_paths):
            doc_id = doc_ids[i] if doc_ids else None
            task = ProcessingTask(file_path=file_path, doc_id=doc_id)
            tasks.append(task)

        # Process in parallel
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {}
            for task in tasks:
                future = executor.submit(self._process_single_file_with_retry, task)
                future_to_task[future] = task

            # Collect results
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Task execution failed for {task.file_path}: {e}")
                    # Create failed result
                    result = ProcessingResult(
                        task=task,
                        success=False,
                        error=str(e),
                        file_size=os.path.getsize(task.file_path) if os.path.exists(task.file_path) else 0
                    )
                    results.append(result)

        # Update statistics
        self._update_statistics(results)

        return results

    def process_large_file(self, file_path: str, doc_id: Optional[str] = None) -> List[ProcessingResult]:
        """
        Process a large file by splitting it into smaller parts.
        """
        logger.info(f"Processing large file: {file_path}")

        # Check if file should be split
        if not self.file_splitter.should_split(file_path):
            # Process as single file
            task = ProcessingTask(file_path=file_path, doc_id=doc_id)
            result = self._process_single_file_with_retry(task)
            return [result]

        # Split file
        split_files = self.file_splitter.split_file(file_path)

        if len(split_files) == 1:
            # Splitting failed or not needed, process as single file
            task = ProcessingTask(file_path=file_path, doc_id=doc_id)
            result = self._process_single_file_with_retry(task)
            return [result]

        # Process split files
        logger.info(f"Processing {len(split_files)} file parts in parallel")

        # Generate doc_ids for parts
        part_doc_ids = []
        base_name = Path(file_path).stem
        for i, split_file in enumerate(split_files):
            if doc_id:
                part_id = f"{doc_id}_part_{i+1}"
            else:
                part_id = f"{base_name}_part_{i+1}"
            part_doc_ids.append(part_id)

        results = self.process_files_batch(split_files, part_doc_ids)

        # Clean up temporary split files
        try:
            temp_dir = os.path.dirname(split_files[0])
            if temp_dir.startswith(tempfile.gettempdir()):
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temporary split files in {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary files: {e}")

        return results

    def _process_single_file_with_retry(self, task: ProcessingTask) -> ProcessingResult:
        """Process a single file with retry logic."""
        start_time = time.time()
        last_error = None

        for attempt in range(task.max_retries + 1):
            try:
                file_size = os.path.getsize(task.file_path)

                # Process file
                chunks, metadata = self.base_processor.process_file(task.file_path, task.doc_id)

                processing_time = time.time() - start_time

                return ProcessingResult(
                    task=task,
                    success=True,
                    chunks=chunks,
                    metadata=metadata.__dict__ if hasattr(metadata, '__dict__') else metadata,
                    processing_time=processing_time,
                    file_size=file_size
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Processing attempt {attempt + 1} failed for {task.file_path}: {e}")

                if attempt < task.max_retries:
                    # Exponential backoff
                    time.sleep(2 ** attempt)
                else:
                    # Final failure
                    processing_time = time.time() - start_time
                    return ProcessingResult(
                        task=task,
                        success=False,
                        error=last_error,
                        processing_time=processing_time,
                        file_size=os.path.getsize(task.file_path) if os.path.exists(task.file_path) else 0
                    )

        # Should not reach here
        return ProcessingResult(
            task=task,
            success=False,
            error="Unknown error",
            file_size=0
        )

    def _update_statistics(self, results: List[ProcessingResult]):
        """Update processing statistics."""
        self.processing_stats['total_files'] += len(results)

        for result in results:
            if result.success:
                self.processing_stats['successful_files'] += 1
                if result.chunks:
                    self.processing_stats['total_chunks'] += len(result.chunks)
            else:
                self.processing_stats['failed_files'] += 1
                if result.error:
                    self.processing_stats['errors'].append(result.error)

            self.processing_stats['total_processing_time'] += result.processing_time

    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        stats = self.processing_stats.copy()

        # Calculate derived metrics
        if stats['total_files'] > 0:
            stats['success_rate'] = stats['successful_files'] / stats['total_files']
            stats['average_processing_time'] = stats['total_processing_time'] / stats['total_files']

        if stats['successful_files'] > 0:
            stats['average_chunks_per_file'] = stats['total_chunks'] / stats['successful_files']

        return stats

    def reset_statistics(self):
        """Reset processing statistics."""
        self.processing_stats = {
            'total_files': 0,
            'successful_files': 0,
            'failed_files': 0,
            'total_chunks': 0,
            'total_processing_time': 0.0,
            'errors': []
        }


class ProgressiveDocumentProcessor:
    """
    Progressive processor that can handle incremental processing of large document collections.
    """

    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        self.scalable_processor = ScalableDocumentProcessor()
        os.makedirs(checkpoint_dir, exist_ok=True)

    def process_document_collection(self, file_paths: List[str], batch_size: int = 10) -> Dict[str, Any]:
        """
        Process a large collection of documents with progress tracking and resumability.
        """
        total_files = len(file_paths)
        processed_results = []
        checkpoint_file = os.path.join(self.checkpoint_dir, "processing_checkpoint.json")

        # Load checkpoint if exists
        start_index = self._load_checkpoint(checkpoint_file)

        logger.info(f"Starting progressive processing from index {start_index}/{total_files}")

        try:
            # Process in batches
            for i in range(start_index, total_files, batch_size):
                batch_end = min(i + batch_size, total_files)
                batch_files = file_paths[i:batch_end]

                logger.info(f"Processing batch {i//batch_size + 1}: files {i+1}-{batch_end}")

                # Process batch
                batch_results = self.scalable_processor.process_files_batch(batch_files)
                processed_results.extend(batch_results)

                # Save checkpoint
                self._save_checkpoint(checkpoint_file, batch_end)

                # Log progress
                successful = sum(1 for r in batch_results if r.success)
                logger.info(f"Batch complete: {successful}/{len(batch_results)} successful")

        except Exception as e:
            logger.error(f"Progressive processing failed: {e}")
            # Save emergency checkpoint
            self._save_checkpoint(checkpoint_file, len(processed_results))
            raise

        # Final statistics
        stats = self.scalable_processor.get_statistics()
        stats['progressive_processing'] = True
        stats['final_checkpoint'] = total_files

        return {
            'results': processed_results,
            'statistics': stats
        }

    def _load_checkpoint(self, checkpoint_file: str) -> int:
        """Load processing checkpoint."""
        if os.path.exists(checkpoint_file):
            try:
                import json
                with open(checkpoint_file, 'r') as f:
                    checkpoint = json.load(f)
                return checkpoint.get('processed_count', 0)
            except Exception as e:
                logger.warning(f"Failed to load checkpoint: {e}")

        return 0

    def _save_checkpoint(self, checkpoint_file: str, processed_count: int):
        """Save processing checkpoint."""
        try:
            import json
            checkpoint = {
                'processed_count': processed_count,
                'timestamp': time.time()
            }
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint, f)
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

