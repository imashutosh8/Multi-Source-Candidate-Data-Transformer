import logging
from typing import Dict, Any, List, Optional
from candidate_transformer.models.provenance import FieldMetadata

logger = logging.getLogger(__name__)

class ConfidenceCalculator:
    """
    Computes field-level and overall candidate profile confidence scores.
    Uses a configurable weighted average approach where missing fields are penalized.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        # Default weights representing the business value and impact of each candidate field.
        # Identity and contact info are weighted highest.
        self.weights = weights or {
            "full_name": 0.25,
            "emails": 0.20,
            "phones": 0.15,
            "experience": 0.15,
            "education": 0.10,
            "skills": 0.08,
            "location": 0.03,
            "headline": 0.02,
            "years_experience": 0.02
        }
        
        # Normalize weights so they sum to 1.0
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            self.weights = {k: v / total_weight for k, v in self.weights.items()}
        else:
            logger.error("Sum of confidence weights is 0 or negative. Initializing to equal weights.")
            equal_weight = 1.0 / len(self.weights)
            self.weights = {k: equal_weight for k in self.weights}

    def _get_field_confidence(self, value: Any) -> float:
        """
        Determines the confidence score for a specific candidate field.
        Handles both individual FieldMetadata structures and lists of FieldMetadata.
        """
        if value is None:
            return 0.0

        if isinstance(value, FieldMetadata):
            return value.confidence

        if isinstance(value, list):
            if not value:
                return 0.0
            
            # Check if all items in list are FieldMetadata wrappers
            confidences = [item.confidence for item in value if isinstance(item, FieldMetadata)]
            if not confidences:
                return 0.0
            
            # For lists, return the average confidence of its items
            return sum(confidences) / len(confidences)

        return 0.0

    def calculate(self, candidate_fields: Dict[str, Any]) -> float:
        """
        Calculates the overall confidence score for a candidate profile based on field confidences.

        Args:
            candidate_fields (Dict[str, Any]): Dictionary of candidate fields.

        Returns:
            float: A float between 0.0 and 1.0 representing the overall profile confidence.
        """
        overall_score = 0.0

        for field_name, weight in self.weights.items():
            # Retrieve field value (can be a FieldMetadata or List[FieldMetadata])
            field_val = candidate_fields.get(field_name)
            field_confidence = self._get_field_confidence(field_val)
            
            contribution = field_confidence * weight
            overall_score += contribution
            
            logger.debug(f"Field '{field_name}': confidence={field_confidence:.2f}, weight={weight:.2f}, contribution={contribution:.3f}")

        logger.info(f"Calculated overall candidate profile confidence score: {overall_score:.4f}")
        return round(overall_score, 4)
