from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

class PipelineConfig(BaseModel):
    """
    Configuration options that govern the Candidate Transformer pipeline execution.
    Controls error handling, priority of sources, and confidence calculations.
    """
    model_config = ConfigDict(frozen=True)

    # Policy for when extracting from a specific file throws a parsing error or missing file
    # - "best_effort": Log warning and proceed with other files
    # - "fail_fast": Raise exception and terminate pipeline
    failure_policy: Literal["best_effort", "fail_fast"] = Field(
        default="best_effort",
        description="Behavior when parsing/extracting a source file fails."
    )

    # Lower index = higher priority for conflict resolution
    source_priority: List[str] = Field(
        default_factory=lambda: ["ats", "csv", "pdf", "txt"],
        description="Fuzzy filename keywords determining resolving priority."
    )

    # Weights used by the overall confidence calculator
    confidence_weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Custom weight overrides for candidate fields in overall score computation."
    )
