import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from candidate_transformer.models.provenance import FieldMetadata, Provenance
from candidate_transformer.models.canonical import CanonicalCandidate

logger = logging.getLogger(__name__)

class ProjectionError(Exception):
    """Raised when projection fails, e.g. when a required field is missing and policy is set to 'error'."""
    pass

class SchemaProjector:
    """
    Projects a CanonicalCandidate model into an output dictionary structured 
    according to a runtime JSON configuration.
    Supports field renaming, nested path extraction, and missing value policies.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.fields_config = config.get("fields", [])
        self.include_confidence = config.get("include_confidence", False)
        self.default_on_missing = config.get("on_missing", "null") # "null" | "omit" | "error"

    def _resolve_path(self, candidate: CanonicalCandidate, path: str) -> Tuple[Any, float, Optional[Provenance]]:
        """
        Dynamically resolves a path (like 'emails[0]' or 'experience[0].company') on CanonicalCandidate.
        Returns a tuple of (value, confidence, provenance).
        """
        parts = path.split('.')
        current: Any = candidate
        last_confidence = 1.0
        last_provenance = None

        for idx, part in enumerate(parts):
            if not current:
                return None, 0.0, None

            # Check for list index pattern: e.g. "emails[0]"
            index_match = re.match(r'^(\w+)\[(\d+)\]$', part)
            if index_match:
                attr_name = index_match.group(1)
                list_idx = int(index_match.group(2))

                # Fetch list
                current = getattr(current, attr_name, None)
                if not isinstance(current, list) or list_idx >= len(current):
                    return None, 0.0, None
                current = current[list_idx]
            else:
                # Direct attribute lookup
                current = getattr(current, part, None)

            # Unwrap FieldMetadata but keep its confidence and provenance
            if isinstance(current, FieldMetadata):
                last_confidence = current.confidence
                last_provenance = current.provenance
                # If there are more parts to resolve, we must unwrap to access nested attributes
                if idx < len(parts) - 1:
                    current = current.value

        # Final check: if the final resolved value is still a FieldMetadata wrapper, unwrap it
        if isinstance(current, FieldMetadata):
            return current.value, current.confidence, current.provenance

        return current, last_confidence, last_provenance

    def project(self, candidate: CanonicalCandidate) -> Dict[str, Any]:
        """
        Projects a CanonicalCandidate into a dictionary using the configured schema rules.
        """
        projected_output = {}

        for field_cfg in self.fields_config:
            # If "from" is specified, it maps from that candidate path to "path" (renaming).
            # If not, it uses "path" directly.
            source_path = field_cfg.get("from") or field_cfg.get("path")
            target_key = field_cfg.get("path")
            
            # Local override for missing policy
            field_on_missing = field_cfg.get("on_missing", self.default_on_missing)

            if not source_path or not target_key:
                logger.warning(f"Invalid field configuration skipped: {field_cfg}")
                continue

            value, confidence, provenance = self._resolve_path(candidate, source_path)

            # Handle Missing Values
            is_missing = (
                value is None or 
                (isinstance(value, list) and not value) or 
                (isinstance(value, str) and not value.strip())
            )

            if is_missing:
                if field_on_missing == "omit":
                    logger.info(f"Omit policy: skipping missing field '{target_key}' mapped from '{source_path}'")
                    continue
                elif field_on_missing == "error":
                    logger.error(f"Error policy: required field '{target_key}' mapped from '{source_path}' is missing.")
                    raise ProjectionError(f"Required field '{target_key}' is missing (source path: '{source_path}').")
                else: # "null"
                    value_to_write = None
            else:
                value_to_write = value

            # Format the output value
            if self.include_confidence and not is_missing:
                projected_output[target_key] = {
                    "value": self._strip_metadata(value_to_write),
                    "confidence": confidence,
                    "provenance": provenance.model_dump(mode='json') if provenance else None
                }
            else:
                # If we're not including confidence, check if value itself contains FieldMetadata lists (e.g. lists like skills)
                # and strip their metadata, returning only raw lists/objects
                projected_output[target_key] = self._strip_metadata(value_to_write)

        return projected_output

    def _strip_metadata(self, val: Any) -> Any:
        """Helper to recursively strip FieldMetadata wrappers to output clean raw JSON structures."""
        if isinstance(val, FieldMetadata):
            return self._strip_metadata(val.value)
        elif isinstance(val, list):
            return [self._strip_metadata(item) for item in val]
        elif isinstance(val, dict):
            return {k: self._strip_metadata(v) for k, v in val.items()}
        elif hasattr(val, "model_dump"): # Handles nested Pydantic models like WorkExperience or Education
            raw_dict = val.model_dump(mode='json')
            return self._strip_metadata(raw_dict)
        return val
