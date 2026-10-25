"""HTTP client for BAAK with Cloudflare bypass."""

import time
import logging
from typing import Optional, Dict, Any
from urllib.parse import urljoin

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

import requests


logger = logging.getLogger(__name__)


class BAAKClient:
    """HTTP client for fetching BAAK data with Cloudflare handling."""

    def __init__(
        self,
        base_url: str = "https://baak.gunadarma.ac.id",
        timeout: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        use_curl_cffi: bool = True,
    ):
        """
        Initialize BAAK client.
        
        Args:
            base_url: Base URL for BAAK
            timeout: Request timeout in seconds
            max_retries: Number of retries on failure
            retry_delay: Delay between retries in seconds
            use_curl_cffi: Whether to use curl-cffi (True) or requests (False)
        """
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_curl_cffi = use_curl_cffi and cffi_requests is not None
        
        if not self.use_curl_cffi and use_curl_cffi:
            logger.warning("curl-cffi not available, falling back to requests")
        
        # Headers to mimic a real browser
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        GET request to BAAK endpoint.
        
        Args:
            path: URL path (relative to base_url)
            params: Query parameters
            
        Returns:
            Response text or None on failure
        """
        url = urljoin(self.base_url, path)
        
        for attempt in range(self.max_retries):
            try:
                if self.use_curl_cffi:
                    response = cffi_requests.get(
                        url,
                        params=params,
                        headers=self.headers,
                        timeout=self.timeout,
                        impersonate="chrome120",  # TLS fingerprint
                    )
                else:
                    response = requests.get(
                        url,
                        params=params,
                        headers=self.headers,
                        timeout=self.timeout,
                    )
                
                response.raise_for_status()
                logger.info(f"✓ GET {url} (attempt {attempt + 1})")
                return response.text
                
            except Exception as e:
                logger.warning(
                    f"✗ GET {url} (attempt {attempt + 1}/{self.max_retries}): {type(e).__name__}: {e}"
                )
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Failed after {self.max_retries} attempts")
                    return None
        
        return None

    def is_cloudflare_error(self, html: str) -> bool:
        """Check if response is Cloudflare error page."""
        return any(marker in html for marker in [
            "cf_clearance",
            "Challenge",
            "Just a moment",
            "Cloudflare",
        ])
