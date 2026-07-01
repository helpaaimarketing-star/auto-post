"""Duplicate detection — prevents re-processing the same lead."""

import logging
from airtable_client import AirtableClient

logger = logging.getLogger("CheckDuplication")


class DuplicationChecker:
    """Checks Airtable for existing business records."""

    def __init__(self):
        self.db = AirtableClient()

    def is_duplicate(self, business_name: str, platform: str = "google_maps",
                     table: str = "Leads") -> bool:
        name_safe = business_name.replace("'", "\\'")
        formula = f"{{Name}}='{name_safe}'"

        try:
            data = self.db._request(
                "GET", table,
                params={"filterByFormula": formula, "pageSize": 1},
            )
            exists = len(data.get("records", [])) > 0
            if exists:
                logger.info(f"Duplicate found: {business_name} ({platform})")
            return exists

        except RuntimeError as e:
            err = str(e)
            if "INVALID_FILTER_BY_FORMULA" in err or "Unknown field names" in err:
                logger.warning(
                    f"Dedup formula failed — field names in Airtable may not match.\n"
                    f"Expected fields: Name in table '{table}'.\n"
                    f"Error: {err}"
                )
            else:
                logger.warning(f"Dedup check failed for '{business_name}': {err}")
            return False
