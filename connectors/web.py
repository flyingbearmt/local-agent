import re
from urllib.parse import urlparse
from typing import Optional

import requests
from bs4 import BeautifulSoup


def read_web_page(url: str) -> str:
    """
    Fetch and extract text content from a web page.
    
    Args:
        url: The URL to fetch
        
    Returns:
        The extracted text content
        
    Raises:
        ValueError: If URL is invalid or content cannot be fetched
    """
    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    
    # Set headers to mimic a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Fetch the page
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Extract text
        text = soup.get_text()
        
        # Clean up text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Add metadata
        title = soup.find('title')
        title_text = title.get_text().strip() if title else url
        
        # Format with metadata
        formatted_text = f"Source: {url}\nTitle: {title_text}\n\n{text}"
        
        return formatted_text
        
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch URL: {e}")
    except Exception as e:
        raise ValueError(f"Error parsing content: {e}")


def read_raw_text_url(url: str) -> str:
    """
    Fetch raw text content from URLs (e.g., GitHub raw files, plain text APIs).
    
    Args:
        url: The URL to fetch
        
    Returns:
        The raw text content
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Try to detect encoding
        response.encoding = response.apparent_encoding
        
        return response.text
        
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch URL: {e}")


def is_github_raw_url(url: str) -> bool:
    """Check if URL is a GitHub raw file URL."""
    return bool(re.match(r'https://raw\.githubusercontent\.com/', url))


def is_github_url(url: str) -> bool:
    """Check if URL is a GitHub file URL (not raw)."""
    return bool(re.match(r'https://github\.com/[^/]+/[^/]+/blob/', url))


def convert_github_to_raw(url: str) -> str:
    """Convert GitHub file URL to raw URL."""
    return url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')


def read_url(url: str) -> str:
    """
    Unified function to read content from various URL types.
    
    Args:
        url: The URL to read
        
    Returns:
        The text content
    """
    # Handle GitHub URLs
    if is_github_url(url):
        url = convert_github_to_raw(url)
        return read_raw_text_url(url)
    
    # Handle raw text URLs
    if is_github_raw_url(url) or url.endswith(('.txt', '.md', '.py', '.js', '.json', '.yaml', '.yml', '.csv', '.rst')):
        return read_raw_text_url(url)
    
    # Handle HTML pages
    if any(scheme in url.lower() for scheme in ['http://', 'https://']):
        return read_web_page(url)
    
    raise ValueError(f"Unsupported URL format: {url}")
