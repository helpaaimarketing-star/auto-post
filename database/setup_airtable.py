"""
setup_airtable.py — Database Layer
Run ONCE before starting the bot.
Prints exact instructions for setting up all required Airtable tables.
"""

TABLES = {
    "Raw Dump": [
        ("BusinessName", "Single line text"),
        ("Niche", "Single line text"),
        ("City", "Single line text"),
        ("Country", "Single line text"),
        ("Website", "URL"),
        ("Phone", "Single line text"),
        ("Address", "Single line text"),
        ("Rating", "Number (decimal)"),
        ("Reviews", "Number (integer)"),
        ("Platform", "Single line text"),
        ("WeakPoints", "Long text"),
        ("SocialProfiles", "Long text"),
        ("WeaknessScore", "Number (integer, 0–10)"),
        ("PlatformsMissing", "Single line text"),
        ("Status", "Single select: Pending Review | Approved | Skipped | Direct Outreach"),
        ("EmailStatus", "Single select: Queued | Sent | Failed | DM Required"),
        ("ContactMethod", "Single select: Email | DM"),
    ],
    "Deals": [
        ("OrderID", "Single line text"),
        ("BusinessName", "Single line text"),
        ("Niche", "Single line text"),
        ("City", "Single line text"),
        ("Country", "Single line text"),
        ("Package", "Single select: starter | growth | pro"),
        ("Price", "Number (integer)"),
        ("ClientEmail", "Email"),
        ("Status", "Single select: Deal Closed | Active | Churned"),
        ("Notes", "Long text"),
        ("DealDate", "Single line text"),
    ],
    "Post Builds": [
        ("OrderID", "Single line text"),
        ("BusinessName", "Single line text"),
        ("Niche", "Single line text"),
        ("Platform", "Single select: instagram | facebook | twitter"),
        ("Caption", "Long text"),
        ("Hashtags", "Long text"),
        ("Description", "Long text"),
        ("ImagePrompt", "Long text"),
        ("CTA", "Single line text"),
        ("BestTimeToPost", "Single line text"),
        ("EstimatedReach", "Single line text"),
        ("Tags", "Single line text"),
        ("Status", "Single select: Ready for Delivery | Delivered"),
        ("BuildDate", "Single line text"),
    ],
    "Email Log": [
        ("BusinessName", "Single line text"),
        ("ToEmail", "Email"),
        ("Subject", "Single line text"),
        ("Status", "Single select: Sent | Failed | No Email Found"),
        ("OrderID", "Single line text"),
        ("SentAt", "Single line text"),
    ],
    "Reports": [
        ("Title", "Single line text"),
        ("Niche", "Single line text"),
        ("City", "Single line text"),
        ("Country", "Single line text"),
        ("LeadCount", "Number (integer)"),
        ("AvgWeaknessScore", "Number (decimal)"),
        ("TopWeakPoints", "Long text"),
        ("CreatedAt", "Single line text"),
    ],
    "Follow-ups": [
        ("BusinessName", "Single line text"),
        ("Contact", "Single line text"),
        ("Channel", "Single select: email | instagram_dm | facebook_dm | phone"),
        ("InterestLevel", "Single select: hot | warm | cold"),
        ("Notes", "Long text"),
        ("OrderID", "Single line text"),
        ("Status", "Single select: Open | Done | Lost"),
        ("DueAt", "Date"),
        ("CreatedAt", "Single line text"),
    ],
    "Learner Data": [
        ("BusinessName", "Single line text"),
        ("Niche", "Single line text"),
        ("Action", "Single line text"),
        ("Outcome", "Single line text"),
        ("Score", "Number (integer)"),
        ("Notes", "Long text"),
        ("CreatedAt", "Single line text"),
    ],
    "Pricing History": [
        ("OrderID", "Single line text"),
        ("BusinessName", "Single line text"),
        ("Niche", "Single line text"),
        ("Package", "Single select: starter | growth | pro"),
        ("Price", "Number (integer)"),
        ("Country", "Single line text"),
        ("CreatedAt", "Single line text"),
    ],
}


def main():
    print("\n" + "═" * 60)
    print("  SMMA Bot — Airtable Setup Guide")
    print("═" * 60)
    print("\nGo to: https://airtable.com → Open your Base\n")
    print("Create the following 8 tables with these fields:\n")

    for table_name, fields in TABLES.items():
        print(f"┌─ TABLE: {table_name} {'─' * (45 - len(table_name))}")
        for field_name, field_type in fields:
            print(f"│  • {field_name:<22} → {field_type}")
        print(f"└{'─' * 50}\n")

    print("=" * 60)
    print("Once tables are created, fill in your .env file:")
    print("   AIRTABLE_API_KEY=your_key")
    print("   AIRTABLE_BASE_ID=your_base_id")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
