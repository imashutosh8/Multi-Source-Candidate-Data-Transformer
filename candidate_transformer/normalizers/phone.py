import logging
import phonenumbers
from candidate_transformer.normalizers.base import BaseNormalizer

logger = logging.getLogger(__name__)

class PhoneNormalizer(BaseNormalizer):
    """
    Normalizes phone numbers to the E.164 standard format using the phonenumbers package.
    Defaults to US region for parsing non-international numbers.
    """
    def __init__(self, default_region: str = "US"):
        self.default_region = default_region

    def normalize(self, value: str) -> str:
        if not isinstance(value, str):
            return ""
        
        cleaned = value.strip()
        if not cleaned:
            return ""

        try:
            # Parse the phone number
            parsed_number = phonenumbers.parse(cleaned, self.default_region)
            if phonenumbers.is_valid_number(parsed_number):
                return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
            else:
                logger.warning(f"Phone number '{value}' parsed but marked as invalid by phonenumbers library.")
        except Exception as e:
            logger.debug(f"Failed to parse phone number '{value}' using phonenumbers: {e}")

        # Fallback: remove spaces/dashes if it only contains digits and optional leading plus
        fallback_clean = "".join(c for c in cleaned if c.isdigit() or c == "+")
        return fallback_clean if fallback_clean else cleaned
