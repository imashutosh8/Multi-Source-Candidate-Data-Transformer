import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from candidate_transformer.models.provenance import FieldMetadata, Provenance
from candidate_transformer.models.canonical import WorkExperience, Education
from candidate_transformer.models.intermediate import IntermediateCandidate
from candidate_transformer.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class JSONExtractor(BaseExtractor):
    """
    Extracts candidate data from a structured ATS JSON file.
    Assumes standard nested structured candidate formats.
    """

    def __init__(self, confidence_score: float = 0.99):
        self.confidence_score = confidence_score

    def _resolve_key(self, data: Dict[str, Any], path: List[str]) -> Optional[Any]:
        """Resolves a nested key in a dictionary using a list of keys."""
        current = data
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    def extract(self, source: Union[Path, str, Any]) -> IntermediateCandidate:
        if isinstance(source, (str, Path)):
            source_name = Path(source).name
        elif hasattr(source, "name"):
            source_name = Path(source.name).name
        else:
            source_name = "stream.json"

        logger.info(f"Extracting JSON candidate data from {source_name}")

        try:
            if isinstance(source, (str, Path)):
                with open(source, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = json.load(source)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format in {source_name}: {e}")
            return IntermediateCandidate()
        except Exception as e:
            logger.error(f"Failed to read JSON source {source_name}: {e}")
            return IntermediateCandidate()

        # Helper function to wrap values in FieldMetadata
        def make_meta(field_name: str, value: Any, method: str = "JSON ATS Import") -> FieldMetadata:
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

        # 1. Full Name
        raw_name = data.get("full_name") or data.get("name") or data.get("candidate_name")
        full_name = make_meta("full_name", str(raw_name)) if raw_name else None

        # 2. Emails
        emails = []
        raw_emails = data.get("emails") or data.get("email") or self._resolve_key(data, ["contact", "emails"]) or self._resolve_key(data, ["contact", "email"])
        if raw_emails:
            email_list = [raw_emails] if isinstance(raw_emails, str) else raw_emails
            for email in email_list:
                if email and isinstance(email, str):
                    emails.append(make_meta("emails", email.strip()))

        # 3. Phones
        phones = []
        raw_phones = data.get("phones") or data.get("phone") or self._resolve_key(data, ["contact", "phones"]) or self._resolve_key(data, ["contact", "phone"])
        if raw_phones:
            phone_list = [raw_phones] if isinstance(raw_phones, str) else raw_phones
            for phone in phone_list:
                if phone and isinstance(phone, str):
                    phones.append(make_meta("phones", phone.strip()))

        # 4. Location
        raw_location = data.get("location") or self._resolve_key(data, ["contact", "location"])
        location = make_meta("location", str(raw_location)) if raw_location else None

        # 5. Links
        links = []
        raw_links = data.get("links") or data.get("websites") or self._resolve_key(data, ["contact", "links"])
        if raw_links:
            link_list = [raw_links] if isinstance(raw_links, str) else raw_links
            for link in link_list:
                if link and isinstance(link, str):
                    links.append(make_meta("links", link.strip()))

        # 6. Headline
        raw_headline = data.get("headline") or data.get("title") or data.get("summary")
        headline = make_meta("headline", str(raw_headline)) if raw_headline else None

        # 7. Years of Experience
        raw_exp = data.get("years_experience") or data.get("experience_years") or data.get("total_experience")
        years_experience = None
        if raw_exp is not None:
            try:
                years_experience = make_meta("years_experience", float(raw_exp))
            except ValueError:
                logger.warning(f"Could not parse years_experience '{raw_exp}' as float.")

        # 8. Skills
        skills = []
        raw_skills = data.get("skills") or data.get("technologies") or data.get("skillset")
        if raw_skills:
            skill_list = raw_skills if isinstance(raw_skills, list) else [raw_skills]
            for skill in skill_list:
                if skill and isinstance(skill, str):
                    skills.append(make_meta("skills", skill.strip()))

        # 9. Experience
        experience = []
        # Support jobs list in various schemas
        raw_jobs = (
            data.get("experience") or 
            data.get("jobs") or 
            self._resolve_key(data, ["history", "jobs"]) or 
            self._resolve_key(data, ["history", "experience"])
        )
        if isinstance(raw_jobs, list):
            for job in raw_jobs:
                if isinstance(job, dict):
                    comp = job.get("company") or job.get("employer") or "Unknown Company"
                    title = job.get("title") or job.get("role")
                    start = job.get("start_date") or job.get("start")
                    end = job.get("end_date") or job.get("end")
                    desc = job.get("description") or job.get("desc")

                    work = WorkExperience(
                        company=str(comp),
                        title=str(title) if title else None,
                        start_date=str(start) if start else None,
                        end_date=str(end) if end else None,
                        description=str(desc) if desc else None
                    )
                    experience.append(make_meta("experience", work, method="JSON Job Parsing"))

        # 10. Education
        education = []
        # Support education list in various schemas
        raw_schools = (
            data.get("education") or 
            data.get("schools") or 
            self._resolve_key(data, ["history", "schools"]) or 
            self._resolve_key(data, ["history", "education"])
        )
        if isinstance(raw_schools, list):
            for school in raw_schools:
                if isinstance(school, dict):
                    inst = school.get("institution") or school.get("school") or school.get("university") or school.get("college")
                    if inst:
                        deg = school.get("degree")
                        major = school.get("major") or school.get("field") or school.get("field_of_study")
                        start = school.get("start_date") or school.get("start")
                        end = school.get("end_date") or school.get("end")

                        edu = Education(
                            institution=str(inst),
                            degree=str(deg) if deg else None,
                            major=str(major) if major else None,
                            start_date=str(start) if start else None,
                            end_date=str(end) if end else None
                        )
                        education.append(make_meta("education", edu, method="JSON Education Parsing"))

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
