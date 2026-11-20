"""Optional MaxMind country lookup. Missing databases produce unknown data."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def lookup_country(ip_value: str | None, database_path: str | None = None) -> dict[str, Any]:
    if not ip_value:
        return {"country_code": None, "country_name": None, "geoip_checked_at": None}
    path_value = database_path or os.environ.get("GEOIP_DB", "")
    if not path_value or not Path(path_value).is_file():
        return {"country_code": None, "country_name": None, "geoip_checked_at": None}
    try:
        import maxminddb  # type: ignore[import-not-found]

        from engine.models import iso_utc

        with maxminddb.open_database(path_value) as reader:
            result = reader.get(ip_value) or {}
        country = result.get("country", {}).get("iso_code") or result.get("registered_country", {}).get("iso_code")
        names = result.get("country", {}).get("names", {})
        return {
            "country_code": str(country).upper() if country else None,
            "country_name": names.get("en") if country else None,
            "geoip_checked_at": iso_utc(),
        }
    except (ImportError, OSError, ValueError):
        return {"country_code": None, "country_name": None, "geoip_checked_at": None}
