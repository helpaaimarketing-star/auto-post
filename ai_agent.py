"""AI/ML model handler — OpenRouter dual-model content generation and analysis."""

import json
import logging
import requests
from typing import Dict, Any, Optional
from config import Config
from processing.rule_engine import RuleEngine

logger = logging.getLogger("AIAgent")


class AIAgent:
    """Processes data through Groq (general utilities) and OpenRouter (social post generation)."""

    GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self):
        self.groq_headers = {
            "Authorization": f"Bearer {Config.GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        self.openrouter_headers = {
            "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/smma-bot",
            "X-Title": "SMMA Bot System",
        }
        self.rules = RuleEngine()

    def _call(self, system: str, user: str, temperature: float = 0.7, provider: str = "groq", model: str = None, max_tokens: int = 2000) -> str:
        """Call either Groq or OpenRouter API.
        
        provider='groq'       -> Uses GROQ_API_KEY with Config.GROQ_MODEL
        provider='openrouter' -> Uses OPENROUTER_API_KEY with the specified model
        """
        if provider == "openrouter":
            url = self.OPENROUTER_URL
            headers = self.openrouter_headers
            selected_model = model or Config.OPENROUTER_MODEL_SOCIAL
        else:
            url = self.GROQ_URL
            headers = self.groq_headers
            selected_model = Config.GROQ_MODEL

        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=40)
            if res.status_code != 200:
                logger.error(f"{provider.upper()} error {res.status_code} [{selected_model}]: {res.text[:300]}")
                return ""
            return res.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"{provider.upper()} call failed [{selected_model}]: {e}")
            return ""

    def _call_json(self, system: str, user: str, provider: str = "groq", model: str = None, max_tokens: int = 2000) -> Optional[Any]:
        system += "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation, no backticks."
        raw = self._call(system, user, temperature=0.3, provider=provider, model=model, max_tokens=max_tokens)
        try:
            clean = raw.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0].strip()
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0].strip()
                
            # Extra robust extraction for random AI conversation text
            start_list = clean.find('[')
            start_dict = clean.find('{')
            
            if start_list != -1 and start_dict != -1:
                start = min(start_list, start_dict)
            elif start_list != -1:
                start = start_list
            else:
                start = start_dict
                
            if start != -1:
                end_list = clean.rfind(']')
                end_dict = clean.rfind('}')
                end = max(end_list, end_dict)
                if end != -1:
                    clean = clean[start:end+1]
                    
            return json.loads(clean)
        except Exception as e:
            logger.error(f"JSON parse failed: {e} | Raw: {raw[:200]}")
            return None

    def generate_cold_email(self, business_name: str, niche: str, city: str,
                             country: str, weak_points: list, website: str,
                             pricing: Dict) -> Dict[str, str]:
        weak_str = "\n".join(f"- {w}" for w in weak_points[:3])
        system = """You are an expert cold email copywriter for a social media marketing agency.
Rules:
- Sound like a real human, not a salesperson
- Never mention prices in the email body
- Be specific about THEIR business weaknesses
- Max 120 words in the body
- Subject line: under 50 chars, curiosity-driven, no clickbait
- One CTA only: ask if they want to see a sample post for their industry
- Output valid JSON with keys: subject, body, preview_text"""

        user = f"""Write a cold outreach email for:
Business: {business_name}
Industry: {niche}
Location: {city}, {country}
Website: {website or "No website"}
Social Media Problems:
{weak_str}

Make them curious about ONE sample post we made for their niche."""

        result = self._call_json(system, user, provider="groq")
        if not result:
            return {
                "subject": f"Quick thought about {business_name}",
                "body": (
                    f"Hi,\n\nI came across {business_name} and noticed your social media "
                    f"could use some attention — specifically {weak_points[0] if weak_points else 'your posting consistency'}.\n\n"
                    f"I've put together a sample post for {niche} businesses in {city}. "
                    f"Would it be okay if I sent it over?\n\nBest regards"
                ),
                "preview_text": f"I made something for {business_name}",
            }
        return result

    def generate_discord_pitch(self, business_name: str, niche: str, city: str,
                                country: str, weak_points: list,
                                profiles: Dict, pricing: Dict) -> str:
        weak_str = "\n".join(f"• {w}" for w in weak_points[:4])
        profile_str = "\n".join(f"• {k.capitalize()}: {v}" for k, v in profiles.items()) \
                      or "• No social profiles found"
        starter = pricing.get("starter", 299)
        growth = pricing.get("growth", 599)

        system = """You are a confident sales consultant writing a direct outreach message.
Write a concise pitch (max 200 words) that:
- Highlights their specific social media weaknesses
- Positions the agency as the solution
- Mentions a natural price range
- Ends with a clear next step
- Uses bullet points for readability"""

        user = f"""Business: {business_name}
Niche: {niche} | Location: {city}, {country}
Social Profiles Found:
{profile_str}
Weaknesses Found:
{weak_str}
Suggested Pricing: ${starter} – ${growth}/month

Write the outreach pitch."""

        return self._call(system, user, provider="groq")

    def generate_social_post(self, business_name: str, niche: str, city: str,
                              order_id: str, platform: str = "instagram") -> Dict[str, str]:
        system = f"""You are a professional social media content creator specialising in {niche} businesses.
Create a high-engagement post for {platform} that:
- Uses a proven viral hook in the first line
- Feels authentic, local, not corporate
- Drives foot traffic or enquiries
- Has strong engagement triggers (questions, CTAs, relatable content)

Return ONLY valid JSON with keys:
- caption (main post text, 150-200 words, use emojis naturally)
- hashtags (30 relevant hashtags as a single string, space-separated)
- description (Google Business / YouTube description, 80-100 words)
- image_prompt (detailed Midjourney/DALL-E prompt describing the perfect image)
- cta (one punchy call-to-action line)
- best_time_to_post (e.g. "Tuesday 6–8 PM local time")
- estimated_reach (e.g. "500–2,000 organic reach")
- tags (5 relevant keyword tags as a list)"""

        user = f"""Create an engaging {platform} post for:
Business: {business_name}
Industry: {niche}
Location: {city}
Order: {order_id}

Make it feel local, authentic, and designed to get saves and shares."""

        # Determine OpenRouter model based on platform
        plat_lower = platform.lower()
        if plat_lower in ["linkedin", "b2b", "threads"]:
            model = Config.OPENROUTER_MODEL_B2B
        else:
            model = Config.OPENROUTER_MODEL_SOCIAL

        result = self._call_json(system, user, provider="openrouter", model=model)
        if not result:
            return {
                "caption": (
                    f"✨ {business_name} — your local {niche} destination in {city}!\n\n"
                    f"We're passionate about serving our community. Come visit us today! 📍 {city}"
                ),
                "hashtags": f"#{niche.replace(' ', '')} #{city.replace(' ', '')} #local #smallbusiness",
                "description": f"{business_name} is a top-rated {niche} business in {city}.",
                "image_prompt": f"Professional photo of a {niche} business in {city}, warm lighting, welcoming",
                "cta": "Book your appointment today!",
                "best_time_to_post": "Tuesday–Thursday, 6–8 PM",
                "estimated_reach": "300–1,500 organic reach",
                "tags": [niche, city, "local business", "social media", "marketing"],
            }
        return result

    def suggest_pricing(self, niche: str, weak_points: list, country: str) -> Dict:
        return self.rules.suggest_pricing(niche, weak_points, country)

    def generate_dm_script(self, business_name: str, niche: str, city: str,
                            country: str, weak_points: list, pricing: Dict,
                            sale_hooks: list = None, profiles: Dict = None) -> str:
        """
        Generate a hyper-personalised DM based on each lead's SPECIFIC problems.
        - Mentions the EXACT platform that is weak
        - Quotes approximate follower/engagement data found
        - Offers a specific service as the fix
        - Short (80-100 words), casual, human-sounding
        """
        sale_hooks = sale_hooks or []
        profiles = profiles or {}

        # Build rich context for the AI
        problems_str = "\n".join(f"- {w}" for w in weak_points[:3]) if weak_points else "- Inconsistent posting"
        hooks_str = "\n".join(f"- {h}" for h in sale_hooks[:2]) if sale_hooks else ""
        profile_str = ", ".join(profiles.keys()) if profiles else "unknown platforms"
        starter = pricing.get("starter", 299)
        symbol = pricing.get("symbol", "$")

        system = """You are a top SMMA closer writing a short, casual DM for Instagram or TikTok.
Rules:
- Max 100 words. Short DMs get READ. Long ones get ignored.
- Start with something genuine you noticed — mention a SPECIFIC platform (Instagram, TikTok, etc.)
- Mention ONE concrete problem (e.g. low followers, inactive account, missing platform)
- Position our service as the solution in ONE sentence
- End with a soft question like "Want me to send over a free sample post for your niche?"
- Casual tone, no corporate speak, no hashtags
- Sound like a real person, not a bot or template
- Do NOT mention price in the DM"""

        user = f"""Write a personalised DM for:
Name/Brand: {business_name}
Niche: {niche}
Platforms they are ON: {profile_str or 'none found'}

Specific problems found:
{problems_str}

What we can offer them:
{hooks_str or 'Social media growth and content creation'}

Write a natural, short DM that feels like it was written specifically for them."""

        result = self._call(system, user, temperature=0.85, provider="groq")
        if not result:
            # Fallback using the most specific problem we have
            main_problem = weak_points[0] if weak_points else "your social media presence could use some attention"
            main_hook = sale_hooks[0] if sale_hooks else "grow your online presence"
            return (
                f"Hey {business_name}! 👋\n\n"
                f"I was checking out your profile and noticed — {main_problem.lower()}.\n\n"
                f"{main_hook}. I actually put together a free sample post for {niche} brands — "
                f"want me to send it over? No strings attached 🙌"
            )
        return result

    def generate_report_summary(self, title: str, niche: str, city: str, country: str,
                                lead_count: int, avg_score: float, top_weak_points: list) -> str:
        weak_str = "\n".join(f"- {name}: {count} leads" for name, count in top_weak_points)
        system = """You are a master business consultant and agency growth strategist.
Write a professional, highly actionable AI Executive Summary (max 180 words) based on the aggregated lead weakness report.
- Identify the single biggest opportunity area for outreach.
- Provide 2 concrete suggestions on how the agency should position its services (e.g. Starter vs Growth package pitching).
- Keep it highly professional, insightful, and motivating.
- Do NOT use markdown code blocks or placeholders."""

        user = f"""Report Title: {title}
Niche: {niche} | Location: {city}, {country}
Total Leads Analyzed: {lead_count}
Average Weakness Score: {avg_score}/10
Top Weakness Statistics:
{weak_str}"""

        return self._call(system, user, provider="groq")
        
    def analyze_post_quality(self, business_name: str, niche: str, weak_points: list, existing_posts_summary: str = "") -> str:
        """Analyze why the business's current posts are not working."""
        system = """You are a top-tier Social Media Marketing Expert.
Based on the provided weak points, niche, and (if available) the actual existing posts,
explain WHY their current social media strategy is failing.
Direct, professional, actionable. Frame it as a mini-audit.
If real posts are provided, reference SPECIFIC patterns you see (caption style, hashtag overuse, content type gaps, etc.).
Keep it under 150 words."""

        posts_section = f"\n\nReal Posts Analyzed:\n{existing_posts_summary}" if existing_posts_summary else ""

        user = f"""Business: {business_name}
Niche: {niche}
Problems Found: {", ".join(weak_points) if weak_points else 'General low engagement'}{posts_section}

Write a short, punchy analysis of what they are doing wrong based on their ACTUAL posts (if provided) and why it's hurting their growth."""
        
        return self._call(system, user, provider="groq") or "Your current social media presence lacks consistency and value-driven content, resulting in low engagement and missed leads."

    def generate_improved_posts(self, business_name: str, niche: str, weak_points: list, platform: str = "instagram", count: int = 5, context: dict = None) -> list:
        """Generate N improved post templates referencing the brand's actual existing posts."""
        context = context or {}
        context_str = f"Website Title: {context.get('title', 'N/A')}\nWebsite Description: {context.get('description', 'N/A')}"
        
        # Inject real scraped posts if available
        posts_summary = context.get("existing_posts_summary", "")
        has_real_posts = context.get("has_real_posts", False)
        trending_info = context.get("trending_info", "")
        
        if has_real_posts and posts_summary:
            reference_instruction = f"""
=== REAL POSTS FROM THIS EXACT INSTAGRAM PROFILE ===
{posts_summary}

STRICT RULES — READ CAREFULLY:
1. Study the actual captions above. Copy their EXACT tone, energy, language, and emoji style.
2. If they sell specific products/services, NAME those in your posts — do not invent new ones.
3. Use the SAME types of hashtags they already use (niche + brand specific).
4. Match their caption LENGTH — if their real posts are short punchy, yours must be too.
5. Your new posts must feel like they came from the SAME person who wrote those captions.
6. Make the new posts BETTER (stronger CTA, more value) but never change the brand voice.

BANNED (will result in rejection):
- Inventing product names that aren't in their real posts
- Generic phrases: "Welcome to our world", "Step into our journey", "Behind the scenes of our story"
- Mismatching tone (writing formal when they're casual, or vice versa)"""
        else:
            reference_instruction = f"""
NOTE: Could not scrape posts for this profile (private/blocked).
You must STILL write highly specific, commercial posts for a {niche} brand.
Rules:
- Invent 2-3 SPECIFIC product/service names that make sense for this niche
- Write in an authentic brand voice (not corporate fluff)
- Every post must have a clear offer, CTA, or value
BANNED: "Welcome to our world", "Behind the scenes", "Step into our journey", "We believe in", "Our story"."""

        system = f"""You are an elite Social Media Manager for top-tier brands.
You MUST return the output as a valid JSON array of objects.
{reference_instruction}

For each post, select one of these File Types:
- PNG: for text, vectors, graphics
- JPEG: for Photos
- MP4: for animated/video content

And select one of these Post Styles:
- vector/illustration: flat designs, clean UI, no cartoons
- minimalist/clean: simple design, clear background, premium brands
- typography: beautiful fonts, quotes, alerts, announcement
- infographics: step-by-step guides, facts, data designing
- Photomontage / Manipulation: photo mixing, creating new scenes
- Carousel (Multi-slide): 3-10 swiping slides of high value
- 3D / AI Art: hyper-realistic 3D objects, premium aesthetic (NO cartoons)

CRITICAL RULES:
1. NEVER use placeholders. Write the ACTUAL, realistic copy/text.
2. The "caption" must be 100% complete, highly specific, engaging, matching the brand's voice.
3. For 'typography', 'vector/illustration', or 'infographics': The "image_prompt" must include the EXACT text on the graphic.
4. For 'Carousel (Multi-slide)': The "image_prompt" must write out EXACT text for each slide.
5. NO CARTOONS, NO GENERIC TROPES. Every concept must be highly professional and commercial.
6. Each post must feel like it belongs to THIS brand — not a generic template.

Each object in the JSON array must have exactly these keys:
- "style" (string: one of the 7 Post Styles listed above)
- "file_type" (string: PNG, JPEG, or MP4)
- "caption" (string: Full ready-to-post caption with emojis, matching brand tone)
- "hashtags" (string: 15-20 relevant hashtags)
- "image_prompt" (string: Detailed visual description AND exact copy/text on the image/slides)
- "best_time" (string: Suggested posting time)
- "why_better" (string: 1-2 sentences explaining WHY this beats their current approach)
- "expected_improvement" (string: e.g. '+40% engagement')"""

        user = f"""Business: {business_name}
Niche: {niche}
Platform: {platform}
Current Problems: {", ".join(weak_points) if weak_points else 'Low engagement'}
{context_str}

Generate {count} different post templates. Use a variety of File Types and Post Styles (do not repeat the same style/file type). Each post must feel authentic to THIS brand based on their existing content style.{(" Use these trending topics as inspiration where relevant: " + trending_info) if trending_info else ""}"""

        plat_lower = platform.lower()
        if plat_lower in ["linkedin", "b2b", "threads"]:
            or_model = Config.OPENROUTER_MODEL_B2B
        else:
            or_model = Config.OPENROUTER_MODEL_SOCIAL

        # Try 1: OpenRouter (better creative quality)
        result = None
        if Config.OPENROUTER_API_KEY:
            result = self._call_json(system, user, provider="openrouter", model=or_model, max_tokens=4000)

        # Try 2: Groq fallback (always available, fast)
        if not isinstance(result, list) or len(result) == 0:
            logger.warning("OpenRouter failed or returned bad JSON — retrying with Groq...")
            result = self._call_json(system, user, provider="groq", max_tokens=4000)

        if isinstance(result, list) and len(result) > 0:
            return result

        logger.error("Both OpenRouter and Groq failed to generate posts — returning hardcoded fallback")
        return [{
            "style": "infographics",
            "file_type": "PNG",
            "caption": f"Are you making these marketing mistakes with your {niche} business? 🛑 Let's fix them today! Here is our step-by-step blueprint to double your outreach results. Save this for later! 💡",
            "hashtags": f"#{niche.replace(' ', '')} #tips #growth #smma",
            "image_prompt": f"Title: 3 Common mistakes in {niche}. Step 1: No call to action. Step 2: No links. Step 3: Low content density.",
            "best_time": "Tuesday 6 PM",
            "why_better": "Provides upfront value instead of just selling, which drives saves and shares.",
            "expected_improvement": "+50% reach"
        }] * count

    def detect_niche(self, text: str, url: str = "") -> str:
        """Detect the business niche from website text or URL."""
        system = "You are a business classifier. Classify the business niche from the text or the URL in 1-2 words (e.g. Fitness, Real Estate, SaaS, Clothing, Web Design, Musician). Return ONLY the niche name. If the text is empty or generic, use the URL to guess the niche."
        user = f"URL: {url}\nWebsite Text: {text[:1000]}"
        return self._call(system, user, provider="groq") or "General"

    def generate_call_script(self, business_name: str, niche: str, weak_points: list, pricing: Dict, competitor_intel: str = "") -> str:
        """Generate a professional sales call script like a senior expert."""
        weak_str = "\n".join(f"- {w}" for w in weak_points[:5]) if weak_points else "- Inconsistent social media presence"
        starter = pricing.get("starter", 299)
        growth = pricing.get("growth", 599)
        symbol = pricing.get("symbol", "$")

        system = """You are the world's #1 SMMA sales closer with 15+ years of experience. 
Write a COMPLETE phone/video call script for closing a social media marketing deal.

The script MUST have these sections in order:
1. HOOK (first 10 seconds — grab attention, mention something specific about THEIR business)
2. BRIEF ISSUES (30 seconds — summarize 2-3 specific problems you found on their social media)
3. PITCH (30 seconds — position your agency as the solution, mention 1 case study result)
4. HOW WE FIX (45 seconds — step-by-step what you'll do for them: audit, strategy, content calendar, posting)
5. COMPETITOR INTEL (15 seconds — mention what their competitors are doing better on social media)
6. CLOSE (15 seconds — create urgency, offer a free trial post, ask for commitment)

Rules:
- Sound like a confident expert giving advice, NOT a desperate salesperson
- Use their business name and niche naturally
- Include specific numbers and results (e.g. '3x engagement in 60 days')
- The person reading this should feel compelled to reply and close the deal
- Chances of closing should be at least 60%
- Write the ACTUAL words to say, not instructions
- Keep total script under 350 words
- Add [PAUSE] markers where the caller should pause for response"""

        user = f"""Write a closing call script for:
Business: {business_name}
Niche: {niche}
Problems Found:
{weak_str}
Suggested Pricing: {symbol}{starter} – {symbol}{growth}/month
Competitor Info: {competitor_intel or 'Their competitors are more active on Instagram and TikTok with better engagement'}

Write the full script now."""

        result = self._call(system, user, temperature=0.8, provider="groq")
        if not result:
            return (
                f"📞 CALL SCRIPT — {business_name}\n\n"
                f"🪝 HOOK:\n"
                f"\"Hey! I was looking at {business_name}'s social media and I noticed something interesting...\"\n[PAUSE]\n\n"
                f"⚠️ ISSUES:\n"
                f"\"So here's what I found — {weak_points[0] if weak_points else 'your posting is inconsistent'}. "
                f"That's actually costing you potential customers every single day.\"\n[PAUSE]\n\n"
                f"💡 PITCH:\n"
                f"\"We specialize in {niche} businesses and we've helped similar brands 3x their engagement in 60 days.\"\n[PAUSE]\n\n"
                f"🔧 HOW WE FIX:\n"
                f"\"Here's what we do — full audit, custom strategy, content calendar, and we handle ALL the posting. You focus on your business.\"\n[PAUSE]\n\n"
                f"🏆 COMPETITOR INTEL:\n"
                f"\"Your competitors are already doing this. They're posting 4-5x a week with high engagement.\"\n[PAUSE]\n\n"
                f"🎯 CLOSE:\n"
                f"\"Tell you what — let me create ONE free sample post for {business_name}. If you love it, we start at {symbol}{starter}/month. Fair enough?\"\n"
            )
        return result

__all__ = ["AIAgent"]
