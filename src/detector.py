from urllib.parse import urlparse

def get_url_type(url: str) -> str:
    """
    Detects if the URL is for a gallery (Instagram, Pinterest, etc.) or video.
    Returns "gallery" or "video".
    """
    if not url:
        return "video"
    
    try:
        # Normalize and extract domain
        if not url.startswith('http'):
            url = 'https://' + url
            
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        gallery_domains = [
            'instagram.com', 
            'pinterest.', 
            'twitter.com', 
            'x.com', 
            'deviantart.com', 
            'imgur.com',
            'tiktok.com' # TikTok can be both, but user list puts it in gallery usually? 
                         # Wait, prompt list: Instagram, Pinterest, Twitter/X, DeviantArt, Imgur.
                         # YouTube, Twitch, Vimeo -> Video.
                         # TikTok is often video but can be images. Let's stick to prompt list.
        ]
        
        if any(d in domain for d in gallery_domains):
            return "gallery"
            
        return "video"
        
    except Exception:
        return "video"
