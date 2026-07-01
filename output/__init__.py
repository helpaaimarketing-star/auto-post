from output.post_processor import build_post_text_file, format_post_embed_fields


def __getattr__(name):
    if name in ("send_email", "send_email_sync"):
        from email_sender import send_email, send_email_sync
        if name == "send_email":
            return send_email
        return send_email_sync
    elif name in ("LeadActionView", "build_lead_embed", "fetch_lead_from_airtable"):
        from views import LeadActionView, build_lead_embed, fetch_lead_from_airtable
        if name == "LeadActionView":
            return LeadActionView
        elif name == "build_lead_embed":
            return build_lead_embed
        return fetch_lead_from_airtable
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = [
    "send_email", "send_email_sync",
    "LeadActionView", "build_lead_embed", "fetch_lead_from_airtable",
    "build_post_text_file", "format_post_embed_fields",
]
