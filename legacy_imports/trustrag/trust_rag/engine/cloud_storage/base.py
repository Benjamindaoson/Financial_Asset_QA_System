"""
Base classes and interfaces for cloud storage providers.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import mimetypes
import validators

logger = logging.getLogger(__name__)


@dataclass
class CloudFileInfo:
    """Information about a file in cloud storage."""

    file_id: str
    filename: str
    size: int  # bytes
    mime_type: str
    download_url: Optional[str] = None
    direct_url: Optional[str] = None  # Direct download URL if available
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    owner: Optional[str] = None
    is_public: bool = False
    expires_at: Optional[datetime] = None  # For temporary links
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @property
    def is_expired(self) -> bool:
        """Check if the file link has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    @property
    def size_mb(self) -> float:
        """File size in MB."""
        return self.size / (1024 * 1024)

    @property
    def file_extension(self) -> Optional[str]:
        """File extension from filename."""
        if '.' in self.filename:
            return self.filename.split('.')[-1].lower()
        return None

    def is_supported_format(self, supported_formats: List[str]) -> bool:
        """Check if file format is supported."""
        if not self.file_extension:
            return False
        return self.file_extension in [fmt.lower() for fmt in supported_formats]


@dataclass
class DownloadResult:
    """Result of a file download operation."""

    success: bool
    file_info: Optional[CloudFileInfo] = None
    local_path: Optional[str] = None
    error_message: Optional[str] = None
    bytes_downloaded: int = 0
    download_time: float = 0.0  # seconds


@dataclass
class ValidationResult:
    """Result of link validation."""

    is_valid: bool
    provider: Optional[str] = None
    file_info: Optional[CloudFileInfo] = None
    error_message: Optional[str] = None
    confidence: float = 0.0  # 0.0 to 1.0


class CloudStorageProvider(ABC):
    """Abstract base class for cloud storage providers."""

    # Supported file formats for this provider
    SUPPORTED_FORMATS = [
        'pdf', 'doc', 'docx', 'txt', 'html', 'htm',
        'csv', 'xlsx', 'xls', 'ppt', 'pptx',
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff',
        'mp3', 'wav', 'mp4', 'avi', 'mov', 'm4a'
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the cloud storage provider."""
        pass

    @abstractmethod
    def can_handle_url(self, url: str) -> bool:
        """Check if this provider can handle the given URL."""
        pass

    @abstractmethod
    async def validate_link(self, url: str) -> ValidationResult:
        """Validate if the link is accessible and get file info."""
        pass

    @abstractmethod
    async def download_file(
        self,
        url: str,
        local_path: str,
        progress_callback: Optional[callable] = None
    ) -> DownloadResult:
        """Download file from cloud storage to local path."""
        pass

    def validate_file_format(self, file_info: CloudFileInfo) -> bool:
        """Validate if the file format is supported."""
        return file_info.is_supported_format(self.SUPPORTED_FORMATS)

    def get_mime_type_from_filename(self, filename: str) -> str:
        """Get MIME type from filename."""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or 'application/octet-stream'

    def parse_file_size(self, size_str: str) -> Optional[int]:
        """Parse file size string (e.g., '1.5MB', '500KB') to bytes."""
        if not size_str:
            return None

        try:
            # Handle various formats
            size_str = size_str.upper().replace(' ', '')

            # Extract number and unit
            import re
            match = re.match(r'^(\d+(?:\.\d+)?)([KMGT]?B?)$', size_str)
            if not match:
                return None

            number, unit = match.groups()
            number = float(number)

            # Convert to bytes
            multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4}
            multiplier = multipliers.get(unit, 1) if unit else 1

            return int(number * multiplier)
        except (ValueError, TypeError):
            return None


class CloudStorageError(Exception):
    """Base exception for cloud storage operations."""

    def __init__(self, message: str, provider: str = None, url: str = None):
        self.message = message
        self.provider = provider
        self.url = url
        super().__init__(f"{provider or 'CloudStorage'}: {message}")


class LinkValidationError(CloudStorageError):
    """Exception raised when link validation fails."""
    pass


class DownloadError(CloudStorageError):
    """Exception raised when file download fails."""
    pass


class UnsupportedFormatError(CloudStorageError):
    """Exception raised when file format is not supported."""
    pass







