import pytest
from datetime import datetime
from candidate_transformer.models.provenance import FieldMetadata, Provenance
from candidate_transformer.models.canonical import CanonicalCandidate, WorkExperience, Education
from candidate_transformer.projection.projector import SchemaProjector, ProjectionError

def test_projector_basic():
    # Setup test CanonicalCandidate
    prov = Provenance(field="test", source="ats.json", method="test", timestamp=datetime.utcnow())
    candidate = CanonicalCandidate(
        candidate_id="uuid-1234",
        full_name=FieldMetadata(value="John Doe", confidence=0.99, provenance=prov),
        emails=[
            FieldMetadata(value="john.doe@example.com", confidence=0.99, provenance=prov),
            FieldMetadata(value="john.work@example.com", confidence=0.95, provenance=prov)
        ],
        phones=[],
        location=None,
        links=[],
        headline=FieldMetadata(value="Staff Engineer", confidence=0.99, provenance=prov),
        years_experience=None,
        skills=[FieldMetadata(value="Python", confidence=0.99, provenance=prov)],
        experience=[
            FieldMetadata(
                value=WorkExperience(company="Google", title="SWE II", start_date="2020-01", end_date="2022-01"),
                confidence=0.99,
                provenance=prov
            )
        ],
        education=[],
        provenance=[],
        overall_confidence=0.97
    )

    # 1. Test Project without confidence values (flat values output)
    config = {
        "fields": [
            {"path": "full_name"},
            {"path": "primary_email", "from": "emails[0]"},
            {"path": "secondary_email", "from": "emails[1]"},
            {"path": "current_company", "from": "experience[0].company"},
            {"path": "missing_phone", "from": "phones[0]"}
        ],
        "include_confidence": False,
        "on_missing": "null"
    }

    projector = SchemaProjector(config)
    output = projector.project(candidate)
    
    assert output["full_name"] == "John Doe"
    assert output["primary_email"] == "john.doe@example.com"
    assert output["secondary_email"] == "john.work@example.com"
    assert output["current_company"] == "Google"
    assert output["missing_phone"] is None

    # 2. Test Project with confidence values
    config_conf = {
        "fields": [
            {"path": "full_name"},
            {"path": "primary_email", "from": "emails[0]"}
        ],
        "include_confidence": True,
        "on_missing": "null"
    }
    projector_conf = SchemaProjector(config_conf)
    output_conf = projector_conf.project(candidate)
    
    assert isinstance(output_conf["full_name"], dict)
    assert output_conf["full_name"]["value"] == "John Doe"
    assert output_conf["full_name"]["confidence"] == 0.99
    assert output_conf["primary_email"]["value"] == "john.doe@example.com"
    assert output_conf["primary_email"]["confidence"] == 0.99

def test_projector_missing_policies():
    prov = Provenance(field="test", source="ats.json", method="test", timestamp=datetime.utcnow())
    candidate = CanonicalCandidate(
        candidate_id="uuid-1234",
        full_name=None, # Missing name
        emails=[],
        phones=[],
        location=None,
        links=[],
        headline=None,
        years_experience=None,
        skills=[],
        experience=[],
        education=[],
        provenance=[],
        overall_confidence=1.0
    )

    # Policy: omit
    config_omit = {
        "fields": [
            {"path": "full_name"}
        ],
        "include_confidence": False,
        "on_missing": "omit"
    }
    projector_omit = SchemaProjector(config_omit)
    output_omit = projector_omit.project(candidate)
    assert "full_name" not in output_omit

    # Policy: error
    config_error = {
        "fields": [
            {"path": "full_name"}
        ],
        "include_confidence": False,
        "on_missing": "error"
    }
    projector_error = SchemaProjector(config_error)
    with pytest.raises(ProjectionError):
        projector_error.project(candidate)
