import logging
from typing import Any, Dict, List, TypeVar
from candidate_transformer.models.provenance import FieldMetadata, Provenance

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ProvenanceTracker:
    """
    Handles provenance tracking, field mutation metadata updates,
    and collation of field-level provenance records into the canonical candidate.
    """

    @staticmethod
    def track_transformation(meta: FieldMetadata[T], method_suffix: str) -> FieldMetadata[T]:
        """
        Returns a new FieldMetadata object with the value preserved, but the provenance method
        updated to reflect the normalization or transformation applied.
        """
        if not meta:
            return meta

        updated_provenance = Provenance(
            field=meta.provenance.field,
            source=meta.provenance.source,
            method=f"{meta.provenance.method} -> {method_suffix}",
            timestamp=meta.provenance.timestamp
        )
        
        # We construct a new FieldMetadata keeping the original value/confidence but updating provenance
        return FieldMetadata(
            value=meta.value,
            confidence=meta.confidence,
            provenance=updated_provenance
        )

    @staticmethod
    def collate_provenance(candidate_fields: Dict[str, Any]) -> List[Provenance]:
        """
        Traverses candidate attributes, extracts all FieldMetadata provenance blocks,
        and returns a deduplicated list of Provenance records representing the complete candidate profile history.
        """
        provenance_list: List[Provenance] = []
        seen_keys = set()

        def add_provenance(prov: Provenance):
            # Check unique by field, source, and method
            unique_key = (prov.field, prov.source, prov.method)
            if unique_key not in seen_keys:
                seen_keys.add(unique_key)
                provenance_list.append(prov)

        for field_name, value in candidate_fields.items():
            # Check if it's a direct FieldMetadata wrapper
            if isinstance(value, FieldMetadata):
                add_provenance(value.provenance)
            # Check if it's a list containing FieldMetadata wrappers (like emails, phones, skills, exp, edu)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, FieldMetadata):
                        add_provenance(item.provenance)

        # Sort provenances by field and source for predictable output ordering
        provenance_list.sort(key=lambda p: (p.field, p.source))
        return provenance_list
