import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, List, Optional, Union
from candidate_transformer.models.provenance import FieldMetadata, Provenance
from candidate_transformer.models.canonical import WorkExperience, Education
from candidate_transformer.models.intermediate import IntermediateCandidate
from candidate_transformer.extractors.base import BaseExtractor
from candidate_transformer.config import EMAIL_PATTERN, PHONE_PATTERN, LINK_PATTERN, SKILL_VOCABULARY

logger = logging.getLogger(__name__)

class TXTNotesExtractor(BaseExtractor):
    """
    Extracts candidate data from Recruiter Notes text files.
    Parses unstructured text using pattern matching for labels and entities.
    """

    def __init__(self, confidence_score: float = 0.70):
        self.confidence_score = confidence_score

    def extract(self, source: Union[Path, str, Any]) -> IntermediateCandidate:
        if isinstance(source, (str, Path)):
            source_name = Path(source).name
        elif hasattr(source, "name"):
            source_name = Path(source.name).name
        else:
            source_name = "stream.txt"

        logger.info(f"Extracting TXT notes data from {source_name}")

        try:
            if isinstance(source, (str, Path)):
                with open(source, "r", encoding="utf-8") as f:
                    text = f.read()
            else:
                text = source.read()
                if isinstance(text, bytes):
                    text = text.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to read TXT source {source_name}: {e}")
            return IntermediateCandidate()

        if not text.strip():
            logger.warning(f"TXT source {source_name} is empty.")
            return IntermediateCandidate()

        # Helper function to wrap values in FieldMetadata
        def make_meta(field_name: str, value: Any, method: str = "Notes Text Parsing") -> FieldMetadata:
            return FieldMetadata(
                value=value,
                confidence=self.confidence_score,
                provenance=Provenance(
                    field=field_name,
                    source=source_name,
                    method=method,
                    timestamp=datetime.utcnow()
                )
            )

        # 1. Full Name: Look for "Candidate: [Name]" or "Name: [Name]"
        full_name = None
        name_match = re.search(r'(?:candidate|name):\s*([^\n\r]+)', text, re.IGNORECASE)
        if name_match:
            full_name = make_meta("full_name", name_match.group(1).strip())

        # 2. Emails: Regex scan
        emails = []
        found_emails = re.findall(EMAIL_PATTERN, text)
        for email in found_emails:
            emails.append(make_meta("emails", email.strip()))

        # 3. Phones: Regex scan
        phones = []
        found_phones = re.findall(PHONE_PATTERN, text)
        for phone in found_phones:
            phones.append(make_meta("phones", phone.strip()))

        # 4. Links: Look for URLs
        links = []
        found_links = re.findall(LINK_PATTERN, text)
        for link in found_links:
            links.append(make_meta("links", link.strip()))

        # 5. Headline: Look for "Headline: [Headline]" or "Summary: [Summary]"
        headline = None
        headline_match = re.search(r'(?:headline|summary|title):\s*([^\n\r]+)', text, re.IGNORECASE)
        if headline_match:
            headline = make_meta("headline", headline_match.group(1).strip())

        # 6. Location: Look for "Location: [Location]" or "Address: [Address]"
        location = None
        location_match = re.search(r'(?:location|address|city):\s*([^\n\r]+)', text, re.IGNORECASE)
        if location_match:
            location = make_meta("location", location_match.group(1).strip())

        # 7. Years of Experience: Match patterns like "6 years experience" or "8+ yrs of experience"
        years_experience = None
        exp_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:years|yrs)\s*(?:of)?\s*experience', text, re.IGNORECASE)
        if exp_match:
            try:
                years_experience = make_meta("years_experience", float(exp_match.group(1)))
            except ValueError:
                pass

        # 8. Skills: Look for "Skills: [Skills]" or check text for keywords
        skills = []
        skills_match = re.search(r'(?:skills|technologies|tech\s*stack)(?:\s+include|\s*:)\s*([^\n\r]+)', text, re.IGNORECASE)
        if skills_match:
            skills_str = skills_match.group(1).strip()
            # Split by comma or semicolon
            for s in re.split(r'[,;]', skills_str):
                cleaned = s.strip()
                if cleaned:
                    skills.append(make_meta("skills", cleaned))
        else:
            # Fallback to vocabulary lookup
            text_lower = text.lower()
            for skill_vocab in SKILL_VOCABULARY:
                pattern = rf'\b{re.escape(skill_vocab)}\b'
                if skill_vocab in ["c++", "cpp", "c#"]:
                    pattern = rf'(?:^|\s|/){re.escape(skill_vocab)}(?:$|\s|,|\.)'
                if re.search(pattern, text_lower):
                    skills.append(make_meta("skills", skill_vocab))

        # 9. Experience / Education Paragraph Parser
        experience = []
        education = []

        # Find sentences containing job patterns, e.g.:
        # "He worked at Cloud Inc. from 2021-03 to 2024-05 as a Site Reliability Engineer."
        # "worked at [Company] as [Title] ([Start] to [End])"
        # Let's search using regular expressions for company-date-title patterns
        job_pattern = r'(?:worked at|at)\s+([A-Z][A-Za-z0-9\s\.\,]+?)\s+(?:from|since)?\s*(\d{4}-\d{2}|\d{4})\s+to\s+(\d{4}-\d{2}|\d{4}|Present)\s+(?:as a|as)\s+([A-Za-z\s]+)'
        job_matches = re.finditer(job_pattern, text, re.IGNORECASE)
        for match in job_matches:
            comp = match.group(1).strip()
            start = match.group(2).strip()
            end = match.group(3).strip()
            title = match.group(4).strip()
            
            work = WorkExperience(
                company=comp,
                title=title,
                start_date=start,
                end_date=end,
                description=None
            )
            experience.append(make_meta("experience", work, method="Notes Job RegEx"))

        # Education match, e.g.:
        # "B.S. in Info Tech from State College (2014-09 to 2018-05)"
        # "[Degree] in [Major] from [School] ([Start] to [End])"
        edu_pattern = r'([A-Za-z\.\s]{2,10})\s+in\s+([A-Za-z\s]+?)\s+from\s+([A-Za-z0-9\s]+?)\s*\(\s*(\d{4}-\d{2}|\d{4})\s+to\s+(\d{4}-\d{2}|\d{4})\s*\)'
        edu_matches = re.finditer(edu_pattern, text, re.IGNORECASE)
        for match in edu_matches:
            deg = match.group(1).strip()
            major = match.group(2).strip()
            inst = match.group(3).strip()
            start = match.group(4).strip()
            end = match.group(5).strip()

            edu = Education(
                institution=inst,
                degree=deg,
                major=major,
                start_date=start,
                end_date=end
            )
            education.append(make_meta("education", edu, method="Notes Edu RegEx"))

        return IntermediateCandidate(
            full_name=full_name,
            emails=emails,
            phones=phones,
            location=location,
            links=links,
            headline=headline,
            years_experience=years_experience,
            skills=skills,
            experience=experience,
            education=education
        )
