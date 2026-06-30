import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Type

# Import configuration
from candidate_transformer.config.pipeline_config import PipelineConfig

# Import models
from candidate_transformer.models.provenance import FieldMetadata, Provenance
from candidate_transformer.models.canonical import CanonicalCandidate, WorkExperience, Education
from candidate_transformer.models.intermediate import IntermediateCandidate

# Import extractors
from candidate_transformer.extractors.csv_extractor import CSVExtractor
from candidate_transformer.extractors.json_extractor import JSONExtractor
from candidate_transformer.extractors.pdf_extractor import PDFExtractor
from candidate_transformer.extractors.txt_extractor import TXTNotesExtractor

# Import normalizers
from candidate_transformer.normalizers.base import BaseNormalizer
from candidate_transformer.normalizers.email import EmailNormalizer
from candidate_transformer.normalizers.name import NameNormalizer
from candidate_transformer.normalizers.phone import PhoneNormalizer
from candidate_transformer.normalizers.date import DateNormalizer
from candidate_transformer.normalizers.skills import SkillNormalizer

# Import processing modules
from candidate_transformer.mergers.merger import CandidateMerger
from candidate_transformer.provenance.tracker import ProvenanceTracker
from candidate_transformer.confidence.calculator import ConfidenceCalculator
from candidate_transformer.projection.projector import SchemaProjector
from candidate_transformer.validators.validator import OutputValidator, ValidationSchema, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar('T')

class PipelineError(Exception):
    """Base exception for all pipeline errors."""
    pass

class ExtractionError(PipelineError):
    """Raised when file extraction fails under fail_fast policy."""
    pass

class NormalizationError(PipelineError):
    """Raised when field normalization fails."""
    pass


class CandidateTransformerOrchestrator:
    """
    Main Orchestrator for the Candidate Data Transformer pipeline.
    Coordinates source detection, extraction, normalization, merging,
    confidence scoring, projection, and final validation.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.merger = CandidateMerger(source_priority=self.config.source_priority)
        self.confidence_calculator = ConfidenceCalculator(weights=self.config.confidence_weights)
        
        # Initialize normalizers
        self.name_normalizer = NameNormalizer()
        self.email_normalizer = EmailNormalizer()
        self.phone_normalizer = PhoneNormalizer()
        self.date_normalizer = DateNormalizer()
        self.skill_normalizer = SkillNormalizer()

    def _normalize_field(
        self,
        field_meta: Optional[FieldMetadata[T]],
        normalizer: BaseNormalizer,
        method_suffix: str
    ) -> Optional[FieldMetadata[T]]:
        """Generic helper to clean and track provenance for scalar metadata wrappers."""
        if not field_meta or field_meta.value is None:
            return None

        try:
            norm_val = normalizer.normalize(field_meta.value)
            return ProvenanceTracker.track_transformation(
                FieldMetadata(
                    value=norm_val,
                    confidence=field_meta.confidence,
                    provenance=field_meta.provenance
                ),
                method_suffix
            )
        except Exception as e:
            msg = f"Failed to normalize field '{field_meta.provenance.field}': {e}"
            logger.error(msg)
            if self.config.failure_policy == "fail_fast":
                raise NormalizationError(msg) from e
            return field_meta

    def _normalize_field_list(
        self,
        field_list: List[FieldMetadata[T]],
        normalizer: BaseNormalizer,
        method_suffix: str
    ) -> List[FieldMetadata[T]]:
        """Generic helper to clean collections of metadata wrappers."""
        normalized = []
        for item in field_list:
            norm_item = self._normalize_field(item, normalizer, method_suffix)
            if norm_item:
                normalized.append(norm_item)
        return normalized

    def _normalize_work_experience(self, exp_meta: FieldMetadata[WorkExperience]) -> FieldMetadata[WorkExperience]:
        """Specific normalizer for WorkExperience objects."""
        val = exp_meta.value
        norm_company = self.name_normalizer.normalize(val.company)
        norm_start = self.date_normalizer.normalize(val.start_date) if val.start_date else None
        norm_end = self.date_normalizer.normalize(val.end_date) if val.end_date else None
        
        norm_work = WorkExperience(
            company=norm_company,
            title=val.title.strip() if val.title else None,
            start_date=norm_start,
            end_date=norm_end,
            description=val.description.strip() if val.description else None
        )
        return ProvenanceTracker.track_transformation(
            FieldMetadata(
                value=norm_work,
                confidence=exp_meta.confidence,
                provenance=exp_meta.provenance
            ),
            "Experience Normalized"
        )

    def _normalize_education(self, edu_meta: FieldMetadata[Education]) -> FieldMetadata[Education]:
        """Specific normalizer for Education objects."""
        val = edu_meta.value
        norm_inst = self.name_normalizer.normalize(val.institution)
        norm_start = self.date_normalizer.normalize(val.start_date) if val.start_date else None
        norm_end = self.date_normalizer.normalize(val.end_date) if val.end_date else None

        norm_edu = Education(
            institution=norm_inst,
            degree=val.degree.strip() if val.degree else None,
            major=val.major.strip() if val.major else None,
            start_date=norm_start,
            end_date=norm_end
        )
        return ProvenanceTracker.track_transformation(
            FieldMetadata(
                value=norm_edu,
                confidence=edu_meta.confidence,
                provenance=edu_meta.provenance
            ),
            "Education Normalized"
        )

    def _normalize_candidate(self, cand: IntermediateCandidate) -> IntermediateCandidate:
        """Cleans all fields inside an IntermediateCandidate profile."""
        # Simple cleanup wrapper for links to strip spaces and trailing slashes
        class SimpleLinkCleanup(BaseNormalizer):
            def normalize(self, val: str) -> str:
                return val.strip().rstrip('/')

        return IntermediateCandidate(
            full_name=self._normalize_field(cand.full_name, self.name_normalizer, "Name Normalized"),
            emails=self._normalize_field_list(cand.emails, self.email_normalizer, "Email Normalized"),
            phones=self._normalize_field_list(cand.phones, self.phone_normalizer, "Phone Normalized (E.164)"),
            location=self._normalize_field(cand.location, self.name_normalizer, "Location Cleaned"),
            links=self._normalize_field_list(cand.links, SimpleLinkCleanup(), "Link Cleaned"),
            headline=self._normalize_field(cand.headline, SimpleLinkCleanup(), "Headline Cleaned"),
            years_experience=cand.years_experience,
            skills=self._normalize_field_list(cand.skills, self.skill_normalizer, "Skill Normalized"),
            experience=[self._normalize_work_experience(x) for x in cand.experience],
            education=[self._normalize_education(x) for x in cand.education]
        )

    def _safe_extract(self, path: Optional[Path], extractor_cls: Type[Any]) -> Optional[IntermediateCandidate]:
        """Robustly extracts from file path, handling errors based on the configuration policy."""
        if not path:
            return None

        if not path.exists():
            msg = f"Input file path does not exist: {path}"
            logger.warning(msg)
            if self.config.failure_policy == "fail_fast":
                raise ExtractionError(msg)
            return None

        try:
            return extractor_cls().extract(path)
        except Exception as e:
            msg = f"Failed to extract from file '{path.name}': {e}"
            logger.error(msg)
            if self.config.failure_policy == "fail_fast":
                raise ExtractionError(msg) from e
            return None

    def run(
        self,
        csv_path: Optional[Path] = None,
        ats_path: Optional[Path] = None,
        resume_path: Optional[Path] = None,
        notes_path: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Runs the full pipeline, coordinates extraction, normalization, merging,
        confidence calculations, projection, and schema validation.
        """
        intermediate_profiles: List[IntermediateCandidate] = []

        # 1. Extraction (Using safe extractor wrapper)
        csv_profile = self._safe_extract(csv_path, CSVExtractor)
        if csv_profile: intermediate_profiles.append(csv_profile)

        ats_profile = self._safe_extract(ats_path, JSONExtractor)
        if ats_profile: intermediate_profiles.append(ats_profile)

        pdf_profile = self._safe_extract(resume_path, PDFExtractor)
        if pdf_profile: intermediate_profiles.append(pdf_profile)

        txt_profile = self._safe_extract(notes_path, TXTNotesExtractor)
        if txt_profile: intermediate_profiles.append(txt_profile)

        if not intermediate_profiles:
            raise ExtractionError("No candidate data was extracted. Provide at least one valid source file.")

        # 2. Normalization
        normalized_profiles = [self._normalize_candidate(cand) for cand in intermediate_profiles]

        # 3. Merging
        merged_fields = self.merger.merge(normalized_profiles)

        # 4. Confidence Score Calculation
        overall_confidence = self.confidence_calculator.calculate(merged_fields)

        # 5. Provenance Collation
        collated_provenance = ProvenanceTracker.collate_provenance(merged_fields)

        # 6. Generate Canonical Candidate
        candidate_id = str(uuid.uuid4())
        canonical_candidate = CanonicalCandidate(
            candidate_id=candidate_id,
            full_name=merged_fields["full_name"],
            emails=merged_fields["emails"],
            phones=merged_fields["phones"],
            location=merged_fields["location"],
            links=merged_fields["links"],
            headline=merged_fields["headline"],
            years_experience=merged_fields["years_experience"],
            skills=merged_fields["skills"],
            experience=merged_fields["experience"],
            education=merged_fields["education"],
            provenance=collated_provenance,
            overall_confidence=overall_confidence
        )

        # 7. Projection Config Loading
        proj_config = config or {
            "fields": [
                {"path": "candidate_id"},
                {"path": "full_name"},
                {"path": "emails"},
                {"path": "phones"},
                {"path": "skills"},
                {"path": "overall_confidence"}
            ],
            "include_confidence": False,
            "on_missing": "null"
        }

        # 8. Projection Layer Execution
        projector = SchemaProjector(proj_config)
        projected_data = projector.project(canonical_candidate)

        # 9. Validation Layer Execution
        validation_cfg = proj_config.get("validation")
        if validation_cfg:
            validation_schema = ValidationSchema.model_validate(validation_cfg)
            validator = OutputValidator(validation_schema)
            is_valid, errors = validator.validate(projected_data)
            if not is_valid:
                raise ValidationError(errors)

        return projected_data
