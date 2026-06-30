import re
import logging
from dateutil import parser
from candidate_transformer.normalizers.base import BaseNormalizer

logger = logging.getLogger(__name__)

class DateNormalizer(BaseNormalizer):
    """
    Normalizes dates from various free-text formats into a standard YYYY-MM format.
    Handles 'Present' or 'current' ongoing tags.
    """
    def normalize(self, value: str) -> str:
        if not isinstance(value, str):
            return ""
        
        cleaned = value.strip()
        if not cleaned:
            return ""

        # Normalize ongoing marker
        if cleaned.lower() in ["present", "current", "now", "ongoing", "till date"]:
            return "Present"

        # Check if it's already in YYYY-MM format
        if re.match(r'^\d{4}-\d{2}$', cleaned):
            return cleaned

        # Check if it is a pure 4-digit year, e.g. "2021" -> "2021-01"
        if re.match(r'^\d{4}$', cleaned):
            return f"{cleaned}-01"

        try:
            # Parse with dateutil parser
            from datetime import datetime
            default_dt = datetime(2026, 1, 1)  # Default missing parts to Jan 1st
            parsed_dt = parser.parse(cleaned, fuzzy=True, default=default_dt)
            return parsed_dt.strftime("%Y-%m")
        except Exception as e:
            logger.debug(f"dateutil failed to parse date string '{value}': {e}")

        # Manual regex fallback for common structures like MM/YYYY
        slash_match = re.search(r'\b(0?[1-9]|1[0-2])/(19|20)?(\d{2})\b', cleaned)
        if slash_match:
            month = int(slash_match.group(1))
            year_suffix = slash_match.group(3)
            century = slash_match.group(2) or "20"
            full_year = f"{century}{year_suffix}" if len(year_suffix) == 2 else year_suffix
            return f"{full_year}-{month:02d}"

        # If a 4-digit year can be found anywhere, default to that year + January
        year_match = re.search(r'\b((?:19|20)\d{2})\b', cleaned)
        if year_match:
            return f"{year_match.group(1)}-01"

        return cleaned
