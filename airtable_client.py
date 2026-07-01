"""Database utilities — Airtable client with retry and pagination."""

import time
import logging
import requests
from typing import Dict, Any, List, Optional
from config import Config

logger = logging.getLogger("DBUtils")


class AirtableClient:
    """Handles all Airtable read/write operations with rate-limit handling."""

    def __init__(self):
        self.base_url = f"https://api.airtable.com/v0/{Config.AIRTABLE_BASE_ID}"
        self.headers = {
            "Authorization": f"Bearer {Config.AIRTABLE_API_KEY}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, table: str,
                 json_data=None, params=None, retries=4) -> Dict:
        url = f"{self.base_url}/{table}"
        delay = 1.0
        for attempt in range(retries):
            try:
                res = requests.request(
                    method, url, headers=self.headers,
                    json=json_data, params=params, timeout=15,
                )
                if res.status_code == 429:
                    logger.warning(f"Airtable rate limit — waiting {delay}s")
                    time.sleep(delay)
                    delay *= 2
                    continue
                if res.status_code not in (200, 201):
                    # Log FULL error body so we can see exactly which field fails
                    full_error = res.text
                    logger.error(
                        f"Airtable {res.status_code} on {method} {table}:\n"
                        f"Payload fields: {list(json_data.get('fields', {}).keys()) if json_data else 'N/A'}\n"
                        f"Response: {full_error}"
                    )
                    raise RuntimeError(
                        f"Airtable error {res.status_code}: {full_error[:300]}"
                    )
                return res.json()
            except requests.RequestException as e:
                if attempt == retries - 1:
                    raise RuntimeError(f"Airtable network error: {e}")
                time.sleep(delay)
                delay *= 2
        raise RuntimeError("Airtable retries exhausted")

    def create(self, table: str, fields: Dict) -> Dict:
        clean_fields = {k: v for k, v in fields.items() if v is not None and v != ""}
        return self._request("POST", table, json_data={"fields": clean_fields})

    def update(self, table: str, record_id: str, fields: Dict) -> Dict:
        clean_fields = {k: (None if v == "" else v) for k, v in fields.items() if v is not None}
        return self._request("PATCH", f"{table}/{record_id}",
                             json_data={"fields": clean_fields})

    def delete(self, table: str, record_id: str) -> Dict:
        return self._request("DELETE", f"{table}/{record_id}")

    def get_record(self, table: str, record_id: str) -> Dict:
        return self._request("GET", f"{table}/{record_id}")

    def fetch_all(self, table: str, formula: Optional[str] = None,
                  sort: Optional[List] = None) -> List[Dict]:
        records = []
        offset = None
        params: Dict[str, Any] = {"pageSize": 100}
        if formula:
            params["filterByFormula"] = formula
        if sort:
            for i, s in enumerate(sort):
                params[f"sort[{i}][field]"] = s["field"]
                params[f"sort[{i}][direction]"] = s.get("direction", "asc")
        while True:
            if offset:
                params["offset"] = offset
            data = self._request("GET", table, params=params)
            records.extend(data.get("records", []))
            offset = data.get("offset")
            if not offset:
                break
        return records


__all__ = ["AirtableClient"]
