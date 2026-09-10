"""
Link validation and URL parsing utilities for cloud storage.
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, parse_qs, urljoin
import validators
import requests
from .base import ValidationResult, CloudFileInfo, LinkValidationError

logger = logging.getLogger(__name__)


class LinkValidator:
    """Validator for cloud storage sharing links."""

    # URL patterns for different cloud storage providers
    PROVIDER_PATTERNS = {
        'google_drive': [
            r'https?://(?:drive\.google\.com|docs\.google\.com)/(?:file/d/|open\?id=|uc\?id=)([a-zA-Z0-9_-]+)',
            r'https?://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
            r'https?://docs\.google\.com/.*[?&]id=([a-zA-Z0-9_-]+)',
        ],
        'baidu_yun': [
            r'https?://pan\.baidu\.com/s/([a-zA-Z0-9_-]+)',
            r'https?://yun\.baidu\.com/s/([a-zA-Z0-9_-]+)',
        ],
        'quark': [
            r'https?://pan\.quark\.cn/s/([a-zA-Z0-9_-]+)',
        ],
        'onedrive': [
            r'https?://(?:onedrive\.live\.com|1drv\.ms)/.*(?:resid=|id=|cid=)([a-zA-Z0-9%_-]+)',
            r'https?://(?:onedrive\.live\.com|1drv\.ms)/redir\?resid=([a-zA-Z0-9%_-]+)',
        ],
        'dropbox': [
            r'https?://(?:www\.)?dropbox\.com/s/([a-zA-Z0-9_-]+)',
            r'https?://(?:www\.)?dropbox\.com/scl/fi/([a-zA-Z0-9_-]+)',
        ],
        'mega': [
            r'https?://mega\.nz/(?:file|folder)/([a-zA-Z0-9_-]+)',
        ],
        'box': [
            r'https?://(?:app\.)?box\.com/s/([a-zA-Z0-9_-]+)',
        ],
        'pcloud': [
            r'https?://(?:www\.)?pcloud\.com/.*[#&]code=([a-zA-Z0-9_-]+)',
        ],
        'mediafire': [
            r'https?://(?:www\.)?mediafire\.com/(?:file|download)/([a-zA-Z0-9_-]+)',
        ]
    }

    # Headers to mimic browser requests
    BROWSER_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    def __init__(self, timeout: int = 10, max_redirects: int = 5):
        self.timeout = timeout
        self.max_redirects = max_redirects

    def identify_provider(self, url: str) -> Optional[str]:
        """Identify the cloud storage provider from URL."""
        if not validators.url(url):
            return None

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Check domain-based identification
        domain_mappings = {
            'drive.google.com': 'google_drive',
            'docs.google.com': 'google_drive',
            'pan.baidu.com': 'baidu_yun',
            'yun.baidu.com': 'baidu_yun',
            'pan.quark.cn': 'quark',
            'onedrive.live.com': 'onedrive',
            '1drv.ms': 'onedrive',
            'dropbox.com': 'dropbox',
            'mega.nz': 'mega',
            'box.com': 'box',
            'pcloud.com': 'pcloud',
            'mediafire.com': 'mediafire'
        }

        for domain_pattern, provider in domain_mappings.items():
            if domain_pattern in domain:
                return provider

        # Fallback to pattern matching
        for provider, patterns in self.PROVIDER_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url):
                    return provider

        return None

    def extract_file_id(self, url: str, provider: str) -> Optional[str]:
        """Extract file ID from sharing URL."""
        if provider not in self.PROVIDER_PATTERNS:
            return None

        patterns = self.PROVIDER_PATTERNS[provider]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                file_id = match.group(1)
                # URL decode if necessary
                if '%' in file_id:
                    from urllib.parse import unquote
                    file_id = unquote(file_id)
                return file_id

        return None

    def validate_url_format(self, url: str) -> Tuple[bool, Optional[str]]:
        """Basic URL format validation."""
        if not validators.url(url):
            return False, "Invalid URL format"

        if not url.startswith(('http://', 'https://')):
            return False, "URL must use HTTP or HTTPS protocol"

        return True, None

    def check_url_accessibility(self, url: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Check if URL is accessible and get basic info."""
        try:
            # Configure session with redirects
            session = requests.Session()
            session.max_redirects = self.max_redirects

            # Make HEAD request first (lighter than GET)
            response = session.head(
                url,
                headers=self.BROWSER_HEADERS,
                timeout=self.timeout,
                allow_redirects=True
            )

            # If HEAD fails, try GET
            if response.status_code >= 400:
                response = session.get(
                    url,
                    headers=self.BROWSER_HEADERS,
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=True  # Don't download content
                )

            # Check response
            if response.status_code == 200:
                # Extract basic info from headers
                content_length = response.headers.get('content-length')
                content_type = response.headers.get('content-type', '')
                content_disposition = response.headers.get('content-disposition', '')

                info = {
                    'status_code': response.status_code,
                    'content_type': content_type,
                    'content_length': content_length,
                    'content_disposition': content_disposition,
                    'final_url': response.url
                }

                return True, None, info

            elif response.status_code == 403:
                return False, "Access forbidden - file may be private or require authentication", None
            elif response.status_code == 404:
                return False, "File not found", None
            elif response.status_code >= 500:
                return False, f"Server error: {response.status_code}", None
            else:
                return False, f"HTTP {response.status_code}: {response.reason}", None

        except requests.exceptions.Timeout:
            return False, "Request timeout", None
        except requests.exceptions.ConnectionError:
            return False, "Connection error", None
        except requests.exceptions.TooManyRedirects:
            return False, "Too many redirects", None
        except Exception as e:
            return False, f"Network error: {str(e)}", None

    def validate_cloud_link(self, url: str) -> ValidationResult:
        """Comprehensive validation of cloud storage link."""
        try:
            # Step 1: Basic URL validation
            is_valid_format, format_error = self.validate_url_format(url)
            if not is_valid_format:
                return ValidationResult(
                    is_valid=False,
                    error_message=format_error,
                    confidence=0.0
                )

            # Step 2: Identify provider
            provider = self.identify_provider(url)
            if not provider:
                return ValidationResult(
                    is_valid=False,
                    error_message="Unsupported cloud storage provider",
                    confidence=0.0
                )

            # Step 3: Extract file ID
            file_id = self.extract_file_id(url, provider)
            if not file_id:
                return ValidationResult(
                    is_valid=False,
                    error_message="Could not extract file ID from URL",
                    confidence=0.1
                )

            # Step 4: Check accessibility
            is_accessible, access_error, response_info = self.check_url_accessibility(url)
            if not is_accessible:
                return ValidationResult(
                    is_valid=False,
                    provider=provider,
                    error_message=access_error,
                    confidence=0.3
                )

            # Step 5: Extract file information
            file_info = self._extract_file_info(url, provider, file_id, response_info)

            return ValidationResult(
                is_valid=True,
                provider=provider,
                file_info=file_info,
                confidence=0.9
            )

        except Exception as e:
            logger.error(f"Link validation error: {e}", exc_info=True)
            return ValidationResult(
                is_valid=False,
                error_message=f"Validation failed: {str(e)}",
                confidence=0.0
            )

    def _extract_file_info(self, url: str, provider: str, file_id: str, response_info: Dict[str, Any]) -> CloudFileInfo:
        """Extract file information from response."""
        from datetime import datetime

        # Try to extract filename from various sources
        filename = self._extract_filename(url, response_info)

        # Get file size
        size = 0
        if response_info.get('content_length'):
            try:
                size = int(response_info['content_length'])
            except (ValueError, TypeError):
                pass

        # Get MIME type
        mime_type = response_info.get('content_type', 'application/octet-stream')
        if not mime_type or mime_type == 'application/octet-stream':
            mime_type = self._guess_mime_type(filename)

        return CloudFileInfo(
            file_id=file_id,
            filename=filename,
            size=size,
            mime_type=mime_type,
            download_url=url,
            is_public=True,  # Assuming sharing links are public
            metadata={
                'provider': provider,
                'original_url': url,
                'response_headers': response_info
            }
        )

    def _extract_filename(self, url: str, response_info: Dict[str, Any]) -> str:
        """Extract filename from URL or response headers."""
        # Try Content-Disposition header first
        content_disposition = response_info.get('content_disposition', '')
        if content_disposition:
            import re
            filename_match = re.search(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', content_disposition, re.IGNORECASE)
            if filename_match:
                filename = filename_match.group(1).strip('\'"')
                if filename:
                    return filename

        # Try to extract from URL path
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        if path_parts:
            last_part = path_parts[-1]
            if '.' in last_part and len(last_part) > 1:
                return last_part

        # Fallback to generic name with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"cloud_file_{timestamp}"

    def _guess_mime_type(self, filename: str) -> str:
        """Guess MIME type from filename."""
        import mimetypes
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or 'application/octet-stream'

    def batch_validate_links(self, urls: List[str]) -> Dict[str, ValidationResult]:
        """Validate multiple links in batch."""
        results = {}
        for url in urls:
            results[url] = self.validate_cloud_link(url)
        return results







