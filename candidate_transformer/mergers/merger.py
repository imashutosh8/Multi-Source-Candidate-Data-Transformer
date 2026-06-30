import logging
from typing import List, Optional, Any, TypeVar, Dict
from rapidfuzz import fuzz
from candidate_transformer.models.provenance import FieldMetadata, Provenance
from candidate_transformer.models.canonical import WorkExperience, Education
from candidate_transformer.models.intermediate import IntermediateCandidate

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CandidateMerger:
    """
    Merges multiple IntermediateCandidate objects into a single set of fields
    ready for CanonicalCandidate representation.
    Handles conflict resolution using configurable source priority and confidence scores.
    """

    def __init__(self, source_priority: Optional[List[str]] = None):
        # Default priority: ATS (high) > CSV (med-high) > PDF (medium) > TXT (low)
        # Matches lowercase substrings of the source filename
        self.source_priority = source_priority or ["ats", "csv", "pdf", "txt"]

    def _get_priority(self, source: str) -> int:
        """
        Returns the priority index of a source. Lower index means higher priority.
        If the source is not recognized, it returns a low priority index.
        """
        source_lower = source.lower()
        for idx, key in enumerate(self.source_priority):
            if key.lower() in source_lower:
                return idx
        return len(self.source_priority)

    def _resolve_scalar(self, values: List[FieldMetadata[T]]) -> Optional[FieldMetadata[T]]:
        """
        Resolves conflicts among scalar values from different sources.
        Picks the highest priority non-empty value. Breaks ties with confidence scores.
        """
        valid = [v for v in values if v is not None and v.value is not None and str(v.value).strip() != ""]
        if not valid:
            return None
        
        # Sort by priority index ascending (0 is highest), then confidence descending
        valid.sort(key=lambda x: (self._get_priority(x.provenance.source), -x.confidence))
        return valid[0]

    def _merge_list_unique(self, list_items: List[FieldMetadata[str]], case_insensitive: bool = False) -> List[FieldMetadata[str]]:
        """
        Deduplicates a flat list of strings across all sources, retaining the
        highest-priority/highest-confidence metadata for each unique string.
        """
        unique_map = {}
        for item in list_items:
            if not item or item.value is None:
                continue
            
            key = item.value.strip()
            if not key:
                continue
            if case_insensitive:
                key = key.lower()

            p_current = self._get_priority(item.provenance.source)

            if key not in unique_map:
                unique_map[key] = item
            else:
                existing = unique_map[key]
                p_existing = self._get_priority(existing.provenance.source)
                
                # Replace if current is higher priority, or equal priority but higher confidence
                if p_current < p_existing or (p_current == p_existing and item.confidence > existing.confidence):
                    unique_map[key] = item

        return list(unique_map.values())

    def _is_same_company(self, c1: str, c2: str) -> bool:
        """Determines if two company names are similar using fuzzy matching."""
        import re
        clean1 = re.sub(r'\b(inc|corp|ltd|co|corporation|incorporated)\b\.?', '', c1.lower()).strip()
        clean2 = re.sub(r'\b(inc|corp|ltd|co|corporation|incorporated)\b\.?', '', c2.lower()).strip()
        return fuzz.ratio(clean1, clean2) > 75.0

    def _merge_work_experience(self, w1: WorkExperience, w2: WorkExperience, p1: int, p2: int) -> WorkExperience:
        """Merges two WorkExperience records, preferring fields from the higher priority source."""
        base, fallback = (w1, w2) if p1 <= p2 else (w2, w1)
        return WorkExperience(
            company=base.company if base.company else fallback.company,
            title=base.title if base.title else fallback.title,
            start_date=base.start_date if base.start_date else fallback.start_date,
            end_date=base.end_date if base.end_date else fallback.end_date,
            description=base.description if base.description else fallback.description
        )

    def _is_same_institution(self, inst1: str, inst2: str) -> bool:
        """Determines if two institution names are similar using fuzzy matching."""
        import re
        clean1 = re.sub(r'\b(university|college|school|inst|institute|of)\b\.?', '', inst1.lower()).strip()
        clean2 = re.sub(r'\b(university|college|school|inst|institute|of)\b\.?', '', inst2.lower()).strip()
        return fuzz.ratio(clean1, clean2) > 75.0

    def _merge_education(self, e1: Education, e2: Education, p1: int, p2: int) -> Education:
        """Merges two Education records, preferring fields from the higher priority source."""
        base, fallback = (e1, e2) if p1 <= p2 else (e2, e1)
        return Education(
            institution=base.institution if base.institution else fallback.institution,
            degree=base.degree if base.degree else fallback.degree,
            major=base.major if base.major else fallback.major,
            start_date=base.start_date if base.start_date else fallback.start_date,
            end_date=base.end_date if base.end_date else fallback.end_date
        )

    def merge(self, candidates: List[IntermediateCandidate]) -> Dict[str, Any]:
        """
        Merges multiple intermediate candidates into a dictionary of fields,
        applying deduplication, normalization conflicts, and merging nested collections.
        """
        logger.info(f"Merging {len(candidates)} candidate profiles.")

        # Group values from all candidate profiles
        names = []
        emails = []
        phones = []
        locations = []
        links = []
        headlines = []
        exp_years = []
        skills = []
        experiences = []
        educations = []

        for c in candidates:
            if c.full_name: names.append(c.full_name)
            if c.location: locations.append(c.location)
            if c.headline: headlines.append(c.headline)
            if c.years_experience: exp_years.append(c.years_experience)
            
            emails.extend(c.emails)
            phones.extend(c.phones)
            links.extend(c.links)
            skills.extend(c.skills)
            experiences.extend(c.experience)
            educations.extend(c.education)

        # 1. Resolve Scalars
        merged_name = self._resolve_scalar(names)
        merged_location = self._resolve_scalar(locations)
        merged_headline = self._resolve_scalar(headlines)
        merged_exp_years = self._resolve_scalar(exp_years)

        # 2. Merge Flat Lists (with case insensitivity for emails and links)
        merged_emails = self._merge_list_unique(emails, case_insensitive=True)
        merged_phones = self._merge_list_unique(phones)
        merged_links = self._merge_list_unique(links, case_insensitive=True)
        merged_skills = self._merge_list_unique(skills, case_insensitive=True)

        # 3. Merge Complex Collections: Experience
        merged_experiences: List[FieldMetadata[WorkExperience]] = []
        for item in experiences:
            matched_idx = -1
            for idx, existing in enumerate(merged_experiences):
                if self._is_same_company(item.value.company, existing.value.company):
                    matched_idx = idx
                    break
            
            if matched_idx != -1:
                existing = merged_experiences[matched_idx]
                p1 = self._get_priority(existing.provenance.source)
                p2 = self._get_priority(item.provenance.source)
                
                merged_val = self._merge_work_experience(existing.value, item.value, p1, p2)
                best_meta = existing if p1 <= p2 else item
                
                merged_experiences[matched_idx] = FieldMetadata(
                    value=merged_val,
                    confidence=best_meta.confidence,
                    provenance=best_meta.provenance
                )
            else:
                merged_experiences.append(item)

        # 4. Merge Complex Collections: Education
        merged_educations: List[FieldMetadata[Education]] = []
        for item in educations:
            matched_idx = -1
            for idx, existing in enumerate(merged_educations):
                if self._is_same_institution(item.value.institution, existing.value.institution):
                    matched_idx = idx
                    break

            if matched_idx != -1:
                existing = merged_educations[matched_idx]
                p1 = self._get_priority(existing.provenance.source)
                p2 = self._get_priority(item.provenance.source)
                
                merged_val = self._merge_education(existing.value, item.value, p1, p2)
                best_meta = existing if p1 <= p2 else item
                
                merged_educations[matched_idx] = FieldMetadata(
                    value=merged_val,
                    confidence=best_meta.confidence,
                    provenance=best_meta.provenance
                )
            else:
                merged_educations.append(item)

        return {
            "full_name": merged_name,
            "emails": merged_emails,
            "phones": merged_phones,
            "location": merged_location,
            "links": merged_links,
            "headline": merged_headline,
            "years_experience": merged_exp_years,
            "skills": merged_skills,
            "experience": merged_experiences,
            "education": merged_educations
        }
