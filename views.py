"""Discord UI views for the SMMA Bot — persistent buttons and embed builders."""

import asyncio
import io
import logging
from typing import Optional, Dict

import discord
import requests as _requests

from config import Config
from airtable_client import AirtableClient
from utils.helper import get_or_create_channel, lead_score_color
from ai_agent import AIAgent
from order_manager import DealManager
from email_sender import send_email
from dm_sender import DMSender

logger = logging.getLogger("DiscordViews")

LEAD_CACHE: dict = {}


def build_lead_embed(lead: dict, index: int, total: int, ai: AIAgent) -> discord.Embed:
    score = lead.get("weakness_score", 0)
    embed = discord.Embed(
        title=f"🎯 Lead #{index}/{total}: {lead['name']}",
        color=lead_score_color(score),
    )
    city_val = lead.get('city') or ''
    country_val = lead.get('country') or ''
    loc_display = ", ".join(v for v in [city_val, country_val] if v) or "Worldwide"
    embed.add_field(name="📍 Location", value=loc_display, inline=True)
    embed.add_field(name="🏷️ Niche", value=lead["niche"], inline=True)
    embed.add_field(name="⚡ Weakness Score", value=f"{score}/10", inline=True)
    if lead.get("website"):
        embed.add_field(name="🌐 Website", value=lead["website"], inline=False)
    if lead.get("email"):
        embed.add_field(name="📧 Email", value=lead["email"], inline=True)
    if lead.get("phone"):
        embed.add_field(name="📞 Phone/WA", value=lead["phone"], inline=True)
    if lead.get("snippet"):
        embed.add_field(name="📝 About", value=lead["snippet"][:300], inline=False)
    profiles = lead.get("profiles", {})
    followers = lead.get("followers", {})
    if profiles:
        prof_lines = []
        for k, v in profiles.items():
            fol = followers.get(k, 0)
            fol_str = f" ({fol:,} followers)" if fol else ""
            prof_lines.append(f"• {k.capitalize()}{fol_str}: {v}")
        embed.add_field(name="🔗 Social Profiles Found", value="\n".join(prof_lines), inline=False)
    weak_text = "\n".join(f"• {w}" for w in lead.get("weak_points", [])[:5])
    if weak_text:
        embed.add_field(name="❌ Problems Detected", value=weak_text, inline=False)
    hooks = lead.get("sale_hooks", [])
    if hooks:
        hooks_text = "\n".join(f"💡 {h}" for h in hooks[:3])
        embed.add_field(name="💰 What to Sell Them", value=hooks_text, inline=False)
    pricing = ai.suggest_pricing(lead["niche"], lead.get("weak_points", []), country_val or "United States")
    embed.add_field(
        name="💵 Suggested Price",
        value=f"{pricing['symbol']}{pricing['starter']} – {pricing['symbol']}{pricing['growth']}/mo",
        inline=True,
    )
    embed.set_footer(text=f"ID: {lead['record_id']} | Score: {score}/10")
    return embed


async def fetch_lead_from_airtable(db: AirtableClient, record_id: str) -> Optional[dict]:
    try:
        record = await asyncio.to_thread(db.get_record, "Leads", record_id)
        f = record.get("fields", {})
        weak_text = f.get("WeakPoints", "")
        profiles = {}
        issues = []
        for line in weak_text.split("\n"):
            if line.startswith("• "):
                issues.append(line.strip("• "))
            elif ": " in line and "http" in line:
                k, v = line.split(": ", 1)
                profiles[k.strip().lower()] = v.strip()
        return {
            "record_id": record_id,
            "name": f.get("Name", "Unknown"),
            "niche": f.get("Niche", ""),
            "city": f.get("City", ""),
            "country": f.get("Country", ""),
            "website": f.get("Website", ""),
            "phone": f.get("Phone", ""),
            "weak_points": issues,
            "profiles": profiles,
            "weakness_score": int(f.get("LeadScore", 0)),
            "email": f.get("Email", ""),
        }
    except Exception as e:
        logger.error(f"Airtable fetch failed for {record_id}: {e}")
        return None


class LeadActionView(discord.ui.View):
    def __init__(self, record_id: str, lead: Optional[dict] = None,
                 db: Optional[AirtableClient] = None,
                 ai: Optional[AIAgent] = None,
                 deals: Optional[DealManager] = None):
        super().__init__(timeout=None)
        self.record_id = record_id
        self.db = db or AirtableClient()
        self.ai = ai or AIAgent()
        self.deals = deals or DealManager()
        self.dm_sender = DMSender()
        if lead:
            LEAD_CACHE[record_id] = lead
        self.approve_btn.custom_id = f"approve_{record_id}"
        self.skip_btn.custom_id = f"skip_{record_id}"
        self.direct_btn.custom_id = f"direct_{record_id}"

    async def _get_lead(self) -> Optional[dict]:
        if self.record_id in LEAD_CACHE:
            return LEAD_CACHE[self.record_id]
        lead = await fetch_lead_from_airtable(self.db, self.record_id)
        if lead:
            LEAD_CACHE[self.record_id] = lead
        return lead

    @discord.ui.button(label="✅ Approve (Auto Email)", style=discord.ButtonStyle.success, custom_id="approve_placeholder")
    async def approve_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        lead = await self._get_lead()
        if not lead:
            await interaction.followup.send("❌ Lead data not found.", ephemeral=True)
            return
        name = lead["name"]
        niche = lead["niche"]
        city = lead["city"]
        country = lead["country"]
        website = lead.get("website", "")
        weak_points = lead.get("weak_points", [])
        profiles = lead.get("profiles", {})
        biz_email = lead.get("email", "")
        pricing = self.ai.suggest_pricing(niche, weak_points, country)
        if biz_email:
            await interaction.followup.send(f"⚙️ **{name}** ke liye email generate ho rahi hai…", ephemeral=True)
            email_data = await asyncio.to_thread(self.ai.generate_cold_email, name, niche, city, country, weak_points, website, pricing)
            subject = email_data.get("subject", f"Quick thought about {name}")
            body = email_data.get("body", "")
            try:
                self.db.update("Raw Dump", self.record_id, {"Status": "Approved", "EmailStatus": "Queued", "ContactMethod": "Email"})
            except Exception as e:
                logger.warning(f"Airtable update failed: {e}")
            sent = await send_email(biz_email, subject, body, name)
            status_msg = "✅ Email bhej di!" if sent else "⚠️ Email fail — SMTP check karo"
            self.deals.log_email(name, biz_email, subject, "Sent" if sent else "Failed")
            embed = discord.Embed(title=f"✅ Approved: {name}", color=0x2ECC71)
            embed.add_field(name="📧 Subject", value=subject, inline=False)
            embed.add_field(name="📝 Email Body", value=body[:800], inline=False)
            embed.add_field(name="📤 Status", value=status_msg, inline=False)
            embed.add_field(name="💰 Suggested", value=pricing["pitch"], inline=True)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"📱 **{name}** ki email nahi mili — DM script bana raha hun…", ephemeral=True)
            dm_script = await asyncio.to_thread(self.dm_sender.build_dm, lead, pricing)
            try:
                self.db.update("Raw Dump", self.record_id, {"Status": "Approved", "EmailStatus": "DM Required", "ContactMethod": "DM"})
            except Exception as e:
                logger.warning(f"Airtable update failed: {e}")
            self.deals.log_email(name, "NO_EMAIL", f"DM Script — {name}", "DM Required")
            mkt_ch = await get_or_create_channel(interaction.guild, Config.MARKETING_CHANNEL_NAME)
            embed = discord.Embed(title=f"📱 DM Script Ready: {name}", color=0x3498DB)
            embed.add_field(name="🏷️ Business", value=f"{name} | {niche}", inline=True)
            embed.add_field(name="📍 Location", value=f"{city}, {country}", inline=True)
            embed.add_field(name="💰 Suggested", value=pricing["pitch"], inline=True)
            if profiles:
                links = []
                for platform, url in profiles.items():
                    icon = {"instagram": "📸", "facebook": "👥", "twitter": "🐦"}.get(platform, "🔗")
                    links.append(f"{icon} [{platform.capitalize()}]({url})")
                embed.add_field(name="🔗 In Profiles Pe DM Karo", value="\n".join(links), inline=False)
            else:
                embed.add_field(name="🔍 Profile Links", value=f"Google pe dhundho: `{name} {city} Instagram`", inline=False)
            embed.add_field(name="📝 DM Script (Copy Karo)", value=f"```{dm_script[:900]}```", inline=False)
            embed.set_footer(text="Email nahi mili — DM se contact karo ☝️")
            await mkt_ch.send(embed=embed)
            await interaction.followup.send(f"📱 Email nahi mili — DM script {mkt_ch.mention} mein bhej di!")
        self._disable_all()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="❌ Skip", style=discord.ButtonStyle.danger, custom_id="skip_placeholder")
    async def skip_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        lead = await self._get_lead()
        name = lead["name"] if lead else self.record_id
        try:
            self.db.update("Raw Dump", self.record_id, {"Status": "Skipped"})
        except Exception as e:
            logger.warning(f"Skip update failed: {e}")
        await interaction.followup.send(f"❌ **{name}** skip ho gaya.", ephemeral=True)
        self._disable_all()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="📢 Direct Outreach", style=discord.ButtonStyle.primary, custom_id="direct_placeholder")
    async def direct_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        lead = await self._get_lead()
        if not lead:
            await interaction.followup.send("❌ Lead data nahi mila.", ephemeral=True)
            return
        name = lead["name"]
        niche = lead["niche"]
        city = lead["city"]
        country = lead["country"]
        weak_points = lead.get("weak_points", [])
        profiles = lead.get("profiles", {})
        pricing = self.ai.suggest_pricing(niche, weak_points, country)
        pitch = await asyncio.to_thread(self.ai.generate_discord_pitch, name, niche, city, country, weak_points, profiles, pricing)
        try:
            self.db.update("Raw Dump", self.record_id, {"Status": "Direct Outreach"})
        except Exception as e:
            logger.warning(f"Direct update failed: {e}")
        mkt_ch = await get_or_create_channel(interaction.guild, Config.MARKETING_CHANNEL_NAME)
        embed = discord.Embed(title=f"📢 Direct Outreach: {name}", description=pitch, color=0x3498DB)
        embed.add_field(name="📍 Location", value=f"{city}, {country}", inline=True)
        embed.add_field(name="🏷️ Niche", value=niche, inline=True)
        embed.add_field(name="💰 Price", value=pricing["pitch"], inline=True)
        if profiles:
            prof_text = "\n".join(f"• [{k.capitalize()}]({v})" for k, v in profiles.items())
            embed.add_field(name="🔗 Their Profiles", value=prof_text, inline=False)
        await mkt_ch.send(embed=embed)
        await interaction.followup.send(f"📢 Pitch {mkt_ch.mention} mein bhej di!", ephemeral=True)
        self._disable_all()
        await interaction.message.edit(view=self)

    def _disable_all(self):
        for child in self.children:
            child.disabled = True


def build_analysis_embeds(analysis: dict) -> list[discord.Embed]:
    embeds = []
    score = analysis.get("weakness_score", 0)
    color = 0xE74C3C if score >= 7 else (0xF1C40F if score >= 4 else 0x2ECC71)
    overview = discord.Embed(title=f"📊 Analysis Report: {analysis.get('title', analysis.get('url'))}", color=color)
    overview.add_field(name="URL", value=analysis.get('url'), inline=False)
    overview.add_field(name="Load Time", value=f"{analysis.get('load_time_ms')}ms", inline=True)
    overview.add_field(name="Secure (SSL)", value="✅ Yes" if analysis.get('is_secure') else "❌ No", inline=True)
    overview.add_field(name="Tech Stack", value=", ".join(analysis.get('tech_stack')) if analysis.get('tech_stack') else "None detected", inline=False)
    overview.add_field(name="🔥 Weakness Score", value=f"{score}/10", inline=False)
    embeds.append(overview)
    socials = discord.Embed(title="📱 Profiles & Contact Info", color=0x3498DB)
    prof_text = ""
    for k, v in analysis.get("social_profiles", {}).items():
        icon = {"instagram": "📸", "facebook": "👥", "tiktok": "🎵", "linkedin": "💼", "twitter": "🐦"}.get(k, "🔗")
        prof_text += f"{icon} [{k.capitalize()}]({v})\n"
    socials.add_field(name="Social Profiles", value=prof_text or "❌ None found", inline=False)
    contacts = analysis.get("contacts", {})
    socials.add_field(name="📧 Emails", value="\n".join(contacts.get("emails", [])) or "❌ None", inline=True)
    socials.add_field(name="📞 Phones", value="\n".join(contacts.get("phones", [])) or "❌ None", inline=True)
    socials.add_field(name="💬 WhatsApp", value="\n".join(contacts.get("whatsapp", [])) or "❌ None", inline=True)
    embeds.append(socials)
    problems = discord.Embed(title="⚠️ Issues & Weak Points Detected", color=0xE74C3C)
    probs = analysis.get("problems", [])
    problems.description = "\n".join(f"❌ {p}" for p in probs) if probs else "✅ No major issues detected!"
    embeds.append(problems)
    return embeds


def build_post_template_embeds(post_data: dict) -> tuple[discord.Embed | None, list[discord.Embed], list[str]]:
    import urllib.parse
    import random
    import string
    embeds = []
    codes = []
    analysis_emb = None
    reasoning = post_data.get("post_analysis", "")
    if reasoning:
        analysis_emb = discord.Embed(title="🧠 Why Current Posts Aren't Working", description=reasoning, color=0x9B59B6)
    for i, tpl in enumerate(post_data.get("templates", [])):
        style = tpl.get('style', 'Post')
        file_type = tpl.get('file_type', 'PNG')
        code = ''.join(random.choices(string.digits, k=4))
        codes.append(code)
        emb = discord.Embed(title=f"📌 Template {i+1}: {style.upper()}", color=0xF1C40F)
        emb.add_field(name="🆔 Approval Code", value=f"**`{code}`**", inline=True)
        emb.add_field(name="📁 File Type", value=f"`{file_type}`", inline=True)
        emb.add_field(name="🎨 Post Style", value=f"`{style}`", inline=True)
        cap = tpl.get('caption', '')
        if len(cap) > 1024:
            cap = cap[:1021] + "..."
        emb.add_field(name="📝 Caption", value=f"```{cap}```", inline=False)
        emb.add_field(name="#️⃣ Hashtags", value=tpl.get('hashtags', ''), inline=False)
        emb.add_field(name="🖼️ Visual Prompt", value=tpl.get('image_prompt', ''), inline=False)
        img_prompt = tpl.get('image_prompt', '')
        if img_prompt:
            style_lower = style.lower()
            if "vector" in style_lower or "illustration" in style_lower:
                modifier = "high quality vector illustration, premium digital art, clean lines, modern corporate style"
            elif "3d" in style_lower or "ai art" in style_lower:
                modifier = "stunning 3D render, octane render, highly detailed, cinematic lighting, ultra realistic 3D"
            elif "minimalist" in style_lower or "clean" in style_lower:
                modifier = "ultra minimalist, premium aesthetic, modern UI, negative space, highly professional, clean background"
            elif "typography" in style_lower:
                modifier = "bold premium typography design, modern font layout, clean aesthetic, minimalist poster"
            elif "infographic" in style_lower:
                modifier = "clean professional infographic design, data visualization layout, modern UI dashboard style"
            elif "photomontage" in style_lower or "manipulation" in style_lower:
                modifier = "hyper-realistic photo manipulation, cinematic poster, dramatic lighting, high-end photoshop, 8k"
            else:
                modifier = "hyper-realistic, high-end commercial photography, professional marketing asset, photorealistic, DSLR, 8k"
            clean_prompt = f"{modifier}. {img_prompt}"
            encoded = urllib.parse.quote(clean_prompt)
            seed = random.randint(1, 1000000)
            image_url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1080&nologo=true&private=true&seed={seed}"
            tpl['generated_image_url'] = image_url
            emb.set_image(url=image_url)
        emb.add_field(name="💡 Why This Is Better", value=tpl.get('why_better', ''), inline=False)
        emb.add_field(name="📈 Expected Impact", value=tpl.get('expected_improvement', ''), inline=True)
        emb.add_field(name="⏰ Best Time", value=tpl.get('best_time', ''), inline=True)
        emb.set_footer(text=f"Client Approval Code: {code} | Share this with your client to approve this template")
        embeds.append(emb)
    return analysis_emb, embeds, codes


class TemplateDownloadView(discord.ui.View):
    def __init__(self, template_data: dict, template_code: str, business_name: str, niche: str):
        super().__init__(timeout=None)
        self.template_data = template_data
        self.template_code = template_code
        self.business_name = business_name
        self.niche = niche
        self.download_btn.custom_id = f"tpl_dl_{template_code}"

    @discord.ui.button(label="📥 Download Media File", style=discord.ButtonStyle.secondary, custom_id="tpl_dl_placeholder")
    async def download_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        tpl = self.template_data
        style = tpl.get('style', 'Post')
        file_type = tpl.get('file_type', 'PNG').lower()
        if file_type not in ['png', 'jpeg', 'jpg', 'mp4']:
            file_type = 'png'
        if file_type == 'mp4':
            file_type = 'png'
        image_url = tpl.get('generated_image_url')
        import aiohttp
        import io as _io
        file_bytes = None
        if image_url:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status == 200:
                            file_bytes = _io.BytesIO(await resp.read())
            except Exception as e:
                logger.error(f"Failed to download image: {e}")
        if not file_bytes:
            file_bytes = _io.BytesIO(b"Media generation failed.")
            file_type = "txt"
        filename = f"{self.business_name.replace(' ', '_')[:15]}_{style.replace('/', '_')[:10]}_{self.template_code}.{file_type}"
        discord_file = discord.File(fp=file_bytes, filename=filename)
        msg_content = (
            f"📥 **Template `{self.template_code}` — {style.upper()}**\n\n"
            f"**📝 Caption:**\n{tpl.get('caption', '')}\n\n"
            f"**#️⃣ Hashtags:**\n{tpl.get('hashtags', '')}"
        )
        await interaction.followup.send(content=msg_content[:2000], file=discord_file, ephemeral=True)


class AnalysisActionView(discord.ui.View):
    def __init__(self, target_url: str, business_name: str = "", niche: str = "",
                 analysis_data: dict = None, ai=None, db=None, deals=None):
        super().__init__(timeout=None)
        self.target_url = target_url
        self.business_name = business_name
        self.niche = niche
        self.analysis_data = analysis_data or {}
        self.ai = ai
        self.db = db
        self.deals = deals

    def _get_weak_points(self) -> list:
        return self.analysis_data.get("problems", [])

    def _get_contacts(self) -> dict:
        return self.analysis_data.get("contacts", {})

    @discord.ui.button(label="✉️ Cold Email", style=discord.ButtonStyle.secondary, custom_id="ana_email")
    async def email_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not self.ai:
            await interaction.followup.send("❌ AI not available.", ephemeral=True)
            return
        weak_points = self._get_weak_points()
        contacts = self._get_contacts()
        emails = contacts.get("emails", [])
        country = self.analysis_data.get("country", "United States")
        pricing = self.ai.suggest_pricing(self.niche, weak_points, country)
        await interaction.followup.send(f"⚙️ Generating cold email for **{self.business_name}**...", ephemeral=True)
        email_data = await asyncio.to_thread(self.ai.generate_cold_email, self.business_name, self.niche, "", country, weak_points, self.target_url, pricing)
        subject = email_data.get("subject", f"Quick thought about {self.business_name}")
        body = email_data.get("body", "")
        emb = discord.Embed(title=f"✉️ Cold Email: {self.business_name}", color=0x2ECC71)
        emb.add_field(name="📧 To", value=", ".join(emails) if emails else "No email found — send manually", inline=False)
        emb.add_field(name="📌 Subject", value=subject, inline=False)
        emb.add_field(name="📝 Body", value=body[:1000], inline=False)
        emb.add_field(name="💰 Suggested Price", value=pricing.get("pitch", ""), inline=True)
        emb.set_footer(text="Copy karein aur client ko bhejein!")
        mkt_ch = await get_or_create_channel(interaction.guild, Config.MARKETING_CHANNEL_NAME)
        await mkt_ch.send(embed=emb)
        await interaction.followup.send(f"✅ Cold email ready → {mkt_ch.mention}", ephemeral=True)

    @discord.ui.button(label="📱 DM Pitch", style=discord.ButtonStyle.primary, custom_id="ana_dm")
    async def dm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not self.ai:
            await interaction.followup.send("❌ AI not available.", ephemeral=True)
            return
        weak_points = self._get_weak_points()
        profiles = self.analysis_data.get("social_profiles", {})
        country = self.analysis_data.get("country", "United States")
        pricing = self.ai.suggest_pricing(self.niche, weak_points, country)
        dm_script = await asyncio.to_thread(self.ai.generate_dm_script, self.business_name, self.niche, "", country, weak_points, pricing, [], profiles)
        emb = discord.Embed(title=f"📱 DM Script: {self.business_name}", color=0x3498DB)
        emb.add_field(name="🏷️ Business", value=f"{self.business_name} | {self.niche}", inline=True)
        emb.add_field(name="🔗 Target URL", value=self.target_url, inline=False)
        if profiles:
            prof_lines = "\n".join(f"• [{k.capitalize()}]({v})" for k, v in profiles.items())
            emb.add_field(name="📲 Send DM To", value=prof_lines, inline=False)
        emb.add_field(name="📝 DM Script (Copy Karo)", value=f"```{dm_script[:900]}```", inline=False)
        emb.add_field(name="💰 Suggested Price", value=pricing.get("pitch", ""), inline=True)
        emb.set_footer(text="Copy karein aur DM bhejein!")
        mkt_ch = await get_or_create_channel(interaction.guild, Config.MARKETING_CHANNEL_NAME)
        await mkt_ch.send(embed=emb)
        await interaction.followup.send(f"📱 DM Script ready → {mkt_ch.mention}", ephemeral=True)

    @discord.ui.button(label="📞 Call Script", style=discord.ButtonStyle.danger, custom_id="ana_call")
    async def call_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not self.ai:
            await interaction.followup.send("❌ AI not available.", ephemeral=True)
            return
        weak_points = self._get_weak_points()
        country = self.analysis_data.get("country", "United States")
        pricing = self.ai.suggest_pricing(self.niche, weak_points, country)
        script = await asyncio.to_thread(self.ai.generate_call_script, self.business_name, self.niche, weak_points, pricing)
        emb = discord.Embed(title=f"📞 Call Script: {self.business_name}", description=script[:3900], color=0xE74C3C)
        emb.add_field(name="🏷️ Business", value=f"{self.business_name} | {self.niche}", inline=True)
        emb.add_field(name="💰 Close At", value=pricing.get("pitch", ""), inline=True)
        emb.set_footer(text="Script perh kar call karein — Deal close hone ke chances 60%+ hain!")
        mkt_ch = await get_or_create_channel(interaction.guild, Config.MARKETING_CHANNEL_NAME)
        await mkt_ch.send(embed=emb)
        await interaction.followup.send(f"📞 Call Script ready → {mkt_ch.mention}", ephemeral=True)

    @discord.ui.button(label="💾 Save Lead", style=discord.ButtonStyle.success, custom_id="ana_save")
    async def save_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not self.db:
            await interaction.followup.send("❌ Database not available.", ephemeral=True)
            return
        contacts = self._get_contacts()
        weak_points = self._get_weak_points()
        weak_text = "\n".join(f"• {w}" for w in weak_points)
        try:
            await asyncio.to_thread(
                self.db.create, "Raw Dump",
                {
                    "Name": self.business_name,
                    "Niche": self.niche,
                    "Website": self.target_url,
                    "Email": ", ".join(contacts.get("emails", [])),
                    "Phone": ", ".join(contacts.get("phones", [])),
                    "WeakPoints": weak_text,
                    "LeadScore": str(self.analysis_data.get("weakness_score", 0)),
                    "Status": "New",
                    "Source": "Link Analyze",
                }
            )
            await interaction.followup.send(
                f"💾 **{self.business_name}** Airtable mein save ho gaya! ✅\n"
                f"Email: {', '.join(contacts.get('emails', [])) or 'None'}\n"
                f"Score: {self.analysis_data.get('weakness_score', 0)}/10",
                ephemeral=True)
        except Exception as e:
            logger.error(f"Save lead failed: {e}")
            await interaction.followup.send(f"⚠️ Save fail: `{e}`", ephemeral=True)


__all__ = [
    "LeadActionView", "build_lead_embed", "fetch_lead_from_airtable",
    "build_analysis_embeds", "build_post_template_embeds",
    "AnalysisActionView", "TemplateDownloadView"
]
