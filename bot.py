"""SMMA Bot System — Central Discord Controller & Slash Command Handler."""

import io
import os
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import Config
from airtable_client import AirtableClient
from utils.helper import get_or_create_channel
from ai_agent import AIAgent
from processing.data_processor import DataProcessor
from order_manager import DealManager
from learner import Learner
from followup import FollowUpManager
from validation.validator import validate_scrape_input, validate_deal_input, validate_build_input
from input.input import normalize_scrape_input, normalize_deal_input, normalize_build_input
from input.parser import (
    country_autocomplete, niche_autocomplete,
    city_autocomplete, order_id_autocomplete,
)
from processing.link_analyzer import LinkAnalyzer
from processing.post_generator import PostGenerator
from views import LeadActionView, build_lead_embed, build_analysis_embeds, build_post_template_embeds, AnalysisActionView, TemplateDownloadView
from output.post_processor import build_post_text_file, format_post_embed_fields, build_analysis_report_text_file

logger = logging.getLogger("SMMABot")


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"SMMA Bot OK")

    def log_message(self, *_):
        pass


def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    logger.info(f"Health server on port {port}")
    server.serve_forever()


class DiscordBot:
    """Manages Discord bot events, commands, and initialization."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.db = AirtableClient()
        self.ai = AIAgent()
        self.processor = DataProcessor()
        self.deals = DealManager()
        self.learner = Learner()
        self.followups = FollowUpManager()
        self._register_events()
        self._register_commands()

    def _register_events(self):
        bot = self.bot

        @bot.event
        async def on_ready():
            logger.info(f"SMMA Bot online: {bot.user.name} ({bot.user.id})")
            bot.add_view(LeadActionView(record_id="__persistent__",
                                        db=self.db, ai=self.ai, deals=self.deals))
            logger.info("Persistent LeadActionView registered")
            if not heartbeat.is_running():
                heartbeat.start()
            try:
                if Config.DISCORD_GUILD_ID:
                    guild_obj = discord.Object(id=int(Config.DISCORD_GUILD_ID))
                    bot.tree.copy_global_to(guild=guild_obj)
                    synced = await bot.tree.sync(guild=guild_obj)
                else:
                    synced = await bot.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands: {[c.name for c in synced]}")
            except Exception as e:
                logger.error(f"Command sync failed: {e}")

        @tasks.loop(minutes=30)
        async def heartbeat():
            logger.info(f"Heartbeat — alive | Guilds: {len(bot.guilds)}")

        @heartbeat.before_loop
        async def before_heartbeat():
            await bot.wait_until_ready()

        self.heartbeat = heartbeat

    def _register_commands(self):
        bot = self.bot

        @bot.tree.command(name="scrape", description="Global social media leads dhundho (Influencers, Startups, E-com)")
        @app_commands.describe(
            niche="Business category (e.g. Clothing, Fitness, SaaS)",
            city="Target city (or paste URL here for 🔗 Link Analyze)",
            country="Target country (Optional for Worldwide)",
            limit="Kitne leads chahiye",
        )
        @app_commands.autocomplete(niche=niche_autocomplete, city=city_autocomplete,
                                   country=country_autocomplete)
        @app_commands.choices(limit=[
            app_commands.Choice(name="5  leads  — Quick test", value=5),
            app_commands.Choice(name="10 leads  — Normal", value=10),
            app_commands.Choice(name="15 leads  — Default", value=15),
            app_commands.Choice(name="20 leads  — More results", value=20),
            app_commands.Choice(name="25 leads  — Maximum", value=25),
        ])
        async def scrape_command(interaction: discord.Interaction, niche: str,
                                  city: Optional[str] = None, country: Optional[str] = None, limit: Optional[int] = 15):
            # ── Link Analyze Mode ─────────────────────────────────────
            if "link analyze" in niche.lower():
                if not city or not city.strip():
                    await interaction.response.send_message(
                        "🔗 **Link Analyze mode!**\n"
                        "City wale field mein apna URL daalo (e.g. `https://example.com` ya `instagram.com/nike`)\n"
                        "Phir dobara `/scrape` chalao with niche = 🔗 Link Analyze",
                        ephemeral=True)
                    return

                link = city.strip()
                await interaction.response.defer()
                ana_ch = await get_or_create_channel(interaction.guild, Config.ANALYSIS_CHANNEL_NAME)
                await interaction.followup.send(
                    f"🔍 **Analyzing:** `{link}`\n"
                    f"Full report + 5 post templates generate ho rahi hain...\n"
                    f"Results → {ana_ch.mention}")

                try:
                    analyzer = LinkAnalyzer()
                    analysis_data = await asyncio.to_thread(analyzer.analyze, link)

                    text_for_niche = f"{analysis_data.get('title', '')} {analysis_data.get('description', '')}"
                    detected_niche = await asyncio.to_thread(self.ai.detect_niche, text_for_niche, link)
                    b_name = analysis_data.get("title") or link.split("://")[-1].split("/")[0]

                    generator = PostGenerator(self.ai)
                    post_data = await asyncio.to_thread(generator.generate_templates, analysis_data, b_name, detected_niche)

                    ana_embeds = build_analysis_embeds(analysis_data)
                    for emb in ana_embeds:
                        await ana_ch.send(embed=emb)
                        await asyncio.sleep(0.3)

                    analysis_emb, post_embeds, template_codes = build_post_template_embeds(post_data)
                    if analysis_emb:
                        await ana_ch.send(embed=analysis_emb)

                    for idx, emb in enumerate(post_embeds):
                        code = template_codes[idx] if idx < len(template_codes) else "0000"
                        tview = TemplateDownloadView(
                            template_data=post_data.get("templates", [])[idx] if idx < len(post_data.get("templates", [])) else {},
                            template_code=code,
                            business_name=b_name,
                            niche=detected_niche
                        )
                        tpl_data = post_data.get("templates", [])[idx] if idx < len(post_data.get("templates", [])) else {}
                        df = tpl_data.get("_discord_file")
                        if df:
                            await ana_ch.send(embed=emb, file=df, view=tview)
                        else:
                            await ana_ch.send(embed=emb, view=tview)
                        await asyncio.sleep(0.5)

                    view = AnalysisActionView(
                        target_url=link,
                        business_name=b_name,
                        niche=detected_niche,
                        analysis_data=analysis_data,
                        ai=self.ai,
                        db=self.db,
                        deals=self.deals
                    )
                    await ana_ch.send("Take action on this report:", view=view)

                    # Send downloadable report text file
                    report_text = build_analysis_report_text_file(analysis_data, post_data, b_name, detected_niche)
                    file_bytes = io.BytesIO(report_text.encode("utf-8"))
                    filename = f"SMMA_Audit_{b_name.replace(' ', '_')[:20]}.txt"
                    discord_file = discord.File(fp=file_bytes, filename=filename)
                    
                    dl_embed = discord.Embed(
                        title=f"📥 Download Audit & Templates: {b_name}",
                        description=f"Ye file download kar ke client ko send karein! ✅",
                        color=0x1ABC9C,
                    )
                    downloads_ch = await get_or_create_channel(interaction.guild, Config.DOWNLOADS_CHANNEL_NAME)
                    await downloads_ch.send(embed=dl_embed, file=discord_file)
                    
                    discord_file_analysis = discord.File(fp=io.BytesIO(report_text.encode("utf-8")), filename=filename)
                    await ana_ch.send(embed=dl_embed, file=discord_file_analysis)

                except Exception as e:
                    logger.exception("Link Analyze failed")
                    await interaction.followup.send(f"❌ Analyze fail: `{e}`")
                return
            # ── Normal Scrape Mode ────────────────────────────────────

            c_str = city.strip() if city else ""
            co_str = country.strip() if country else ""
            loc_str = f"{c_str}, {co_str}".strip(", ") if c_str or co_str else "Worldwide"
            query = f"{niche} in {loc_str}" if loc_str != "Worldwide" else f"{niche} worldwide"
            raw = normalize_scrape_input(query, niche, city, country, limit)
            ok, err = validate_scrape_input(**{k: raw[k] for k in
                ("query", "niche", "city", "country", "limit")})
            if not ok:
                await interaction.response.send_message(f"❌ {err}", ephemeral=True)
                return

            await interaction.response.defer()
            leads_ch = await get_or_create_channel(interaction.guild, Config.LEADS_CHANNEL_NAME)
            await interaction.followup.send(
                f"🔍 **Scraping shuru!**\n`{niche}` | {loc_str}\nResults → {leads_ch.mention}")

            try:
                leads = await asyncio.to_thread(
                    self.processor.scrape_leads,
                    raw["query"], raw["niche"], raw["city"], raw["country"], raw["limit"],
                )
            except Exception as e:
                await interaction.followup.send(f"❌ Scraping fail: `{e}`")
                return

            if not leads:
                await leads_ch.send(f"⚠️ `{niche}` ke liye koi weak lead nahi mila — {loc_str}.")
                return

            await leads_ch.send(f"✅ **{len(leads)} weak leads mile** | `{niche}` | {loc_str}")
            for i, lead in enumerate(leads, 1):
                embed = build_lead_embed(lead, i, len(leads), self.ai)
                view = LeadActionView(record_id=lead["record_id"], lead=lead,
                                      db=self.db, ai=self.ai, deals=self.deals)
                await leads_ch.send(embed=embed, view=view)
                await asyncio.sleep(0.6)

        @bot.tree.command(name="scan", description="Global scan: dropdowns ke sath influencers/startups dhundho")
        @app_commands.describe(
            niche="Business category (e.g. Clothing, Fitness, SaaS)",
            city="Target city (Optional for Worldwide)",
            country="Target country (Optional for Worldwide)",
            limit="Kitne leads chahiye",
        )
        @app_commands.autocomplete(niche=niche_autocomplete, city=city_autocomplete,
                                   country=country_autocomplete)
        @app_commands.choices(limit=[
            app_commands.Choice(name="5 leads - Quick test", value=5),
            app_commands.Choice(name="10 leads - Normal", value=10),
            app_commands.Choice(name="15 leads - Default", value=15),
            app_commands.Choice(name="20 leads - More results", value=20),
            app_commands.Choice(name="25 leads - Maximum", value=25),
        ])
        async def scan_command(interaction: discord.Interaction, niche: str,
                               city: Optional[str] = None, country: Optional[str] = None, limit: Optional[int] = 15):
            c_str = city.strip() if city else ""
            co_str = country.strip() if country else ""
            loc_str = f"{c_str}, {co_str}".strip(", ") if c_str or co_str else "Worldwide"
            query = f"{niche} in {loc_str}" if loc_str != "Worldwide" else f"{niche} worldwide"
            raw = normalize_scrape_input(query, niche, city, country, limit)
            ok, err = validate_scrape_input(**{k: raw[k] for k in
                ("query", "niche", "city", "country", "limit")})
            if not ok:
                await interaction.response.send_message(f"❌ {err}", ephemeral=True)
                return

            await interaction.response.defer()
            leads_ch = await get_or_create_channel(interaction.guild, Config.LEADS_CHANNEL_NAME)
            await interaction.followup.send(
                f"🔍 **Scan shuru!** `{niche}` | {loc_str}\nResults → {leads_ch.mention}")

            try:
                leads = await asyncio.to_thread(
                    self.processor.scrape_leads,
                    raw["query"], raw["niche"], raw["city"], raw["country"], raw["limit"],
                )
            except Exception as e:
                await interaction.followup.send(f"❌ Scan fail: `{e}`")
                return

            if not leads:
                await leads_ch.send(f"⚠️ `{niche}` ke liye koi weak lead nahi mila — {loc_str}.")
                return

            await leads_ch.send(f"✅ **{len(leads)} weak leads mile** | `{niche}` | {loc_str}")
            for i, lead in enumerate(leads, 1):
                embed = build_lead_embed(lead, i, len(leads), self.ai)
                view = LeadActionView(record_id=lead["record_id"], lead=lead,
                                      db=self.db, ai=self.ai, deals=self.deals)
                await leads_ch.send(embed=embed, view=view)
                await asyncio.sleep(0.6)

        @bot.tree.command(name="analyze", description="Analyze any social profile or website and generate 5 post templates")
        @app_commands.describe(
            link="Website or Social Media URL (e.g. instagram.com/nike)",
            sample_captions="(Optional) Paste 2-3 existing captions from this profile separated by | for better AI results"
        )
        async def analyze_command(interaction: discord.Interaction, link: str, sample_captions: str = ""):
            await interaction.response.defer()
            ana_ch = await get_or_create_channel(interaction.guild, Config.ANALYSIS_CHANNEL_NAME)
            await interaction.followup.send(f"🔍 **Analyzing:** `{link}`\nGenerating full report and 5 post templates...\nResults → {ana_ch.mention}")

            try:
                # 1. Analyze Link
                analyzer = LinkAnalyzer()
                analysis_data = await asyncio.to_thread(analyzer.analyze, link)
                
                # Auto-detect niche always
                text_for_niche = f"{analysis_data.get('title', '')} {analysis_data.get('description', '')}"
                detected_niche = await asyncio.to_thread(self.ai.detect_niche, text_for_niche, link)
                logger.info(f"Auto-detected niche: {detected_niche}")

                # Use title from analysis or domain from URL as business name
                b_name = analysis_data.get("title") or link.split("://")[-1].split("/")[0]

                # 2. Inject manual captions if provided
                if sample_captions.strip():
                    captions_list = [c.strip() for c in sample_captions.split("|") if c.strip()]
                    manual_posts = [{"caption": c, "likes": 0, "comments": 0, "type": "image", "hashtags": [], "url": ""} for c in captions_list]
                    analysis_data["manual_sample_posts"] = manual_posts
                    logger.info(f"Manual captions injected: {len(manual_posts)}")

                # 2. Generate Post Templates
                generator = PostGenerator(self.ai)
                post_data = await asyncio.to_thread(generator.generate_templates, analysis_data, b_name, detected_niche)

                # 3. Send Embeds to Analysis Channel
                ana_embeds = build_analysis_embeds(analysis_data)
                for emb in ana_embeds:
                    await ana_ch.send(embed=emb)
                    await asyncio.sleep(0.3)
                    
                analysis_emb, post_embeds, template_codes = build_post_template_embeds(post_data)
                if analysis_emb:
                    await ana_ch.send(embed=analysis_emb)
                for idx, emb in enumerate(post_embeds):
                    code = template_codes[idx] if idx < len(template_codes) else "0000"
                    tpl = post_data.get("templates", [])[idx] if idx < len(post_data.get("templates", [])) else {}
                    view = TemplateDownloadView(
                        template_data=tpl,
                        template_code=code,
                        business_name=b_name,
                        niche=detected_niche,
                    )
                    msg = await ana_ch.send(embed=emb, view=view)
                    await asyncio.sleep(0.3)
                    image_url = tpl.get("generated_image_url", "")
                    if image_url:
                        try:
                            import aiohttp, io as _io
                            async with aiohttp.ClientSession() as _sess:
                                async with _sess.get(image_url, timeout=aiohttp.ClientTimeout(total=90)) as _r:
                                    if _r.status == 200:
                                        _data = await _r.read()
                                        _ext = "jpg" if tpl.get("file_type","PNG").upper()=="JPEG" else "png"
                                        _fname = f"template_{idx+1}_{code}.{_ext}"
                                        _new_emb = emb.copy()
                                        _new_emb.set_image(url=f"attachment://{_fname}")
                                        await msg.edit(embed=_new_emb, attachments=[discord.File(fp=_io.BytesIO(_data), filename=_fname)])
                        except Exception as _e:
                            logger.warning(f"Image update failed for template {idx+1}: {_e}")

                # 4. Action Buttons with full data
                view = AnalysisActionView(
                    target_url=link,
                    business_name=b_name,
                    niche=detected_niche,
                    analysis_data=analysis_data,
                    ai=self.ai,
                    db=self.db,
                    deals=self.deals
                )
                await ana_ch.send("Take action on this report:", view=view)
                
                # Send downloadable report text file
                report_text = build_analysis_report_text_file(analysis_data, post_data, b_name, detected_niche)
                file_bytes = io.BytesIO(report_text.encode("utf-8"))
                filename = f"SMMA_Audit_{b_name.replace(' ', '_')[:20]}.txt"
                discord_file = discord.File(fp=file_bytes, filename=filename)
                
                dl_embed = discord.Embed(
                    title=f"📥 Download Audit & Templates: {b_name}",
                    description=f"Ye file download kar ke client ko send karein! ✅",
                    color=0x1ABC9C,
                )
                downloads_ch = await get_or_create_channel(interaction.guild, Config.DOWNLOADS_CHANNEL_NAME)
                await downloads_ch.send(embed=dl_embed, file=discord_file)
                
                discord_file_analysis = discord.File(fp=io.BytesIO(report_text.encode("utf-8")), filename=filename)
                await ana_ch.send(embed=dl_embed, file=discord_file_analysis)
                
            except Exception as e:
                logger.exception("Analyze command failed")
                await interaction.followup.send(f"❌ Analyze fail: `{e}`")

        @bot.tree.command(name="dc", description="Deal close karo aur Order ID generate karo")
        @app_commands.describe(
            business="Client ka business name",
            niche="Business category",
            city="Client ka sheher",
            country="Client ka mulk",
            package="Package level",
            price="Agreed monthly price USD mein",
            email="Client ki email (optional)",
        )
        @app_commands.autocomplete(niche=niche_autocomplete, country=country_autocomplete)
        @app_commands.choices(package=[
            app_commands.Choice(name="Starter  — Basic  ($249–$499/mo)", value="starter"),
            app_commands.Choice(name="Growth   — Popular ($499–$899/mo)", value="growth"),
            app_commands.Choice(name="Pro      — Premium ($899–$1999/mo)", value="pro"),
        ])
        async def deal_close_command(interaction: discord.Interaction, business: str, niche: str,
                                      city: str, country: str, package: str, price: int,
                                      email: Optional[str] = ""):
            raw = normalize_deal_input(business, niche, city, country, package, price, email)
            ok, err = validate_deal_input(**{k: raw[k] for k in
                ("business", "niche", "city", "country", "package", "price", "email")})
            if not ok:
                await interaction.response.send_message(f"❌ {err}", ephemeral=True)
                return

            await interaction.response.defer()
            deals_ch = await get_or_create_channel(interaction.guild, Config.DEALS_CHANNEL_NAME)
            order_id = self.deals.close_deal(
                raw["business"], raw["niche"], raw["city"], raw["country"],
                raw["package"], raw["price"], raw["email"],
            )
            await asyncio.to_thread(
                self.learner.record_pricing,
                order_id, raw["business"], raw["niche"], raw["package"],
                raw["price"], raw["country"],
            )
            await asyncio.to_thread(
                self.learner.record_outcome,
                raw["business"], raw["niche"], "deal_close", "won",
                10, f"{raw['package']} at ${raw['price']}/mo",
            )

            embed = discord.Embed(title="🎉 Deal Close!", color=0x2ECC71)
            embed.add_field(name="🆔 Order ID", value=f"`{order_id}`", inline=False)
            embed.add_field(name="🏢 Business", value=business, inline=True)
            embed.add_field(name="📦 Package", value=package.capitalize(), inline=True)
            embed.add_field(name="💰 Value", value=f"${price}/mo", inline=True)
            embed.add_field(name="📍 Location", value=f"{city}, {country}", inline=True)
            if email:
                embed.add_field(name="📧 Email", value=email, inline=True)
            embed.add_field(name="⚡ Next Step",
                            value=f"`/build order_id:{order_id} platform:instagram`", inline=False)
            embed.set_footer(text="Congratulations! 🚀")
            await deals_ch.send(embed=embed)
            await interaction.followup.send(f"✅ Deal close! Order ID: `{order_id}`\n→ {deals_ch.mention}")

        @bot.tree.command(name="build", description="Client ke liye AI social media post banao + download")
        @app_commands.describe(
            order_id="Order ID — /dc ke baad mila tha",
            platform="Social media platform",
        )
        @app_commands.autocomplete(order_id=order_id_autocomplete)
        @app_commands.choices(platform=[
            app_commands.Choice(name="Instagram — Reels, Stories, Feed", value="instagram"),
            app_commands.Choice(name="Facebook  — Page posts, Groups", value="facebook"),
            app_commands.Choice(name="Twitter   — Tweets, Threads", value="twitter"),
        ])
        async def build_command(interaction: discord.Interaction, order_id: str,
                                 platform: str = "instagram"):
            raw = normalize_build_input(order_id, platform)
            ok, err = validate_build_input(raw["order_id"], raw["platform"])
            if not ok:
                await interaction.response.send_message(f"❌ {err}", ephemeral=True)
                return

            await interaction.response.defer()
            builds_ch = await get_or_create_channel(interaction.guild, Config.BUILDS_CHANNEL_NAME)
            downloads_ch = await get_or_create_channel(interaction.guild, Config.DOWNLOADS_CHANNEL_NAME)

            try:
                records = self.db.fetch_all("Deals", formula=f"{{OrderID}}='{order_id}'")
                if not records:
                    await interaction.followup.send(f"❌ Order ID `{order_id}` Airtable mein nahi mila.")
                    return
                deal = records[0]["fields"]
            except Exception as e:
                await interaction.followup.send(f"❌ Airtable error: `{e}`")
                return

            business = deal.get("BusinessName", "")
            niche = deal.get("Niche", "")
            city = deal.get("City", "")

            await interaction.followup.send(f"⚙️ **{business}** ke liye {platform} post ban rahi hai…")

            post_data = await asyncio.to_thread(
                self.ai.generate_social_post, business, niche, city, order_id, platform)
            self.deals.save_build(order_id, business, niche, platform, post_data)
            await asyncio.to_thread(
                self.learner.record_outcome,
                business, niche, "post_build", "ready_for_delivery",
                7, f"{platform} build for {order_id}",
            )
            fields = format_post_embed_fields(post_data)

            embed = discord.Embed(title=f"📱 Post Ready: {business}", color=0x9B59B6)
            embed.add_field(name="🆔 Order ID", value=f"`{order_id}`", inline=True)
            embed.add_field(name="📲 Platform", value=platform.capitalize(), inline=True)
            embed.add_field(name="⏰ Best Time", value=fields["best_time"], inline=True)
            embed.add_field(name="📝 Caption", value=fields["caption"], inline=False)
            embed.add_field(name="🏷️ Hashtags", value=fields["hashtags"], inline=False)
            embed.add_field(name="📖 Description", value=fields["description"], inline=False)
            embed.add_field(name="🎯 CTA", value=fields["cta"], inline=True)
            embed.add_field(name="📊 Est. Reach", value=fields["estimated_reach"], inline=True)
            embed.add_field(name="🔖 Tags", value=fields["tags"], inline=False)
            embed.add_field(name="🎨 Image Prompt", value=f"```{fields['image_prompt']}```", inline=False)
            await builds_ch.send(embed=embed)

            file_content = build_post_text_file(post_data, business, niche, order_id, platform)
            file_bytes = io.BytesIO(file_content.encode("utf-8"))
            filename = f"{order_id}_{platform}_{business.replace(' ', '_')[:20]}.txt"
            discord_file = discord.File(fp=file_bytes, filename=filename)

            dl_embed = discord.Embed(
                title=f"📥 Download: {business} — {platform.capitalize()}",
                description=f"**Order:** `{order_id}`\n**Platform:** {platform.capitalize()}\n\n"
                            f"File download karo aur client ko bhejo ✅",
                color=0x1ABC9C,
            )
            await downloads_ch.send(embed=dl_embed, file=discord_file)
            await interaction.followup.send(
                f"✅ Post ready!\nPreview → {builds_ch.mention}\n📥 Download → {downloads_ch.mention}")

        @bot.tree.command(name="followup", description="Interest tracking aur follow-up schedule karo")
        @app_commands.describe(
            business="Business/client name",
            contact="Email, phone, ya profile URL",
            channel="Follow-up channel",
            interest="Interest level",
            notes="Short notes",
            due_days="Kitne din baad follow-up karna hai",
            order_id="Optional Order ID",
        )
        @app_commands.choices(channel=[
            app_commands.Choice(name="Email", value="email"),
            app_commands.Choice(name="Instagram DM", value="instagram_dm"),
            app_commands.Choice(name="Facebook DM", value="facebook_dm"),
            app_commands.Choice(name="Phone", value="phone"),
        ])
        @app_commands.choices(interest=[
            app_commands.Choice(name="Hot", value="hot"),
            app_commands.Choice(name="Warm", value="warm"),
            app_commands.Choice(name="Cold", value="cold"),
        ])
        async def followup_command(interaction: discord.Interaction, business: str,
                                   contact: str, channel: str, interest: str,
                                   notes: Optional[str] = "",
                                   due_days: Optional[int] = 2,
                                   order_id: Optional[str] = ""):
            if not business.strip() or not contact.strip():
                await interaction.response.send_message(
                    "ERROR: Business aur contact required hain.", ephemeral=True)
                return
            if due_days is None:
                due_days = 2
            if due_days < 0 or due_days > 30:
                await interaction.response.send_message(
                    "ERROR: due_days 0 se 30 ke beech hona chahiye.", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)
            saved = await asyncio.to_thread(
                self.followups.create_followup,
                business.strip(), contact.strip(), channel, interest,
                (notes or "").strip(), due_days, (order_id or "").strip().upper(),
            )
            await asyncio.to_thread(
                self.learner.record_outcome,
                business.strip(), "", "followup", interest,
                {"hot": 9, "warm": 6, "cold": 3}.get(interest, 5),
                notes or "",
            )
            if saved:
                await interaction.followup.send(
                    f"Follow-up saved: **{business}** | {interest} | due in {due_days} day(s)")
            else:
                await interaction.followup.send(
                    "Follow-up save failed. Airtable `Follow-ups` table/fields check karein.")

    def run(self):
        threading.Thread(target=start_health_server, daemon=True).start()
        self.bot.run(Config.DISCORD_BOT_TOKEN, reconnect=True, log_handler=None)


def main():
    """Start the Discord bot."""
    bot_inst = DiscordBot()
    bot_inst.run()


if __name__ == "__main__":
    main()
