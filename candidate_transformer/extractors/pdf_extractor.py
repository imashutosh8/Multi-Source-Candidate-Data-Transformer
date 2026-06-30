import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, List, Optional, Union
import fitz  # PyMuPDF
from candidate_transformer.models.provenance import FieldMetadata, Provenance
from candidate_transformer.models.canonical import WorkExperience, Education
from candidate_transformer.models.intermediate import IntermediateCandidate
from candidate_transformer.extractors.base import BaseExtractor
from candidate_transformer.config import EMAIL_PATTERN, PHONE_PATTERN, LINK_PATTERN, SKILL_VOCABULARY

logger = logging.getLogger(__name__)

class PDFExtractor(BaseExtractor):
    """
    Extracts candidate data from unstructured Resume PDF files.
    Uses PyMuPDF to extract text and heuristic regex rule-engines to parse sections.
    """

    def __init__(self, confidence_score: float = 0.78):
        self.confidence_score = confidence_score

    def extract(self, source: Union[Path, str, Any]) -> IntermediateCandidate:
        if isinstance(source, (str, Path)):
            source_name = Path(source).name
        elif hasattr(source, "name"):
            source_name = Path(source.name).name
        else:
            source_name = "stream.pdf"

        logger.info(f"Extracting PDF resume data from {source_name}")

        text = ""
        try:
            if isinstance(source, (str, Path)):
                doc = fitz.open(source)
            else:
                # Read raw stream bytes to load PDF in-memory
                content = source.read()
                if isinstance(content, str):
                    content = content.encode('utf-8')
                doc = fitz.open(stream=content, filetype="pdf")

            for page in doc:
                text += page.get_text()
            doc.close()
        except Exception as e:
            logger.error(f"Failed to read/parse PDF source {source_name}: {e}")
            return IntermediateCandidate()

        if not text.strip():
            logger.warning(f"PDF source {source_name} is empty or contains no readable text.")
            return IntermediateCandidate()

        # Helper function to wrap values in FieldMetadata
        def make_meta(field_name: str, value: Any, method: str = "Regex Extraction") -> FieldMetadata:
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

        # 1. Emails
        emails = []
        found_emails = re.findall(EMAIL_PATTERN, text)
        for email in found_emails:
            emails.append(make_meta("emails", email.strip()))

        # 2. Phones
        phones = []
        found_phones = re.findall(PHONE_PATTERN, text)
        for phone in found_phones:
            phones.append(make_meta("phones", phone.strip()))

        # 3. Links
        links = []
        found_links = re.findall(LINK_PATTERN, text)
        for link in found_links:
            links.append(make_meta("links", link.strip()))

        # 4. Parse Lines for name, headline, sections
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Heuristic for full name: First line that doesn't contain email/phone/url
        full_name = None
        for line in lines[:5]:  # Check first few lines
            if (not re.search(EMAIL_PATTERN, line) and 
                not re.search(PHONE_PATTERN, line) and 
                not re.search(r'https?://', line) and 
                len(line.split()) >= 2 and len(line.split()) <= 4):
                full_name = make_meta("full_name", line)
                break

        # Skills extraction from vocabulary
        skills = []
        text_lower = text.lower()
        for skill_vocab in SKILL_VOCABULARY:
            pattern = rf'\b{re.escape(skill_vocab)}\b'
            if skill_vocab in ["c++", "cpp", "c#"]:
                pattern = rf'(?:^|\s|/){re.escape(skill_vocab)}(?:$|\s|,|\.)'
            if re.search(pattern, text_lower):
                skills.append(make_meta("skills", skill_vocab))

        # Basic Section Parsing State Machine
        experience_entries = []
        education_entries = []
        
        current_section = None
        current_block = []

        # Keywords for sections
        exp_keywords = ["experience", "employment", "work history", "professional history", "jobs"]
        edu_keywords = ["education", "academic", "university", "college", "school", "degrees"]

        for line in lines:
            line_lower = line.lower().strip()
            # Detect section change
            is_section_header = False
            for word in exp_keywords:
                if line_lower == word or line_lower.startswith(word + ":") or line_lower.startswith(word + " "):
                    if len(line_lower.split()) < 4:
                        is_section_header = True
                        current_section = "experience"
                        break
            for word in edu_keywords:
                if line_lower == word or line_lower.startswith(word + ":") or line_lower.startswith(word + " "):
                    if len(line_lower.split()) < 4:
                        is_section_header = True
                        current_section = "education"
                        break

            if is_section_header:
                current_block = []
                continue

            if current_section == "experience":
                current_block.append(line)
            elif current_section == "education":
                current_block.append(line)

        # Parse Work Experience Blocks (heuristic)
        # Split blocks when we see a line containing years or company patterns
        # Look for years patterns (e.g. 2020, 2021) or company keywords
        experience = self._parse_experience_section(current_block, source_name)
        education = self._parse_education_section(current_block, source_name)

        return IntermediateCandidate(
            full_name=full_name,
            emails=emails,
            phones=phones,
            location=None, # PDF regex usually doesn't pull location reliably
            links=links,
            headline=None,
            years_experience=None, # Derived or extracted later
            skills=skills,
            experience=experience,
            education=education
        )

    def _parse_experience_section(self, lines: List[str], source_name: str) -> List[FieldMetadata[WorkExperience]]:
        experience = []
        # Group lines into logical chunks: each chunk is a candidate WorkExperience
        # A new chunk begins when we see something that looks like "Company" or a date range
        chunks = []
        temp = []
        for line in lines:
            # If line contains a year range, e.g., "2020 - 2023" or "2019 - Present"
            if re.search(r'\b(19|20)\d{2}\b', line) and len(temp) > 2:
                chunks.append(temp)
                temp = [line]
            else:
                temp.append(line)
        if temp:
            chunks.append(temp)

        for chunk in chunks:
            if not chunk:
                continue
            # Heuristic extract details
            company = "Unknown Company"
            title = None
            start_date = None
            end_date = None
            description_parts = []

            for i, line in enumerate(chunk):
                # Find dates
                date_match = re.findall(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?[a-z]*\.?\s*(?:19|20)\d{2}\b', line, re.IGNORECASE)
                if len(date_match) >= 1:
                    # Clean and set start/end
                    start_date = date_match[0]
                    if len(date_match) >= 2:
                        end_date = date_match[1]
                    elif "present" in line.lower() or "current" in line.lower():
                        end_date = "Present"
                
                # Heuristic for Company
                if "inc" in line.lower() or "corp" in line.lower() or "ltd" in line.lower() or "co." in line.lower() or "company" in line.lower() or "technologies" in line.lower():
                    company = line
                elif i == 0 and company == "Unknown Company":
                    company = line
                elif i == 1 and not title:
                    title = line
                else:
                    description_parts.append(line)

            # Clean and create
            if company != "Unknown Company" or title:
                work = WorkExperience(
                    company=company.strip(),
                    title=title.strip() if title else None,
                    start_date=start_date.strip() if start_date else None,
                    end_date=end_date.strip() if end_date else None,
                    description=" ".join(description_parts).strip() if description_parts else None
                )
                experience.append(
                    FieldMetadata(
                        value=work,
                        confidence=self.confidence_score,
                        provenance=Provenance(
                            field="experience",
                            source=source_name,
                            method="Regex Experience Parser",
                            timestamp=datetime.utcnow()
                        )
                    )
                )
        return experience

    def _parse_education_section(self, lines: List[str], source_name: str) -> List[FieldMetadata[Education]]:
        education = []
        chunks = []
        temp = []
        for line in lines:
            if ("university" in line.lower() or "college" in line.lower() or "school" in line.lower()) and len(temp) > 1:
                chunks.append(temp)
                temp = [line]
            else:
                temp.append(line)
        if temp:
            chunks.append(temp)

        for chunk in chunks:
            if not chunk:
                continue
            institution = "Unknown Institution"
            degree = None
            major = None
            start_date = None
            end_date = None

            for i, line in enumerate(chunk):
                # Institution
                if "university" in line.lower() or "college" in line.lower() or "school" in line.lower() or "institute" in line.lower():
                    institution = line
                # Degree / Major
                degree_match = re.search(r'\b(b\.?s\.?|m\.?s\.?|b\.?a\.?|m\.?a\.?|ph\.?d\.?|bachelor|master|doctorate)\b', line, re.IGNORECASE)
                if degree_match:
                    degree = degree_match.group(1)
                    # Major might be the rest of the line
                    major_part = line.replace(degree, "").strip()
                    if major_part:
                        major = major_part
                
                # Dates
                date_match = re.findall(r'\b(19|20)\d{2}\b', line)
                if len(date_match) >= 1:
                    start_date = date_match[0]
                    if len(date_match) >= 2:
                        end_date = date_match[1]

            if institution != "Unknown Institution":
                edu = Education(
                    institution=institution.strip(),
                    degree=degree.strip() if degree else None,
                    major=major.strip() if major else None,
                    start_date=start_date.strip() if start_date else None,
                    end_date=end_date.strip() if end_date else None
                )
                education.append(
                    FieldMetadata(
                        value=edu,
                        confidence=self.confidence_score,
                        provenance=Provenance(
                            field="education",
                            source=source_name,
                            method="Regex Education Parser",
                            timestamp=datetime.utcnow()
                        )
                    )
                )
        return education
