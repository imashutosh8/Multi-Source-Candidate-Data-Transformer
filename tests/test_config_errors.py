import pytest
from pathlib import Path
from candidate_transformer.config.pipeline_config import PipelineConfig
from candidate_transformer.orchestrator import CandidateTransformerOrchestrator, ExtractionError

def test_pipeline_config_defaults():
    config = PipelineConfig()
    assert config.failure_policy == "best_effort"
    assert config.source_priority == ["ats", "csv", "pdf", "txt"]
    assert config.confidence_weights is None

def test_best_effort_missing_file_does_not_raise():
    # Under best_effort, the pipeline logs a warning and proceeds as long as at least one source succeeded.
    config = PipelineConfig(failure_policy="best_effort")
    orchestrator = CandidateTransformerOrchestrator(config=config)
    
    # We pass a valid ATS JSON and a non-existent CSV path
    valid_ats = Path("data/ats.json")
    invalid_csv = Path("data/non_existent.csv")
    
    # This should run successfully and return output without raising ExtractionError
    result = orchestrator.run(
        ats_path=valid_ats,
        csv_path=invalid_csv
    )
    assert result is not None
    assert result["full_name"] == "Ashutosh Verma"

def test_fail_fast_missing_file_raises():
    # Under fail_fast, any missing file path raises ExtractionError
    config = PipelineConfig(failure_policy="fail_fast")
    orchestrator = CandidateTransformerOrchestrator(config=config)
    
    valid_ats = Path("data/ats.json")
    invalid_csv = Path("data/non_existent.csv")
    
    with pytest.raises(ExtractionError):
        orchestrator.run(
            ats_path=valid_ats,
            csv_path=invalid_csv
        )
