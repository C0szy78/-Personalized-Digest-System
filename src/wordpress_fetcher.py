"""WordPress API fetcher and web scraper for content extraction."""
import requests
from requests.auth import HTTPBasicAuth
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime
from logger_utils import log


class WordPressFetcher:
    """Fetcher for WordPress posts via REST API."""

    def __init__(self, wordpress_url: str, username: str = None, app_password: str = None):
        """
        Initialize WordPress fetcher.

        Args:
            wordpress_url: Base URL of WordPress site (e.g., https://domain1.badev.tools)
            username: WordPress username (optional, for authenticated requests)
            app_password: WordPress Application Password (optional, for authenticated requests)
        """
        self.base_url = wordpress_url.rstrip('/')
        self.api_url = f"{self.base_url}/wp-json/wp/v2/posts"
        self.username = username
        self.app_password = app_password

        # Set up authentication if credentials provided
        self.auth = None
        if username and app_password:
            self.auth = HTTPBasicAuth(username, app_password)
    
    def get_posts(self, per_page: int = 10, page: int = 1) -> List[Dict]:
        """
        Fetch posts from WordPress REST API.
        
        Args:
            per_page: Number of posts to fetch per page
            page: Page number
            
        Returns:
            List of post dictionaries with title, date, link, excerpt
        """
        try:
            params = {
                'per_page': per_page,
                'page': page,
                '_embed': True  # Include embedded data like featured images
            }
            
            response = requests.get(self.api_url, params=params, auth=self.auth, timeout=10)
            
            if not response.ok:
                raise Exception(f"Error: {response.status_code}")
            
            posts = response.json()
            
            # Extract relevant information
            processed_posts = []
            for post in posts:
                processed_posts.append({
                    'id': post.get('id'),
                    'title': post.get('title', {}).get('rendered', 'No Title'),
                    'date': post.get('date'),
                    'link': post.get('link'),
                    'excerpt': post.get('excerpt', {}).get('rendered', ''),
                    'content_html': post.get('content', {}).get('rendered', '')
                })
            
            return processed_posts
            
        except Exception as e:
            log.error(f"Could not fetch posts: {str(e)}")
            return []
    
    def scrape_post_content(self, url: str) -> Optional[str]:
        """
        Scrape clean text content from a WordPress post URL.
        
        Args:
            url: URL of the WordPress post
            
        Returns:
            Clean text content or None if failed
        """
        try:
            response = requests.get(url, auth=self.auth, timeout=10)
            
            if not response.ok:
                raise Exception(f"Error: {response.status_code}")
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Try to find the main content area
            # Common WordPress content selectors
            content = None
            
            # Try different common WordPress content selectors
            selectors = [
                'article .entry-content',
                '.post-content',
                '.article-content',
                'article',
                '.content',
                'main'
            ]
            
            for selector in selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem
                    break
            
            if not content:
                # Fallback to body
                content = soup.body
            
            if content:
                # Remove script and style tags
                for script in content(['script', 'style', 'nav', 'header', 'footer']):
                    script.decompose()
                
                # Get text and clean it
                text = content.get_text(separator='\n', strip=True)
                
                # Clean up extra whitespace
                lines = [line.strip() for line in text.split('\n')]
                lines = [line for line in lines if line]
                clean_text = '\n\n'.join(lines)
                
                return clean_text
            
            return None
            
        except Exception as e:
            log.error(f"Could not scrape content from {url}: {str(e)}")
            return None
    
    def get_posts_with_content(self, per_page: int = 10, page: int = 1) -> List[Dict]:
        """
        Fetch posts and scrape their full content.
        
        Args:
            per_page: Number of posts to fetch
            page: Page number
            
        Returns:
            List of posts with scraped content
        """
        posts = self.get_posts(per_page=per_page, page=page)

        for post in posts:
            log.debug(f"Scraping: {post['title'][:60]}...", indent=2)
            scraped_content = self.scrape_post_content(post['link'])
            
            if scraped_content:
                post['scraped_content'] = scraped_content
                post['content_length'] = len(scraped_content)
            else:
                # Fallback to HTML content if scraping fails
                soup = BeautifulSoup(post['content_html'], 'html.parser')
                post['scraped_content'] = soup.get_text(separator='\n', strip=True)
                post['content_length'] = len(post['scraped_content'])
        
        return posts