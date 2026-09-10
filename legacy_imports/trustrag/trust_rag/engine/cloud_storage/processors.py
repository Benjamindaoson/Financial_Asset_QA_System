"""
Cloud storage processor implementations for different providers.
"""

import asyncio
import logging
import os
import tempfile
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import aiohttp
import requests
from urllib.parse import urlparse, parse_qs
from .base import (
    CloudStorageProvider,
    CloudFileInfo,
    ValidationResult,
    DownloadResult,
    LinkValidationError,
    DownloadError
)

logger = logging.getLogger(__name__)


class GoogleDriveProcessor(CloudStorageProvider):
    """Google Drive file processor."""

    SUPPORTED_FORMATS = [
        'pdf', 'doc', 'docx', 'txt', 'html', 'htm',
        'csv', 'xlsx', 'xls', 'ppt', 'pptx',
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff',
        'mp3', 'wav', 'mp4', 'avi', 'mov', 'm4a'
    ]

    @property
    def provider_name(self) -> str:
        return "google_drive"

    def can_handle_url(self, url: str) -> bool:
        """Check if URL is a Google Drive sharing link."""
        return any(domain in url.lower() for domain in ['drive.google.com', 'docs.google.com'])

    async def validate_link(self, url: str) -> ValidationResult:
        """Validate Google Drive sharing link."""
        try:
            # Extract file ID
            file_id = self._extract_file_id(url)
            if not file_id:
                raise LinkValidationError("Invalid Google Drive URL format", self.provider_name, url)

            # Try to get file metadata from Google Drive API
            # For now, we'll use basic validation
            file_info = await self._get_file_info_basic(url, file_id)

            return ValidationResult(
                is_valid=True,
                provider=self.provider_name,
                file_info=file_info,
                confidence=0.8
            )

        except Exception as e:
            logger.error(f"Google Drive validation error: {e}")
            return ValidationResult(
                is_valid=False,
                provider=self.provider_name,
                error_message=str(e),
                confidence=0.0
            )

    async def download_file(
        self,
        url: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> DownloadResult:
        """Download file from Google Drive."""
        try:
            file_id = self._extract_file_id(url)
            if not file_id:
                raise DownloadError("Invalid Google Drive URL", self.provider_name, url)

            # Construct direct download URL
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

            # Download with progress tracking
            start_time = asyncio.get_event_loop().time()

            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status != 200:
                        raise DownloadError(
                            f"Download failed: HTTP {response.status}",
                            self.provider_name,
                            url
                        )

                    # Get file size from headers
                    total_size = int(response.headers.get('Content-Length', 0))
                    downloaded = 0

                    with open(local_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size > 0:
                                progress_callback(downloaded, total_size)

            download_time = asyncio.get_event_loop().time() - start_time

            # Basic file info
            file_size = os.path.getsize(local_path)
            file_info = CloudFileInfo(
                file_id=file_id,
                filename=os.path.basename(local_path),
                size=file_size,
                mime_type=self.get_mime_type_from_filename(local_path),
                download_url=url
            )

            return DownloadResult(
                success=True,
                file_info=file_info,
                local_path=local_path,
                bytes_downloaded=file_size,
                download_time=download_time
            )

        except Exception as e:
            logger.error(f"Google Drive download error: {e}")
            return DownloadResult(
                success=False,
                error_message=str(e)
            )

    def _extract_file_id(self, url: str) -> Optional[str]:
        """Extract file ID from Google Drive URL."""
        import re

        # Pattern for various Google Drive URL formats
        patterns = [
            r'/file/d/([a-zA-Z0-9_-]+)',
            r'/open\?id=([a-zA-Z0-9_-]+)',
            r'/uc\?id=([a-zA-Z0-9_-]+)',
            r'[?&]id=([a-zA-Z0-9_-]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def _get_file_info_basic(self, url: str, file_id: str) -> CloudFileInfo:
        """Get basic file info without API (for public links)."""
        # For basic validation, we'll create a minimal CloudFileInfo
        # In production, you'd use Google Drive API for full metadata
        return CloudFileInfo(
            file_id=file_id,
            filename=f"google_drive_file_{file_id}",
            size=0,  # Unknown without API
            mime_type="application/octet-stream",
            download_url=url,
            is_public=True,
            metadata={'provider': 'google_drive', 'file_id': file_id}
        )


class BaiduYunProcessor(CloudStorageProvider):
    """Baidu Yun (Baidu Cloud) file processor."""

    @property
    def provider_name(self) -> str:
        return "baidu_yun"

    def can_handle_url(self, url: str) -> bool:
        """Check if URL is a Baidu Yun sharing link."""
        return any(domain in url.lower() for domain in ['pan.baidu.com', 'yun.baidu.com'])

    async def validate_link(self, url: str) -> ValidationResult:
        """Validate Baidu Yun sharing link."""
        try:
            share_id = self._extract_share_id(url)
            if not share_id:
                raise LinkValidationError("Invalid Baidu Yun URL format", self.provider_name, url)

            # Basic validation for Baidu Yun links
            file_info = CloudFileInfo(
                file_id=share_id,
                filename=f"baidu_yun_file_{share_id}",
                size=0,
                mime_type="application/octet-stream",
                download_url=url,
                is_public=True,
                metadata={'provider': 'baidu_yun', 'share_id': share_id}
            )

            return ValidationResult(
                is_valid=True,
                provider=self.provider_name,
                file_info=file_info,
                confidence=0.7  # Lower confidence due to limited API access
            )

        except Exception as e:
            logger.error(f"Baidu Yun validation error: {e}")
            return ValidationResult(
                is_valid=False,
                provider=self.provider_name,
                error_message=str(e),
                confidence=0.0
            )

    async def download_file(
        self,
        url: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> DownloadResult:
        """Download file from Baidu Yun."""
        # Note: Baidu Yun downloads often require authentication
        # This is a simplified implementation
        return DownloadResult(
            success=False,
            error_message="Baidu Yun downloads require authentication. Please use direct download links."
        )

    def _extract_share_id(self, url: str) -> Optional[str]:
        """Extract share ID from Baidu Yun URL."""
        import re
        match = re.search(r'/s/([a-zA-Z0-9_-]+)', url)
        return match.group(1) if match else None


class QuarkProcessor(CloudStorageProvider):
    """Quark cloud storage processor."""

    @property
    def provider_name(self) -> str:
        return "quark"

    def can_handle_url(self, url: str) -> bool:
        """Check if URL is a Quark sharing link."""
        return 'pan.quark.cn' in url.lower()

    async def validate_link(self, url: str) -> ValidationResult:
        """Validate Quark sharing link."""
        try:
            share_id = self._extract_share_id(url)
            if not share_id:
                raise LinkValidationError("Invalid Quark URL format", self.provider_name, url)

            file_info = CloudFileInfo(
                file_id=share_id,
                filename=f"quark_file_{share_id}",
                size=0,
                mime_type="application/octet-stream",
                download_url=url,
                is_public=True,
                metadata={'provider': 'quark', 'share_id': share_id}
            )

            return ValidationResult(
                is_valid=True,
                provider=self.provider_name,
                file_info=file_info,
                confidence=0.7
            )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                provider=self.provider_name,
                error_message=str(e),
                confidence=0.0
            )

    async def download_file(
        self,
        url: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> DownloadResult:
        """Download file from Quark."""
        return DownloadResult(
            success=False,
            error_message="Quark downloads require authentication. Please use direct download links."
        )

    def _extract_share_id(self, url: str) -> Optional[str]:
        """Extract share ID from Quark URL."""
        import re
        match = re.search(r'/s/([a-zA-Z0-9_-]+)', url)
        return match.group(1) if match else None


class OneDriveProcessor(CloudStorageProvider):
    """Microsoft OneDrive processor."""

    @property
    def provider_name(self) -> str:
        return "onedrive"

    def can_handle_url(self, url: str) -> bool:
        """Check if URL is a OneDrive sharing link."""
        return any(domain in url.lower() for domain in ['onedrive.live.com', '1drv.ms'])

    async def validate_link(self, url: str) -> ValidationResult:
        """Validate OneDrive sharing link."""
        try:
            resource_id = self._extract_resource_id(url)
            if not resource_id:
                raise LinkValidationError("Invalid OneDrive URL format", self.provider_name, url)

            file_info = CloudFileInfo(
                file_id=resource_id,
                filename=f"onedrive_file_{resource_id[:8]}",
                size=0,
                mime_type="application/octet-stream",
                download_url=url,
                is_public=True,
                metadata={'provider': 'onedrive', 'resource_id': resource_id}
            )

            return ValidationResult(
                is_valid=True,
                provider=self.provider_name,
                file_info=file_info,
                confidence=0.8
            )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                provider=self.provider_name,
                error_message=str(e),
                confidence=0.0
            )

    async def download_file(
        self,
        url: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> DownloadResult:
        """Download file from OneDrive."""
        try:
            # OneDrive sharing links can be complex
            # For now, return not supported for direct download
            return DownloadResult(
                success=False,
                error_message="OneDrive downloads require Microsoft Graph API authentication."
            )
        except Exception as e:
            return DownloadResult(
                success=False,
                error_message=str(e)
            )

    def _extract_resource_id(self, url: str) -> Optional[str]:
        """Extract resource ID from OneDrive URL."""
        import re
        patterns = [
            r'resid=([a-zA-Z0-9%_-]+)',
            r'id=([a-zA-Z0-9%_-]+)',
            r'cid=([a-zA-Z0-9%_-]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None


class DropboxProcessor(CloudStorageProvider):
    """Dropbox processor."""

    @property
    def provider_name(self) -> str:
        return "dropbox"

    def can_handle_url(self, url: str) -> bool:
        """Check if URL is a Dropbox sharing link."""
        return 'dropbox.com' in url.lower()

    async def validate_link(self, url: str) -> ValidationResult:
        """Validate Dropbox sharing link."""
        try:
            file_id = self._extract_file_id(url)
            if not file_id:
                raise LinkValidationError("Invalid Dropbox URL format", self.provider_name, url)

            file_info = CloudFileInfo(
                file_id=file_id,
                filename=f"dropbox_file_{file_id[:8]}",
                size=0,
                mime_type="application/octet-stream",
                download_url=url,
                is_public=True,
                metadata={'provider': 'dropbox', 'file_id': file_id}
            )

            return ValidationResult(
                is_valid=True,
                provider=self.provider_name,
                file_info=file_info,
                confidence=0.8
            )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                provider=self.provider_name,
                error_message=str(e),
                confidence=0.0
            )

    async def download_file(
        self,
        url: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> DownloadResult:
        """Download file from Dropbox."""
        try:
            # Convert sharing link to direct download link
            if 'dropbox.com' in url and '/s/' in url:
                download_url = url.replace('dropbox.com', 'dl.dropboxusercontent.com').replace('?dl=0', '')
            else:
                download_url = url

            start_time = asyncio.get_event_loop().time()

            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status != 200:
                        raise DownloadError(
                            f"Download failed: HTTP {response.status}",
                            self.provider_name,
                            url
                        )

                    total_size = int(response.headers.get('Content-Length', 0))
                    downloaded = 0

                    with open(local_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size > 0:
                                progress_callback(downloaded, total_size)

            download_time = asyncio.get_event_loop().time() - start_time
            file_size = os.path.getsize(local_path)

            file_info = CloudFileInfo(
                file_id=self._extract_file_id(url) or "unknown",
                filename=os.path.basename(local_path),
                size=file_size,
                mime_type=self.get_mime_type_from_filename(local_path),
                download_url=url
            )

            return DownloadResult(
                success=True,
                file_info=file_info,
                local_path=local_path,
                bytes_downloaded=file_size,
                download_time=download_time
            )

        except Exception as e:
            return DownloadResult(
                success=False,
                error_message=str(e)
            )

    def _extract_file_id(self, url: str) -> Optional[str]:
        """Extract file ID from Dropbox URL."""
        import re
        patterns = [
            r'/s/([a-zA-Z0-9_-]+)',
            r'/scl/fi/([a-zA-Z0-9_-]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None


class CloudStorageProcessor:
    """Main processor that delegates to specific providers."""

    def __init__(self):
        self.providers = {
            'google_drive': GoogleDriveProcessor(),
            'baidu_yun': BaiduYunProcessor(),
            'quark': QuarkProcessor(),
            'onedrive': OneDriveProcessor(),
            'dropbox': DropboxProcessor(),
        }
        self.logger = logging.getLogger(__name__)

    def get_provider(self, url: str) -> Optional[CloudStorageProvider]:
        """Get the appropriate provider for a URL."""
        for provider in self.providers.values():
            if provider.can_handle_url(url):
                return provider
        return None

    async def validate_link(self, url: str) -> ValidationResult:
        """Validate a cloud storage link."""
        provider = self.get_provider(url)
        if not provider:
            return ValidationResult(
                is_valid=False,
                error_message="Unsupported cloud storage provider",
                confidence=0.0
            )

        return await provider.validate_link(url)

    async def download_file(
        self,
        url: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> DownloadResult:
        """Download a file from cloud storage."""
        provider = self.get_provider(url)
        if not provider:
            return DownloadResult(
                success=False,
                error_message="Unsupported cloud storage provider"
            )

        return await provider.download_file(url, local_path, progress_callback)

    def get_supported_providers(self) -> List[str]:
        """Get list of supported providers."""
        return list(self.providers.keys())







