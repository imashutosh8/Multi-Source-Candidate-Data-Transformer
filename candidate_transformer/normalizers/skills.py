import logging
from rapidfuzz import process, utils, fuzz
from candidate_transformer.normalizers.base import BaseNormalizer

logger = logging.getLogger(__name__)

class SkillNormalizer(BaseNormalizer):
    """
    Normalizes professional skills using a canonical dictionary and fuzzy string matching.
    Matches variations (e.g. 'CPP' -> 'C++') and typos (e.g. 'Pythn' -> 'Python').
    """
    def __init__(self, similarity_threshold: float = 85.0):
        self.similarity_threshold = similarity_threshold
        # Canonical mappings: lowercase input alias -> Standard Output Name
        self.canonical_skills = {
            "cpp": "C++",
            "c plus plus": "C++",
            "cplusplus": "C++",
            "py": "Python",
            "python": "Python",
            "js": "JavaScript",
            "javascript": "JavaScript",
            "ts": "TypeScript",
            "typescript": "TypeScript",
            "k8s": "Kubernetes",
            "kubernetes": "Kubernetes",
            "aws": "Amazon Web Services",
            "amazon web services": "Amazon Web Services",
            "gcp": "Google Cloud Platform",
            "google cloud platform": "Google Cloud Platform",
            "html": "HTML",
            "css": "CSS",
            "go": "Go",
            "golang": "Go",
            "docker": "Docker",
            "react": "React",
            "node": "Node.js",
            "nodejs": "Node.js",
            "fastapi": "FastAPI",
            "django": "Django",
            "flask": "Flask",
            "terraform": "Terraform",
            "postgres": "PostgreSQL",
            "postgresql": "PostgreSQL",
            "mysql": "MySQL",
            "mongodb": "MongoDB",
            "git": "Git",
            "pandas": "Pandas",
            "numpy": "NumPy"
        }
        
    def normalize(self, value: str) -> str:
        if not isinstance(value, str):
            return ""

        cleaned = value.strip()
        if not cleaned:
            return ""

        cleaned_lower = cleaned.lower()

        # 1. Exact Match on Key
        if cleaned_lower in self.canonical_skills:
            return self.canonical_skills[cleaned_lower]

        # 2. Exact Match on Value
        for canonical_name in self.canonical_skills.values():
            if cleaned_lower == canonical_name.lower():
                return canonical_name

        # 3. Fuzzy Match against mapping keys and values using RapidFuzz
        choices = list(self.canonical_skills.keys()) + list(self.canonical_skills.values())
        best_match = process.extractOne(
            cleaned_lower,
            choices,
            processor=utils.default_process,
            scorer=fuzz.ratio,
            score_cutoff=self.similarity_threshold
        )

        if best_match:
            matched_text = best_match[0]
            # Map back to canonical name if it was a key, otherwise return matched value
            if matched_text in self.canonical_skills:
                return self.canonical_skills[matched_text]
            return matched_text

        # 4. Unknown Skill: Clean and return original in Title Case or uppercase if short (like SQL)
        if len(cleaned) <= 4:
            return cleaned.upper()
        return cleaned.title()
