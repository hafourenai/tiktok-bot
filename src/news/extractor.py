"""Article text extraction."""
import asyncio
import logging
from typing import Optional

import httpx

try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

from src.news.security import is_safe_url

logger = logging.getLogger(__name__)

DEFAULT_EXTRACT_TIMEOUT = 15
DEFAULT_MAX_ARTICLE_SIZE = 3 * 1024 * 1024  # 3 MB


async def extract_article_text(
    url: str,
    timeout: int = DEFAULT_EXTRACT_TIMEOUT,
) -> tuple[Optional[str], Optional[str]]:
    """
    Extract article text from URL.
    
    Returns: (text, error_message)
    """
    if not HAS_TRAFILATURA:
        return None, "Trafilatura not installed"
    
    try:
        # Validate URL
        is_safe, reason = await is_safe_url(url)
        if not is_safe:
            return None, f"URL unsafe: {reason}"
        
        # Fetch article
        client = httpx.AsyncClient(timeout=timeout)
        try:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
        finally:
            await client.aclose()
        
        # Check size
        if len(response.content) > DEFAULT_MAX_ARTICLE_SIZE:
            return None, f"Article exceeds size limit"
        
        # Extract text in thread to avoid blocking
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(
            None,
            trafilatura.extract,
            response.text,
            trafilatura.extract_metadata,
            {"include_tables": True},
        )
        
        if not text:
            return None, "No text extracted from article"
        
        return text[:8000], None  # Limit extracted text to 8k chars
    except httpx.HTTPError as e:
        if isinstance(e, httpx.HTTPStatusError):
            if e.response.status_code == 403:
                return None, "Article access denied (403)"
            elif e.response.status_code == 429:
                return None, "Server rate limited (429)"
        return None, f"HTTP error: {type(e).__name__}"
    except asyncio.TimeoutError:
        return None, "Article fetch timeout"
    except Exception as e:
        logger.exception("Article extraction error for %s", url)
        return None, f"Extraction error: {type(e).__name__}"


async def get_article_content(
    url: str,
    fallback_excerpt: str,
    timeout: int = DEFAULT_EXTRACT_TIMEOUT,
) -> tuple[str, str]:
    """
    Get article content, falling back to excerpt if extraction fails.
    
    Returns: (content_text, origin)  # origin: 'full_text', 'excerpt'
    """
    extracted_text, error = await extract_article_text(url, timeout)
    
    if extracted_text:
        logger.info("Extracted full text from %s", url)
        return extracted_text, "full_text"
    
    logger.info("Using excerpt for %s: %s", url, error)
    return fallback_excerpt, "excerpt"
