import logging
import requests
import re
import time
from bs4 import BeautifulSoup
from typing import Dict, Any, Tuple, List
from urllib.parse import urlparse

logger = logging.getLogger("LinkAnalyzer")

class LinkAnalyzer:
    """Analyzes a given URL for social profiles, contacts, tech stack, and issues."""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
    def analyze(self, url: str) -> Dict[str, Any]:
        if not url.startswith('http'):
            url = 'https://' + url
            
        result = {
            "url": url,
            "title": "",
            "description": "",
            "load_time_ms": 0,
            "is_secure": url.startswith('https'),
            "tech_stack": [],
            "social_profiles": {},
            "contacts": {"emails": set(), "phones": set(), "whatsapp": set()},
            "problems": [],
            "weakness_score": 0
        }
        
        start_time = time.time()
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            result["load_time_ms"] = int((time.time() - start_time) * 1000)
            
            if resp.status_code != 200:
                result["problems"].append(f"Website returned status code {resp.status_code}")
                return result
                
            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')
            
            # Basic Meta
            title_tag = soup.find('title')
            result["title"] = title_tag.text.strip() if title_tag else ""
            
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            if desc_tag:
                result["description"] = desc_tag.get('content', '').strip()
            else:
                result["problems"].append("Missing meta description")
                
            # SPECIAL HANDLING FOR SOCIAL MEDIA LINKS
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            if "instagram.com" in domain or "tiktok.com" in domain or "twitter.com" in domain or "x.com" in domain:
                path_parts = [p for p in parsed_url.path.split('/') if p]
                if path_parts:
                    username = path_parts[0].replace('@', '')

                    # Try to extract a real brand name from OG/meta tags before falling back
                    og_title = soup.find('meta', property='og:title')
                    og_desc = soup.find('meta', property='og:description')

                    real_title = og_title.get('content', '').strip() if og_title else ''
                    real_desc = og_desc.get('content', '').strip() if og_desc else ''

                    # Filter out Instagram/TikTok generic login prompts
                    _generic_phrases = ('log in', 'sign up', 'create account', 'join instagram', 'join tiktok')
                    if real_title and not any(g in real_title.lower() for g in _generic_phrases):
                        result["title"] = real_title
                    else:
                        result["title"] = f"@{username}"

                    if real_desc and not any(g in real_desc.lower() for g in _generic_phrases):
                        result["description"] = real_desc
                    else:
                        result["description"] = (
                            f"Social media brand account @{username} on {domain.split('.')[0].capitalize()}. "
                            f"Generate posts as their professional social media manager."
                        )

                    # Mark as social-only so PostGenerator knows to enrich context
                    result["problems"].append(
                        f"Bot cannot read direct {domain} posts due to privacy blocks. "
                        f"AI will generate posts based purely on the username @{username}."
                    )
                
            og_tag = soup.find('meta', property='og:image')
            if not og_tag:
                result["problems"].append("No OpenGraph image (poor social sharing)")
                
            if result["load_time_ms"] > 3000:
                result["problems"].append(f"Slow load time ({result['load_time_ms']}ms)")
                
            # Social Profiles
            self._extract_socials(html, result["social_profiles"])
            if not result["social_profiles"]:
                result["problems"].append("No social media profiles linked on website")
            elif "instagram" not in result["social_profiles"] and "tiktok" not in result["social_profiles"]:
                result["problems"].append("Missing key modern platforms (Instagram/TikTok)")
                
            # Contacts
            self._extract_contacts(html, result["contacts"])
            if not result["contacts"]["emails"] and not result["contacts"]["phones"]:
                result["problems"].append("No clear contact info (email/phone) found")
            if not result["contacts"]["whatsapp"]:
                result["problems"].append("No WhatsApp or direct chat link")
                
            # Tech Stack
            self._detect_tech_stack(html, resp.headers, result["tech_stack"])
            
            # Simple content heuristic
            if len(html) < 2000:
                result["problems"].append("Very thin content / empty page")
                
            # Calculate score (out of 10)
            base_score = min(len(result["problems"]), 10)
            result["weakness_score"] = base_score
            
        except requests.RequestException as e:
            result["problems"].append(f"Failed to access website: {str(e)}")
            result["weakness_score"] = 10
            
        # Convert sets to lists for JSON serialization downstream if needed
        result["contacts"]["emails"] = list(result["contacts"]["emails"])
        result["contacts"]["phones"] = list(result["contacts"]["phones"])
        result["contacts"]["whatsapp"] = list(result["contacts"]["whatsapp"])
            
        return result
        
    def _extract_socials(self, html: str, profiles: Dict[str, str]):
        platforms = {
            "instagram": r"https?://(?:www\.)?instagram\.com/[^/\"'\s]+",
            "facebook": r"https?://(?:www\.)?facebook\.com/[^/\"'\s]+",
            "tiktok": r"https?://(?:www\.)?tiktok\.com/@[^/\"'\s]+",
            "linkedin": r"https?://(?:www\.)?linkedin\.com/company/[^/\"'\s]+",
            "twitter": r"https?://(?:www\.)?(?:twitter|x)\.com/[^/\"'\s]+",
            "youtube": r"https?://(?:www\.)?youtube\.com/(?:c/|channel/|@)[^/\"'\s]+"
        }
        
        for platform, pattern in platforms.items():
            match = re.search(pattern, html)
            if match:
                url = match.group(0).rstrip('"\'>')
                if "wix.com" not in url and "shopify.com" not in url: # Exclude generic template links
                    profiles[platform] = url
                    
    def _extract_contacts(self, html: str, contacts: Dict[str, set]):
        # Emails
        emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', html)
        # Filter out image extensions and common false positives
        valid_emails = [e for e in emails if not any(e.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '@sentry.io'])]
        contacts["emails"].update(valid_emails[:3]) # Limit to 3
        
        # WhatsApp links
        wa_links = re.findall(r'https?://wa\.me/[0-9]+', html)
        wa_links += re.findall(r'https?://api\.whatsapp\.com/send\?phone=[0-9]+', html)
        if wa_links:
            contacts["whatsapp"].add(wa_links[0])
            
    def _detect_tech_stack(self, html: str, headers: Dict[str, str], stack: List[str]):
        if 'wp-content' in html or 'WordPress' in html:
            stack.append("WordPress")
        if 'cdn.shopify.com' in html or 'Shopify.theme' in html:
            stack.append("Shopify")
        if 'wix.com' in html or 'X-Wix-' in str(headers):
            stack.append("Wix")
        if 'squarespace.com' in html:
            stack.append("Squarespace")
        if 'React' in html or 'data-reactroot' in html:
            stack.append("React")
            
__all__ = ["LinkAnalyzer"]
