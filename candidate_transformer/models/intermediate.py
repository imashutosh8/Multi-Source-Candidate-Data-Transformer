from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from candidate_transformer.models.provenance import FieldMetadata
from candidate_transformer.models.canonical import WorkExperience, Education

class IntermediateCandidate(BaseModel):
    """
    A representation of candidate data extracted from a single source.
    All fields are wrapped in FieldMetadata to track source, extraction method,
    and confidence scores for each extracted value.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    full_name: Optional[FieldMetadata[str]] = Field(None, description="Extracted full name.")
    emails: List[FieldMetadata[str]] = Field(default_factory=list, description="Extracted email addresses.")
    phones: List[FieldMetadata[str]] = Field(default_factory=list, description="Extracted phone numbers.")
    location: Optional[FieldMetadata[str]] = Field(None, description="Extracted location.")
    links: List[FieldMetadata[str]] = Field(default_factory=list, description="Extracted professional or social links.")
    headline: Optional[FieldMetadata[str]] = Field(None, description="Extracted headline or summary.")
    years_experience: Optional[FieldMetadata[float]] = Field(None, description="Extracted years of experience.")
    skills: List[FieldMetadata[str]] = Field(default_factory=list, description="Extracted candidate skills.")
    experience: List[FieldMetadata[WorkExperience]] = Field(default_factory=list, description="Extracted work experience entries.")
    education: List[FieldMetadata[Education]] = Field(default_factory=list, description="Extracted education entries.")
