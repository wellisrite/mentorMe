# from bs4 import BeautifulSoup
# import aiohttp
import logging

logger = logging.getLogger(__name__)

async def extract_linkedin_profile(url: str) -> str:
    """
    IMPORTANT NOTE: This is a stub - LinkedIn scraping is not recommended for V1
    because:
    1. It violates LinkedIn's Terms of Service
    2. Requires handling anti-scraping measures
    3. Brittle to HTML changes
    4. May get IP blocked
    
    Better V2 solutions:
    1. Use LinkedIn's official API with OAuth
    2. Ask users to upload CV text directly
    3. Partner with LinkedIn for proper integration
    """
    logger.warning("LinkedIn scraping not implemented - use CV text instead")
    raise NotImplementedError(
        "LinkedIn scraping is not supported. Please provide CV text directly."
    )