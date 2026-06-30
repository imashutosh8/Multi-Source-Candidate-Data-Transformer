from candidate_transformer.normalizers.base import BaseNormalizer

class EmailNormalizer(BaseNormalizer):
    """
    Normalizes email addresses by trimming whitespace and converting to lowercase.
    """
    def normalize(self, value: str) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip().lower()
