import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class ValidationRule(BaseModel):
    """
    Defines validation constraints for a specific field in the projected output.
    """
    field: str = Field(..., description="The name of the field to validate.")
    required: bool = Field(False, description="Whether the field is required to be present and non-null.")
    type: Optional[str] = Field(None, description="Expected type: 'string', 'number', 'list', 'email', 'phone'.")
    min_length: Optional[int] = Field(None, description="Minimum length for string or list values.")
    pattern: Optional[str] = Field(None, description="Regex pattern to validate string values.")


class ValidationSchema(BaseModel):
    """
    Holds a list of validation rules for checking projected candidate JSON.
    """
    rules: List[ValidationRule] = Field(default_factory=list)


class ValidationError(Exception):
    """Exception raised when validation fails."""
    def __init__(self, errors: List[str]):
        super().__init__(f"Validation failed with errors: {errors}")
        self.errors = errors


class OutputValidator:
    """
    Validates projected candidate dictionaries against a specified ValidationSchema.
    Reports detailed errors for missing required fields, type mismatches, or invalid formats.
    """

    def __init__(self, schema: ValidationSchema):
        self.schema = schema

    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validates the projected data.
        Returns a tuple (is_valid, list_of_error_messages).
        """
        errors = []

        for rule in self.schema.rules:
            field = rule.field
            val = data.get(field)
            
            # Check if field is fully omitted or null (None)
            is_omitted = field not in data
            is_null = val is None

            # 1. Required check
            if rule.required:
                if is_omitted:
                    errors.append(f"Required field '{field}' is omitted from the projected output.")
                    continue
                if is_null:
                    errors.append(f"Required field '{field}' is null.")
                    continue
            
            # If the field is not required and is null/omitted, skip further type checks
            if is_null or is_omitted:
                continue

            # 2. Type validation
            if rule.type:
                # If include_confidence is True, the projected field value is wrapped in a dict:
                # e.g., {"value": "John Doe", "confidence": 0.99, ...}
                # We extract the inner value for type checking.
                inner_val = val
                is_wrapped = isinstance(val, dict) and "value" in val and "confidence" in val
                if is_wrapped:
                    inner_val = val["value"]

                if inner_val is None:
                    # If the inner value is null, type check passes but print warning if required
                    if rule.required:
                        errors.append(f"Required field '{field}' has a null value inside its confidence wrapper.")
                    continue

                if rule.type == "string":
                    if not isinstance(inner_val, str):
                        errors.append(f"Field '{field}' expected type 'string', got '{type(inner_val).__name__}'.")
                    else:
                        # Check min length
                        if rule.min_length is not None and len(inner_val) < rule.min_length:
                            errors.append(f"Field '{field}' string length ({len(inner_val)}) is less than minimum {rule.min_length}.")
                        # Check regex pattern
                        if rule.pattern:
                            if not re.match(rule.pattern, inner_val):
                                errors.append(f"Field '{field}' value '{inner_val}' does not match pattern '{rule.pattern}'.")

                elif rule.type == "number":
                    if not isinstance(inner_val, (int, float)):
                        errors.append(f"Field '{field}' expected type 'number', got '{type(inner_val).__name__}'.")

                elif rule.type == "list":
                    if not isinstance(inner_val, list):
                        errors.append(f"Field '{field}' expected type 'list', got '{type(inner_val).__name__}'.")
                    else:
                        if rule.min_length is not None and len(inner_val) < rule.min_length:
                            errors.append(f"Field '{field}' list size ({len(inner_val)}) is less than minimum {rule.min_length}.")

                elif rule.type == "email":
                    if not isinstance(inner_val, str):
                        errors.append(f"Email field '{field}' must be a string.")
                    elif not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', inner_val):
                        errors.append(f"Field '{field}' has invalid email format: '{inner_val}'.")

                elif rule.type == "phone":
                    if not isinstance(inner_val, str):
                        errors.append(f"Phone field '{field}' must be a string.")
                    # Standard check for E.164 phone formatting (starts with + followed by 7-15 digits)
                    elif not re.match(r'^\+\d{7,15}$', inner_val):
                        errors.append(f"Field '{field}' value '{inner_val}' is not a valid E.164 phone format.")

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning(f"Projected output validation failed with {len(errors)} errors.")
        else:
            logger.info("Projected output validation succeeded.")

        return is_valid, errors
