import requests
import time
import logging
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)


class InstagramAPIError(Exception):
    """Custom exception for Instagram API errors"""
    pass


class InstagramAPI:
    """
    Service for posting to Instagram via Graph API v24.0
    
    This implementation supports both authentication methods:
    - Facebook Login for Business: uses graph.facebook.com
    - Business Login for Instagram: uses graph.instagram.com
    
    For most use cases with Facebook-linked Instagram accounts,
    graph.facebook.com is the recommended host.
    
    Reference: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/
    """
    
    def __init__(self, use_instagram_host: bool = False):
        """
        Initialize Instagram API client
        
        Args:
            use_instagram_host: If True, uses graph.instagram.com (Business Login for Instagram)
                              If False, uses graph.facebook.com (Facebook Login for Business)
                              Default is False for Facebook-linked accounts
        """
        self.user_id = settings.instagram_user_id
        self.access_token = settings.instagram_access_token
        
        # API version - using latest stable version
        self.api_version = "v24.0"
        
        # Choose host based on authentication method
        if use_instagram_host:
            self.base_url = f"https://graph.instagram.com/{self.api_version}"
        else:
            self.base_url = f"https://graph.facebook.com/{self.api_version}"
        
        # Separate host for video uploads (Reels)
        self.upload_url = f"https://rupload.facebook.com/ig-api-upload/{self.api_version}"
    
    def _check_credentials(self):
        """Check if Instagram credentials are configured"""
        if not self.user_id or not self.access_token:
            raise InstagramAPIError(
                "Instagram credentials not configured. "
                "Please set INSTAGRAM_USER_ID and INSTAGRAM_ACCESS_TOKEN in .env file. "
                "See README.md for setup instructions."
            )
    
    def _make_request(
        self, 
        method: str, 
        url: str, 
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with error handling
        
        Args:
            method: HTTP method (GET, POST)
            url: Full URL
            params: Query parameters
            data: Request body data
            headers: Request headers
            
        Returns:
            JSON response
            
        Raises:
            InstagramAPIError: If request fails
        """
        try:
            print(f'method={method}  url={url}  params={params}  json=data  headers={headers}')
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=data,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"Instagram API HTTP error: {error_msg}")
            
            # Parse error response if available
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_detail = error_data['error'].get('message', error_msg)
                    error_type = error_data['error'].get('type', 'Unknown')
                    error_msg = f"{error_type}: {error_detail}"
            except:
                pass
            
            raise InstagramAPIError(error_msg)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Instagram API request error: {str(e)}")
            raise InstagramAPIError(f"Request failed: {str(e)}")
    
    def post_image(self, image_path: str, caption: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Post an image to Instagram using the two-step process:
        1. Create media container
        2. Publish the container
        
        Args:
            image_path: Path to the image file (must be publicly accessible URL in production)
            caption: Caption for the post
            max_retries: Maximum number of retry attempts
            
        Returns:
            Dictionary with post information including media_id
            
        Raises:
            InstagramAPIError: If posting fails
            
        Note:
            In production, image_path should be a publicly accessible URL (e.g., S3, CDN).
            Instagram's API requires the image to be accessible via HTTP/HTTPS.
        """
        self._check_credentials()
        
        logger.info(f"Starting Instagram post process for user {self.user_id}")
        
        # Step 1: Create media container
        container_id = self._create_media_container(image_path, caption, max_retries)
        
        # Small delay to ensure container is ready
        time.sleep(2)
        
        # Step 2: Publish the container
        media_id = self._publish_media(container_id, max_retries)
        
        logger.info(f"Successfully posted to Instagram. Media ID: {media_id}")
        
        return {
            "container_id": container_id,
            "media_id": media_id,
            "success": True
        }
    
    def _create_media_container(
        self, 
        image_path: str, 
        caption: str, 
        max_retries: int
    ) -> str:
        """
        Create a media container (Step 1 of posting)
        
        Endpoint: POST /{ig-user-id}/media
        Reference: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media
        
        Args:
            image_path: URL to the image (must be publicly accessible)
            caption: Post caption
            max_retries: Maximum retry attempts
            
        Returns:
            Container ID (ig_container_id)
        """
        url = f"{self.base_url}/{self.user_id}/media"
        
        # For image publishing, the API expects the public image URL and caption.
        # media_type is not required here and can cause the request to be rejected.
        body = {
            "image_url": image_path,
            "caption": caption,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Creating media container (attempt {attempt + 1}/{max_retries})")
                data = self._make_request("POST", url, data=body, headers=headers)
                
                container_id = data.get("id")
                if not container_id:
                    raise InstagramAPIError("No container ID returned from API")
                
                logger.info(f"Created media container: {container_id}")
                return container_id
                
            except InstagramAPIError as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                
                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise InstagramAPIError(f"Failed to create media container after {max_retries} attempts: {str(e)}")
    
    def _publish_media(self, container_id: str, max_retries: int) -> str:
        """
        Publish a media container (Step 2 of posting)
        
        Endpoint: POST /{ig-user-id}/media_publish
        Reference: https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/content-publishing
        
        Args:
            container_id: ID of the media container from step 1
            max_retries: Maximum retry attempts
            
        Returns:
            Media ID (ig_media_id) of the published post
        """
        url = f"{self.base_url}/{self.user_id}/media_publish"
        
        params = {
            "creation_id": container_id,
            "access_token": self.access_token
        }
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Publishing media container (attempt {attempt + 1}/{max_retries})")
                
                data = self._make_request("POST", url, params=params)
                
                media_id = data.get("id")
                if not media_id:
                    raise InstagramAPIError("No media ID returned from API")
                
                logger.info(f"Published media successfully: {media_id}")
                return media_id
                
            except InstagramAPIError as e:
                error_msg = str(e)
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {error_msg}")
                
                # Check if container is still processing
                if "not ready" in error_msg.lower() or "processing" in error_msg.lower():
                    if attempt < max_retries - 1:
                        wait_time = 5 * (attempt + 1)  # Longer wait for processing
                        logger.info(f"Container still processing. Waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    raise InstagramAPIError(f"Failed to publish media after {max_retries} attempts: {error_msg}")
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get Instagram account information (useful for testing credentials)
        
        Endpoint: GET /{ig-user-id}
        
        Returns:
            Account information including username, account_type, media_count
            
        Raises:
            InstagramAPIError: If request fails
        """
        self._check_credentials()
        
        url = f"{self.base_url}/{self.user_id}"
        params = {
            "fields": "username,account_type,media_count",
            "access_token": self.access_token
        }
        
        try:
            data = self._make_request("GET", url, params=params)
            logger.info(f"Retrieved account info for @{data.get('username')}")
            return data
        except InstagramAPIError as e:
            raise InstagramAPIError(f"Failed to get account info: {str(e)}")


# Singleton instance - uses Facebook Login (graph.facebook.com) by default
# instagram_api = InstagramAPI(use_instagram_host=False)

# Alternative instance for Business Login for Instagram (graph.instagram.com)
# Uncomment if using direct Instagram authentication:
instagram_api = InstagramAPI(use_instagram_host=True)
