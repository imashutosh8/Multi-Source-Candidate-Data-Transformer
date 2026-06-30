from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from candidate_transformer.models.provenance import FieldMetadata, Provenance

class WorkExperience(BaseModel):
    """
    Represents a candidate's employment history.
    """
    model_config = ConfigDict(frozen=True)

    company: str = Field(..., description="Name of the company or organization.")
    title: Optional[str] = Field(None, description="Job title.")
    start_date: Optional[str] = Field(None, description="Start date in YYYY-MM format.")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM format, or 'Present'.")
    description: Optional[str] = Field(None, description="Description of responsibilities and achievements.")


class Education(BaseModel):
    """
    Represents a candidate's academic history.
    """
    model_config = ConfigDict(frozen=True)

    institution: str = Field(..., description="Name of the school, college, or university.")
    degree: Optional[str] = Field(None, description="Degree obtained (e.g., B.S., M.S., Ph.D.).")
    major: Optional[str] = Field(None, description="Field of study or major.")
    start_date: Optional[str] = Field(None, description="Start date in YYYY-MM format.")
    end_date: Optional[str] = Field(None, description="Completion date in YYYY-MM format.")


class CanonicalCandidate(BaseModel):
    """
    The canonical, unified representation of a candidate's profile.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    candidate_id: str = Field(..., description="Unique identifier for the canonical candidate profile.")
    full_name: Optional[FieldMetadata[str]] = Field(None, description="Full name of the candidate.")
    emails: List[FieldMetadata[str]] = Field(default_factory=list, description="Deduplicated list of email addresses.")
    phones: List[FieldMetadata[str]] = Field(default_factory=list, description="Deduplicated list of E.164 phone numbers.")
    location: Optional[FieldMetadata[str]] = Field(None, description="Location of the candidate.")
    links: List[FieldMetadata[str]] = Field(default_factory=list, description="Deduplicated candidate links (GitHub, LinkedIn, websites).")
    headline: Optional[FieldMetadata[str]] = Field(None, description="Professional headline or summary.")
    years_experience: Optional[FieldMetadata[float]] = Field(None, description="Total years of work experience.")
    skills: List[FieldMetadata[str]] = Field(default_factory=list, description="Normalized candidate skills.")
    experience: List[FieldMetadata[WorkExperience]] = Field(default_factory=list, description="Unified work history.")
    education: List[FieldMetadata[Education]] = Field(default_factory=list, description="Unified education history.")
    provenance: List[Provenance] = Field(default_factory=list, description="Aggregated history of all fields and sources.")
    overall_confidence: float = Field(0.0, description="Overall candidate profile confidence score.")
