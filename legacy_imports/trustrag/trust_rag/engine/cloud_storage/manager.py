"""
Cloud Storage Manager - Main interface for cloud storage operations.
"""

import asyncio
import logging
import os
import tempfile
import hashlib
from typing import Dict, List, Optional, Any, Callable, Union
from pathlib import Path
from dataclasses import asdict
from datetime import datetime, timedelta
import json

from .validators import LinkValidator
from .processors import CloudStorageProcessor
from .base import (
    CloudFileInfo,
    ValidationResult,
    DownloadResult,
    CloudStorageError,
    LinkValidationError,
    DownloadError
)

logger = logging.getLogger(__name__)


class CloudStorageManager:
    """
    Main manager for cloud storage operations.

    Handles link validation, file downloads, caching, and metadata management.
    """

    SUPPORTED_PROVIDERS = [
        'google_drive', 'baidu_yun', 'quark', 'onedrive', 'dropbox',
        'mega', 'box', 'pcloud', 'mediafire'
    ]

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        max_cache_age_days: int = 7,
        max_concurrent_downloads: int = 3,
        timeout: int = 30
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "cloud_storage_cache"
        self.cache_dir.mkdir(exist_ok=True)

        self.max_cache_age_days = max_cache_age_days
        self.max_concurrent_downloads = max_concurrent_downloads
        self.timeout = timeout

        self.validator = LinkValidator(timeout=timeout)
        self.processor = CloudStorageProcessor()

        # Download semaphore for concurrency control
        self.download_semaphore = asyncio.Semaphore(max_concurrent_downloads)

        # Cache for validation results
        self.validation_cache: Dict[str, ValidationResult] = {}
        self.cache_file = self.cache_dir / "validation_cache.json"

        self._load_cache()

    def _load_cache(self):
        """Load validation cache from disk."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    # Convert back to ValidationResult objects
                    for url, data in cache_data.items():
                        self.validation_cache[url] = ValidationResult(**data)
        except Exception as e:
            logger.warning(f"Failed to load validation cache: {e}")

    def _save_cache(self):
        """Save validation cache to disk."""
        try:
            cache_data = {}
            for url, result in self.validation_cache.items():
                cache_data[url] = asdict(result)

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save validation cache: {e}")

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key for URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _is_cache_valid(self, result: ValidationResult) -> bool:
        """Check if cached validation result is still valid."""
        # Cache for 1 hour
        cache_age = datetime.now().timestamp() - (result.confidence * 3600)
        return cache_age < 3600

    async def validate_link(self, url: str, use_cache: bool = True) -> ValidationResult:
        """
        Validate a cloud storage link.

        Args:
            url: The sharing link to validate
            use_cache: Whether to use cached results

        Returns:
            ValidationResult with link information
        """
        cache_key = self._get_cache_key(url)

        # Check cache first
        if use_cache and cache_key in self.validation_cache:
            cached_result = self.validation_cache[cache_key]
            if self._is_cache_valid(cached_result):
                logger.debug(f"Using cached validation result for {url}")
                return cached_result

        # Perform validation
        result = await self.validator.validate_cloud_link(url)

        # Cache the result
        if result.confidence > 0:
            self.validation_cache[cache_key] = result
            self._save_cache()

        return result

    async def download_file(
        self,
        url: str,
        local_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        validate_first: bool = True
    ) -> DownloadResult:
        """
        Download a file from cloud storage.

        Args:
            url: The sharing link
            local_path: Local path to save file (auto-generated if None)
            progress_callback: Callback for download progress
            validate_first: Whether to validate link before download

        Returns:
            DownloadResult with operation status
        """
        async with self.download_semaphore:
            try:
                # Validate link first if requested
                if validate_first:
                    validation = await self.validate_link(url)
                    if not validation.is_valid:
                        return DownloadResult(
                            success=False,
                            error_message=validation.error_message or "Link validation failed"
                        )

                # Generate local path if not provided
                if not local_path:
                    file_id = validation.file_info.file_id if validate_first else "unknown"
                    filename = getattr(validation.file_info, 'filename', f"cloud_file_{file_id}")
                    local_path = str(self.cache_dir / filename)

                # Ensure directory exists
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                # Download the file
                result = await self.processor.download_file(url, local_path, progress_callback)

                # Clean up on failure
                if not result.success and os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                    except OSError:
                        pass

                return result

            except Exception as e:
                logger.error(f"Download failed for {url}: {e}")
                return DownloadResult(
                    success=False,
                    error_message=str(e)
                )

    async def batch_validate_links(self, urls: List[str]) -> Dict[str, ValidationResult]:
        """
        Validate multiple links in batch.

        Args:
            urls: List of sharing links to validate

        Returns:
            Dictionary mapping URLs to validation results
        """
        tasks = [self.validate_link(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        validation_results = {}
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                validation_results[url] = ValidationResult(
                    is_valid=False,
                    error_message=str(result),
                    confidence=0.0
                )
            else:
                validation_results[url] = result

        return validation_results

    async def batch_download_files(
        self,
        urls: List[str],
        output_dir: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[str, DownloadResult]:
        """
        Download multiple files in batch.

        Args:
            urls: List of sharing links
            output_dir: Directory to save files
            progress_callback: Callback with (url, downloaded, total) signature

        Returns:
            Dictionary mapping URLs to download results
        """
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
        else:
            output_path = self.cache_dir

        async def download_with_progress(url: str) -> DownloadResult:
            def progress_cb(downloaded: int, total: int):
                if progress_callback:
                    progress_callback(url, downloaded, total)

            local_path = str(output_path / f"cloud_file_{hash(url) % 10000}")
            return await self.download_file(url, local_path, progress_cb, validate_first=False)

        # Download concurrently but respect semaphore
        tasks = [download_with_progress(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        download_results = {}
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                download_results[url] = DownloadResult(
                    success=False,
                    error_message=str(result)
                )
            else:
                download_results[url] = result

        return download_results

    def cleanup_cache(self, max_age_days: Optional[int] = None):
        """
        Clean up old cached files and validation results.

        Args:
            max_age_days: Maximum age in days (uses instance default if None)
        """
        max_age = max_age_days or self.max_cache_age_days
        cutoff_time = datetime.now().timestamp() - (max_age * 24 * 60 * 60)

        # Clean up files
        for file_path in self.cache_dir.glob("*"):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    if stat.st_mtime < cutoff_time:
                        file_path.unlink()
                        logger.debug(f"Cleaned up old cache file: {file_path}")
                except OSError as e:
                    logger.warning(f"Failed to clean up {file_path}: {e}")

        # Clean up validation cache
        expired_urls = []
        for url, result in self.validation_cache.items():
            # Simple heuristic: remove low confidence results
            if result.confidence < 0.5:
                expired_urls.append(url)

        for url in expired_urls:
            del self.validation_cache[url]

        if expired_urls:
            self._save_cache()
            logger.debug(f"Cleaned up {len(expired_urls)} expired validation cache entries")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_files = 0
        total_size = 0

        for file_path in self.cache_dir.glob("*"):
            if file_path.is_file():
                total_files += 1
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    pass

        return {
            'cache_directory': str(self.cache_dir),
            'total_cached_files': total_files,
            'total_cache_size_bytes': total_size,
            'total_cache_size_mb': total_size / (1024 * 1024),
            'validation_cache_entries': len(self.validation_cache),
            'supported_providers': self.SUPPORTED_PROVIDERS
        }

    def get_supported_providers(self) -> List[str]:
        """Get list of supported cloud storage providers."""
        return self.SUPPORTED_PROVIDERS.copy()

    def is_supported_provider(self, provider: str) -> bool:
        """Check if a provider is supported."""
        return provider.lower() in self.SUPPORTED_PROVIDERS







