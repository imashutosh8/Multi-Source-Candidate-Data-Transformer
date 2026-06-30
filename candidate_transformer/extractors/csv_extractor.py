import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Any, List, Optional, Union
from candidate_transformer.models.provenance import FieldMetadata, Provenance
from candidate_transformer.models.canonical import WorkExperience, Education
from candidate_transformer.models.intermediate import IntermediateCandidate
from candidate_transformer.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)

class CSVExtractor(BaseExtractor):
    """
    Extracts candidate data from a recruiter-provided CSV file.
    Assumes the CSV contains header fields and a single row of candidate details.
    """

    def __init__(self, confidence_score: float = 0.95):
        self.confidence_score = confidence_score

    def _get_column_value(self, df: pd.DataFrame, aliases: List[str]) -> Optional[Any]:
        """Finds the first column in df that matches any of the aliases (case-insensitive)."""
        df_cols_lower = [c.lower().strip().replace("_", "").replace(" ", "") for c in df.columns]
        for alias in aliases:
            cleaned_alias = alias.lower().replace("_", "").replace(" ", "")
            if cleaned_alias in df_cols_lower:
                idx = df_cols_lower.index(cleaned_alias)
                val = df.iloc[0, idx]
                if pd.isna(val):
                    return None
                return val
        return None

    def extract(self, source: Union[Path, str, Any]) -> IntermediateCandidate:
        if isinstance(source, (str, Path)):
            source_name = Path(source).name
        elif hasattr(source, "name"):
            source_name = Path(source.name).name
        else:
            source_name = "stream.csv"

        logger.info(f"Extracting CSV candidate data from {source_name}")

        try:
            # Load CSV using pandas (natively supports files, paths, and StringIO)
            df = pd.read_csv(source)
            if df.empty:
                logger.warning(f"CSV source {source_name} is empty.")
                return IntermediateCandidate()
        except Exception as e:
            logger.error(f"Failed to parse CSV source {source_name}: {e}")
            return IntermediateCandidate()

        # Helper function to wrap values in FieldMetadata
        def make_meta(field_name: str, value: Any, method: str = "CSV Mapping") -> FieldMetadata:
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
        raw_name = self._get_column_value(df, ["full_name", "name", "candidate_name", "candidate"])
        full_name = make_meta("full_name", str(raw_name)) if raw_name else None

        # 2. Emails
        emails = []
        raw_email = self._get_column_value(df, ["email", "email_address", "emails"])
        if raw_email:
            for email in str(raw_email).split(","):
                email_str = email.strip()
                if email_str:
                    emails.append(make_meta("emails", email_str))

        # 3. Phones
        phones = []
        raw_phone = self._get_column_value(df, ["phone", "phone_number", "phones", "mobile"])
        if raw_phone:
            for phone in str(raw_phone).split(","):
                phone_str = phone.strip()
                if phone_str:
                    phones.append(make_meta("phones", phone_str))

        # 4. Location
        raw_location = self._get_column_value(df, ["location", "city", "address", "current_location"])
        location = make_meta("location", str(raw_location)) if raw_location else None

        # 5. Links
        links = []
        raw_links = self._get_column_value(df, ["links", "urls", "github", "linkedin", "portfolio"])
        if raw_links:
            # Split by comma or semicolon
            delim = ";" if ";" in str(raw_links) else ","
            for link in str(raw_links).split(delim):
                link_str = link.strip()
                if link_str:
                    links.append(make_meta("links", link_str))

        # 6. Headline
        raw_headline = self._get_column_value(df, ["headline", "title", "summary", "role"])
        headline = make_meta("headline", str(raw_headline)) if raw_headline else None

        # 7. Years of Experience
        raw_exp = self._get_column_value(df, ["years_experience", "experience_years", "exp", "total_exp"])
        years_experience = None
        if raw_exp is not None:
            try:
                years_experience = make_meta("years_experience", float(raw_exp))
            except ValueError:
                logger.warning(f"Could not parse years_experience '{raw_exp}' as float.")

        # 8. Skills
        skills = []
        raw_skills = self._get_column_value(df, ["skills", "skillset", "technologies"])
        if raw_skills:
            delim = ";" if ";" in str(raw_skills) else ","
            for skill in str(raw_skills).split(delim):
                skill_str = skill.strip()
                if skill_str:
                    skills.append(make_meta("skills", skill_str))

        # 9. Experience (Single current job if present in CSV columns)
        experience = []
        comp = self._get_column_value(df, ["company", "current_company", "employer"])
        title = self._get_column_value(df, ["job_title", "title", "current_title"])
        start = self._get_column_value(df, ["start_date", "job_start"])
        end = self._get_column_value(df, ["end_date", "job_end"])
        desc = self._get_column_value(df, ["job_description", "description"])

        if comp or title:
            work = WorkExperience(
                company=str(comp) if comp else "Unknown Company",
                title=str(title) if title else None,
                start_date=str(start) if start else None,
                end_date=str(end) if end else None,
                description=str(desc) if desc else None
            )
            experience.append(make_meta("experience", work, method="CSV Job Parsing"))

        # 10. Education (Single school if present in CSV columns)
        education = []
        inst = self._get_column_value(df, ["school", "institution", "university", "college"])
        deg = self._get_column_value(df, ["degree", "education_degree"])
        major = self._get_column_value(df, ["major", "field_of_study"])
        edu_start = self._get_column_value(df, ["edu_start", "education_start"])
        edu_end = self._get_column_value(df, ["edu_end", "education_end"])

        if inst:
            edu = Education(
                institution=str(inst),
                degree=str(deg) if deg else None,
                major=str(major) if major else None,
                start_date=str(edu_start) if edu_start else None,
                end_date=str(edu_end) if edu_end else None
            )
            education.append(make_meta("education", edu, method="CSV Education Parsing"))

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
