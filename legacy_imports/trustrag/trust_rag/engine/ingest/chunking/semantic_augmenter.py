"""
TrustRAG 2.0 Semantic Augmenter

Generates semantic summaries for complex tables using LLM to improve retrieval.

Features:
1. Async batch processing with rate limiting
2. Complexity-based filtering (only augment complex tables)
3. Graceful degradation on LLM failures
4. Metadata injection for enhanced retrieval
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import time

from trust_rag.engine.ingest.models import Chunk

logger = logging.getLogger(__name__)


class AugmenterConfig(BaseModel):
    """Configuration for semantic augmenter"""
    llm_model: str = Field(default="gpt-4o-mini", description="LLM model for summarization")
    max_summary_length: int = Field(default=50, description="Maximum summary length in words")
    complexity_threshold: int = Field(default=100, description="Minimum tokens to trigger augmentation")
    batch_size: int = Field(default=5, description="Batch size for concurrent requests")
    rate_limit_rpm: int = Field(default=60, description="Rate limit in requests per minute")
    enable_augmentation: bool = Field(default=True, description="Enable/disable augmentation")
    api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    base_url: Optional[str] = Field(default=None, description="Custom API base URL")


class SemanticAugmenter:
    """
    Semantic augmenter for table chunks
    
    Generates concise summaries for complex tables to improve vector retrieval.
    Uses async batch processing with rate limiting and graceful degradation.
    """
    
    def __init__(self, config: Optional[AugmenterConfig] = None):
        """Initialize augmenter with configuration"""
        self.config = config or AugmenterConfig()
        self._llm_client = None
        self._semaphore = None
        self._request_times: List[float] = []
    
    def _init_llm_client(self):
        """Lazy initialization of LLM client"""
        if self._llm_client is not None:
            return
        
        try:
            import openai
            
            # Initialize OpenAI client
            client_kwargs = {}
            if self.config.api_key:
                client_kwargs['api_key'] = self.config.api_key
            if self.config.base_url:
                client_kwargs['base_url'] = self.config.base_url
            
            self._llm_client = openai.AsyncOpenAI(**client_kwargs)
            
            # Initialize semaphore for rate limiting
            self._semaphore = asyncio.Semaphore(self.config.batch_size)
            
            logger.info(f"Initialized LLM client with model={self.config.llm_model}")
            
        except ImportError:
            logger.error("openai package not installed. Install with: pip install openai")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise
    
    async def augment_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Augment chunks with semantic summaries
        
        Args:
            chunks: List of chunks to augment
            
        Returns:
            List of augmented chunks (modified in-place)
        """
        if not self.config.enable_augmentation:
            logger.info("Augmentation disabled, skipping")
            return chunks
        
        # Filter chunks that need augmentation
        chunks_to_augment = [
            (idx, chunk) for idx, chunk in enumerate(chunks)
            if self._should_augment(chunk)
        ]
        
        if not chunks_to_augment:
            logger.info("No chunks need augmentation")
            return chunks
        
        logger.info(f"Augmenting {len(chunks_to_augment)} chunks out of {len(chunks)}")
        
        # Initialize LLM client
        self._init_llm_client()
        
        # Process in batches
        for i in range(0, len(chunks_to_augment), self.config.batch_size):
            batch = chunks_to_augment[i:i + self.config.batch_size]
            
            # Create async tasks for batch
            tasks = [
                self._augment_single_chunk(idx, chunk)
                for idx, chunk in batch
            ]
            
            # Execute batch concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for (idx, chunk), result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.warning(f"Failed to augment chunk {idx}: {result}")
                    chunk.metadata["summary_failed"] = True
                    chunk.metadata["summary_error"] = str(result)
                elif result:
                    # Inject summary into chunk
                    chunks[idx] = self._inject_summary(chunk, result)
        
        logger.info(f"Augmentation complete. Processed {len(chunks_to_augment)} chunks")
        
        return chunks
    
    def _should_augment(self, chunk: Chunk) -> bool:
        """
        Check if chunk should be augmented
        
        Criteria:
        - Chunk type is table
        - Token count exceeds complexity threshold
        - Not already augmented
        """
        # Check if it's a table chunk
        chunk_type = chunk.metadata.get("chunk_type", "")
        if chunk_type != "table":
            return False
        
        # Check if already augmented
        if "table_summary" in chunk.metadata:
            return False
        
        # Check complexity (token estimate)
        token_estimate = len(chunk.text) // 4
        if token_estimate < self.config.complexity_threshold:
            return False
        
        return True
    
    async def _augment_single_chunk(self, idx: int, chunk: Chunk) -> Optional[str]:
        """
        Generate summary for a single chunk
        
        Uses rate limiting and exponential backoff
        """
        async with self._semaphore:
            # Rate limiting
            await self._wait_for_rate_limit()
            
            try:
                # Generate summary
                summary = await self._generate_table_summary(chunk.text)
                
                logger.debug(f"Generated summary for chunk {idx}: {summary[:50]}...")
                
                return summary
                
            except Exception as e:
                logger.error(f"Error generating summary for chunk {idx}: {e}")
                raise
    
    async def _generate_table_summary(self, table_content: str) -> str:
        """
        Generate semantic summary for table using LLM
        
        Args:
            table_content: Table content in Markdown format
            
        Returns:
            Concise summary (max 50 words)
        """
        # Construct prompt
        prompt = f"""请用不超过{self.config.max_summary_length}字总结以下表格的核心内容。
重点描述：
1. 表格主题和用途
2. 关键数据特征（如最高/最低值、趋势等）
3. 重要列名和数据类型

表格内容：
{table_content[:1000]}  # Limit input to avoid token overflow

请用简洁的中文回答："""
        
        try:
            # Call LLM API
            response = await self._llm_client.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": "你是一个专业的数据分析助手，擅长总结表格内容。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Record request time for rate limiting
            self._request_times.append(time.time())
            
            return summary
            
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise
    
    async def _wait_for_rate_limit(self):
        """
        Wait if necessary to respect rate limits
        
        Implements sliding window rate limiting
        """
        now = time.time()
        
        # Remove requests older than 1 minute
        self._request_times = [
            t for t in self._request_times
            if now - t < 60
        ]
        
        # Check if we've hit the rate limit
        if len(self._request_times) >= self.config.rate_limit_rpm:
            # Calculate wait time
            oldest_request = self._request_times[0]
            wait_time = 60 - (now - oldest_request)
            
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
    
    def _inject_summary(self, chunk: Chunk, summary: str) -> Chunk:
        """
        Inject summary into chunk metadata and optionally prepend to content
        
        Args:
            chunk: Original chunk
            summary: Generated summary
            
        Returns:
            Modified chunk
        """
        # Add summary to metadata
        chunk.metadata["table_summary"] = summary
        chunk.metadata["summary_generated"] = True
        
        # Optionally prepend summary to content for better vector representation
        # Format: [Summary: ...]\n\n[Original Content]
        summary_prefix = f"[Summary: {summary}]\n\n"
        
        # Check if content already has a context prefix
        if chunk.text.startswith("[Context:"):
            # Insert summary after context
            parts = chunk.text.split("\n\n", 1)
            if len(parts) == 2:
                chunk.text = f"{parts[0]}\n\n{summary_prefix}{parts[1]}"
            else:
                chunk.text = f"{chunk.text}\n\n{summary_prefix}"
        else:
            # Prepend summary
            chunk.text = summary_prefix + chunk.text
        
        return chunk
    
    def get_stats(self) -> Dict[str, Any]:
        """Get augmentation statistics"""
        return {
            "enabled": self.config.enable_augmentation,
            "model": self.config.llm_model,
            "complexity_threshold": self.config.complexity_threshold,
            "recent_requests": len(self._request_times),
            "rate_limit_rpm": self.config.rate_limit_rpm
        }
