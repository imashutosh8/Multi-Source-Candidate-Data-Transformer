import re
from candidate_transformer.normalizers.base import BaseNormalizer

class NameNormalizer(BaseNormalizer):
    """
    Normalizes names by:
    1. Trimming leading and trailing whitespace.
    2. Collapsing repeated internal spaces.
    3. Standardizing to Title Case.
    """
    def normalize(self, value: str) -> str:
        if not isinstance(value, str):
            return ""
        # Collapse multiple spaces
        cleaned = re.sub(r'\s+', ' ', value.strip())
        # Apply Title Case
        return cleaned.title()
