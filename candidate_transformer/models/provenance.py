from datetime import datetime
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar('T')

class Provenance(BaseModel):
    """
    Tracks the source and method used to extract a specific field.
    """
    model_config = ConfigDict(frozen=True)

    field: str = Field(..., description="The name of the field this provenance applies to.")
    source: str = Field(..., description="The source file or API the data was extracted from.")
    method: str = Field(..., description="The extraction technique (e.g., 'Regex', 'Direct Import', 'Fuzzy Matching').")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="The timestamp when the data was extracted.")


class FieldMetadata(BaseModel, Generic[T]):
    """
    A wrapper that couples a field's value with its confidence score and provenance.
    """
    model_config = ConfigDict(frozen=True)

    value: T = Field(..., description="The actual normalized field value.")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0.")
    provenance: Provenance = Field(..., description="Provenance information for this specific extraction.")
