"""
Batch Ingestion and Auto-Sync Automation.

Supports:
- Scheduled batch ingestion
- Automatic index synchronization
- Watch mode for new documents
"""
import os
import time
import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from trust_rag.config import get_paths
from trust_rag.engine.ingest.pipeline import IngestPipeline
from trust_rag.core.monitoring import get_monitor, monitor_operation

logger = logging.getLogger(__name__)


class BatchIngester:
    """
    Batch document ingestion with automatic synchronization.
    
    Features:
    - Batch process all documents in a directory
    - Automatic index refresh after ingestion
    - Progress tracking and error reporting
    """
    
    def __init__(
        self,
        source_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        profile: str = "generic"
    ):
        """
        Initialize batch ingester.
        
        Args:
            source_dir: Directory containing documents to ingest
            output_dir: Output directory for ingestion artifacts
            profile: Ingest profile to use
        """
        self.source_dir = source_dir or get_paths().raw_docs_dir
        self.output_dir = output_dir or get_paths().ingestion_dir
        self.profile = profile
        self.pipeline = IngestPipeline(output_dir=self.output_dir)
        self.monitor = get_monitor()
    
    @monitor_operation("batch_ingestion")
    def ingest_batch(
        self,
        extensions: Optional[List[str]] = None,
        recursive: bool = True,
        max_files: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Ingest all documents in source directory.
        
        Args:
            extensions: File extensions to process (default: pdf, html, txt, csv, xlsx)
            recursive: Whether to search subdirectories
            max_files: Maximum number of files to process (None = all)
            
        Returns:
            Batch ingestion results
        """
        extensions = extensions or ['.pdf', '.html', '.txt', '.csv', '.xlsx']
        extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in extensions]
        
        # Find all files
        files = self._find_files(extensions, recursive, max_files)
        
        if not files:
            logger.warning(f"No files found in {self.source_dir}")
            return {
                "status": "no_files",
                "total_files": 0,
                "processed": 0,
                "results": []
            }
        
        logger.info(f"Starting batch ingestion: {len(files)} files")
        
        results = []
        success_count = 0
        failed_count = 0
        
        for i, file_path in enumerate(files, 1):
            logger.info(f"Processing [{i}/{len(files)}]: {file_path}")
            
            try:
                result = self.pipeline.ingest(
                    file_path,
                    ingest_profile=self.profile
                )
                
                results.append({
                    "file": file_path,
                    "doc_id": result.doc_id,
                    "status": result.ingest_status,
                    "chunks": len(result.chunks),
                    "errors": result.errors
                })
                
                if result.ingest_status == "OK":
                    success_count += 1
                elif result.ingest_status == "DEGRADED":
                    success_count += 1  # Count as success but with warnings
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to ingest {file_path}: {e}", exc_info=True)
                results.append({
                    "file": file_path,
                    "status": "FAILED",
                    "error": str(e)
                })
                failed_count += 1
        
        summary = {
            "status": "completed",
            "total_files": len(files),
            "processed": len(results),
            "success": success_count,
            "failed": failed_count,
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(
            f"Batch ingestion complete: {success_count} success, "
            f"{failed_count} failed out of {len(files)} files"
        )
        
        return summary
    
    def _find_files(
        self,
        extensions: List[str],
        recursive: bool,
        max_files: Optional[int]
    ) -> List[str]:
        """Find all files matching extensions."""
        files = []
        
        if recursive:
            for root, dirs, filenames in os.walk(self.source_dir):
                for filename in filenames:
                    if any(filename.lower().endswith(ext) for ext in extensions):
                        files.append(os.path.join(root, filename))
                        if max_files and len(files) >= max_files:
                            return files
        else:
            for filename in os.listdir(self.source_dir):
                file_path = os.path.join(self.source_dir, filename)
                if os.path.isfile(file_path):
                    if any(filename.lower().endswith(ext) for ext in extensions):
                        files.append(file_path)
                        if max_files and len(files) >= max_files:
                            return files
        
        return files


class AutoSyncHandler(FileSystemEventHandler):
    """
    File system event handler for automatic ingestion.
    Watches for new files and triggers ingestion.
    """
    
    def __init__(self, ingester: BatchIngester, index_refresher=None):
        """
        Initialize auto-sync handler.
        
        Args:
            ingester: BatchIngester instance
            index_refresher: Function to refresh index (optional)
        """
        self.ingester = ingester
        self.index_refresher = index_refresher
        self.processed_files = set()
    
    def on_created(self, event):
        """Handle file creation event."""
        if event.is_directory:
            return
        
        file_path = event.src_path
        
        # Check if file is ready (not still being written)
        if not self._is_file_ready(file_path):
            return
        
        # Avoid duplicate processing
        if file_path in self.processed_files:
            return
        
        logger.info(f"New file detected: {file_path}")
        
        try:
            result = self.ingester.pipeline.ingest(
                file_path,
                ingest_profile=self.ingester.profile
            )
            
            self.processed_files.add(file_path)
            
            logger.info(
                f"Auto-ingested {file_path}: {result.ingest_status}, "
                f"{len(result.chunks)} chunks"
            )
            
            # Refresh index if refresher provided
            if self.index_refresher:
                try:
                    self.index_refresher()
                    logger.info("Index refreshed after auto-ingestion")
                except Exception as e:
                    logger.error(f"Failed to refresh index: {e}")
                    
        except Exception as e:
            logger.error(f"Auto-ingestion failed for {file_path}: {e}")
    
    def _is_file_ready(self, file_path: str, max_wait: int = 5) -> bool:
        """Check if file is ready (not being written)."""
        try:
            # Wait a bit for file to be fully written
            time.sleep(1)
            
            # Check file size stability
            size1 = os.path.getsize(file_path)
            time.sleep(0.5)
            size2 = os.path.getsize(file_path)
            
            return size1 == size2
        except:
            return False


class AutoSyncService:
    """
    Automatic document synchronization service.
    
    Watches a directory for new documents and automatically ingests them.
    """
    
    def __init__(
        self,
        watch_dir: Optional[str] = None,
        ingester: Optional[BatchIngester] = None,
        index_refresher=None
    ):
        """
        Initialize auto-sync service.
        
        Args:
            watch_dir: Directory to watch for new files
            ingester: BatchIngester instance (optional)
            index_refresher: Function to refresh index (optional)
        """
        self.watch_dir = watch_dir or get_paths().raw_docs_dir
        self.ingester = ingester or BatchIngester()
        self.index_refresher = index_refresher
        self.observer = None
        self.running = False
    
    def start(self):
        """Start watching directory for new files."""
        if self.running:
            logger.warning("Auto-sync service already running")
            return
        
        if not os.path.exists(self.watch_dir):
            logger.error(f"Watch directory does not exist: {self.watch_dir}")
            return
        
        handler = AutoSyncHandler(self.ingester, self.index_refresher)
        self.observer = Observer()
        self.observer.schedule(handler, self.watch_dir, recursive=True)
        self.observer.start()
        self.running = True
        
        logger.info(f"Auto-sync service started, watching: {self.watch_dir}")
    
    def stop(self):
        """Stop watching directory."""
        if not self.running:
            return
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        
        self.running = False
        logger.info("Auto-sync service stopped")
    
    def is_running(self) -> bool:
        """Check if service is running."""
        return self.running


def schedule_batch_ingest(
    interval_seconds: int = 3600,
    source_dir: Optional[str] = None,
    output_dir: Optional[str] = None
):
    """
    Schedule periodic batch ingestion.
    
    Args:
        interval_seconds: Interval between batch runs (default: 1 hour)
        source_dir: Source directory
        output_dir: Output directory
    """
    ingester = BatchIngester(source_dir=source_dir, output_dir=output_dir)
    
    logger.info(f"Scheduled batch ingestion every {interval_seconds} seconds")
    
    while True:
        try:
            logger.info("Starting scheduled batch ingestion")
            result = ingester.ingest_batch()
            logger.info(f"Batch ingestion complete: {result['success']} success, {result['failed']} failed")
        except Exception as e:
            logger.error(f"Scheduled batch ingestion failed: {e}", exc_info=True)
        
        time.sleep(interval_seconds)



