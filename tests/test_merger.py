import pytest
from datetime import datetime
from typing import Any
from candidate_transformer.models.provenance import FieldMetadata, Provenance
from candidate_transformer.models.canonical import WorkExperience, Education
from candidate_transformer.models.intermediate import IntermediateCandidate
from candidate_transformer.mergers.merger import CandidateMerger

def make_meta(field: str, value: Any, source: str, confidence: float) -> FieldMetadata:
    return FieldMetadata(
        value=value,
        confidence=confidence,
        provenance=Provenance(
            field=field,
            source=source,
            method="Test",
            timestamp=datetime.utcnow()
        )
    )

def test_merger_scalar_priority():
    merger = CandidateMerger(source_priority=["ats", "csv", "pdf", "txt"])
    
    # 1. ATS (priority 0) vs PDF (priority 2) -> ATS wins
    meta_ats = make_meta("full_name", "Jane Doe", "ats.json", 0.99)
    meta_pdf = make_meta("full_name", "Jane S. Doe", "resume.pdf", 0.78)
    
    cand1 = IntermediateCandidate(full_name=meta_ats)
    cand2 = IntermediateCandidate(full_name=meta_pdf)
    
    result = merger.merge([cand1, cand2])
    assert result["full_name"].value == "Jane Doe"
    assert result["full_name"].provenance.source == "ats.json"

    # 2. ATS is missing Name, CSV has it -> CSV wins
    meta_csv = make_meta("full_name", "Jane Smith", "recruiter.csv", 0.95)
    cand_ats_empty = IntermediateCandidate(full_name=None)
    cand_csv = IntermediateCandidate(full_name=meta_csv)
    
    result_fallback = merger.merge([cand_ats_empty, cand_csv])
    assert result_fallback["full_name"].value == "Jane Smith"
    assert result_fallback["full_name"].provenance.source == "recruiter.csv"

def test_merger_list_deduplication():
    merger = CandidateMerger(source_priority=["ats", "csv", "pdf", "txt"])
    
    # Duplicate emails with different metadata
    email_ats = make_meta("emails", "alex@example.com", "ats.json", 0.99)
    email_pdf = make_meta("emails", "alex@example.com", "resume.pdf", 0.78)
    email_pdf_other = make_meta("emails", "alex.other@example.com", "resume.pdf", 0.78)
    
    cand1 = IntermediateCandidate(emails=[email_ats])
    cand2 = IntermediateCandidate(emails=[email_pdf, email_pdf_other])
    
    result = merger.merge([cand1, cand2])
    
    # Check that emails are deduplicated and size is 2
    assert len(result["emails"]) == 2
    
    # The duplicate 'alex@example.com' must retain ATS metadata
    alex_meta = [e for e in result["emails"] if e.value == "alex@example.com"][0]
    assert alex_meta.provenance.source == "ats.json"
    assert alex_meta.confidence == 0.99

def test_merger_work_experience():
    merger = CandidateMerger(source_priority=["ats", "csv", "pdf", "txt"])
    
    # Company "Tech Corp" and "Tech Corp Inc." are fuzzy-matched as same company.
    # ATS: Company="Tech Corp", Title="Software Engineer", Desc=None
    # PDF: Company="Tech Corp Inc.", Title="SWE II", Desc="Built cool API services"
    job_ats = WorkExperience(company="Tech Corp", title="Software Engineer", start_date="2020-01", end_date="2023-04", description=None)
    job_pdf = WorkExperience(company="Tech Corp Inc.", title="SWE II", start_date="2020-01", end_date="2023-04", description="Built cool API services")
    
    meta_ats = make_meta("experience", job_ats, "ats.json", 0.99)
    meta_pdf = make_meta("experience", job_pdf, "resume.pdf", 0.78)
    
    cand1 = IntermediateCandidate(experience=[meta_ats])
    cand2 = IntermediateCandidate(experience=[meta_pdf])
    
    result = merger.merge([cand1, cand2])
    
    # They should be merged into a single work experience entry
    assert len(result["experience"]) == 1
    merged_job = result["experience"][0].value
    
    # Check prioritization: company, title from ATS. description falls back to PDF because ATS was None.
    assert merged_job.company == "Tech Corp"
    assert merged_job.title == "Software Engineer"
    assert merged_job.description == "Built cool API services"
    # Merged field should retain ATS provenance metadata
    assert result["experience"][0].provenance.source == "ats.json"
    assert result["experience"][0].confidence == 0.99
