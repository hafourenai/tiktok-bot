"""Security validation for URLs and HTTP operations."""
import asyncio
import logging
import socket
from urllib.parse import urlparse

from src.news.sources import ALLOWED_ARTICLE_DOMAINS

logger = logging.getLogger(__name__)


async def is_public_ip(hostname: str) -> bool:
    """Check if hostname resolves to a public IP (not loopback, private, or link-local)."""
    try:
        # Resolve hostname to IP
        loop = asyncio.get_event_loop()
        addr_info = await loop.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        
        for *_metadata, sockaddr in addr_info:
            ip = sockaddr[0]
            
            # Check IPv4 private ranges and loopback
            if "." in ip:
                parts = [int(x) for x in ip.split(".")]
                # Loopback (127.0.0.0/8)
                if parts[0] == 127:
                    return False
                # Private ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
                if parts[0] == 10 or (parts[0] == 172 and 16 <= parts[1] <= 31) or (parts[0] == 192 and parts[1] == 168):
                    return False
                # Link-local (169.254.0.0/16)
                if parts[0] == 169 and parts[1] == 254:
                    return False
            
            # Check IPv6 loopback/private (simplified)
            if ":" in ip:
                if ip.startswith("::1") or ip.startswith("fc") or ip.startswith("fd"):
                    return False
        
        return True
    except (socket.gaierror, OSError, ValueError):
        logger.warning("Could not resolve hostname %s", hostname)
        return False


async def is_safe_url(url: str, allowed_domains: set = None) -> tuple[bool, str]:
    """
    Validate URL for security:
    - Must be HTTPS
    - Host must be in allowlist or be public IP
    - No internal/loopback addresses
    
    Returns: (is_safe, reason)
    """
    if not allowed_domains:
        allowed_domains = ALLOWED_ARTICLE_DOMAINS
    
    try:
        parsed = urlparse(url)
        
        # Must be HTTPS
        if parsed.scheme != "https":
            return False, f"URL must use HTTPS, got {parsed.scheme}"
        
        # Must have netloc
        if not parsed.netloc:
            return False, "URL missing host"
        
        # Extract hostname (remove port if present)
        hostname = parsed.hostname or parsed.netloc.split(":")[0]
        
        # Check allowlist first
        if hostname in allowed_domains:
            return True, "Hostname in allowlist"
        
        # Check if IP is public
        is_public = await is_public_ip(hostname)
        if not is_public:
            return False, f"Hostname {hostname} resolves to non-public IP"
        
        return True, "Public hostname verified"
    except Exception as e:
        logger.warning("URL validation error for %s: %s", url, e)
        return False, f"URL validation error: {e}"
