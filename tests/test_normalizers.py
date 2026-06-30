import pytest
from candidate_transformer.normalizers.email import EmailNormalizer
from candidate_transformer.normalizers.name import NameNormalizer
from candidate_transformer.normalizers.phone import PhoneNormalizer
from candidate_transformer.normalizers.date import DateNormalizer
from candidate_transformer.normalizers.skills import SkillNormalizer

def test_email_normalizer():
    normalizer = EmailNormalizer()
    assert normalizer.normalize("  ALEX.SMITH@EXAMPLE.COM   ") == "alex.smith@example.com"
    assert normalizer.normalize("john@domain.co.uk") == "john@domain.co.uk"
    assert normalizer.normalize(None) == ""

def test_name_normalizer():
    normalizer = NameNormalizer()
    assert normalizer.normalize("  john   smith  ") == "John Smith"
    assert normalizer.normalize("o'connor") == "O'Connor"
    assert normalizer.normalize("MARIA-JOSE") == "Maria-Jose"
    assert normalizer.normalize(None) == ""

def test_phone_normalizer():
    normalizer = PhoneNormalizer(default_region="US")
    # Valid US phone numbers
    assert normalizer.normalize("415-555-2671") == "+14155552671"
    assert normalizer.normalize("  +1 (415) 555-2671 ") == "+14155552671"
    # Valid International phone numbers
    assert normalizer.normalize("+44 20 7946 0958") == "+442079460958"
    # Fallback/invalid cases
    assert normalizer.normalize("invalid-phone") == "invalid-phone"
    assert normalizer.normalize("12345") == "12345"
    assert normalizer.normalize(None) == ""

def test_date_normalizer():
    normalizer = DateNormalizer()
    assert normalizer.normalize("2020-03-12") == "2020-03"
    assert normalizer.normalize("Jan 2020") == "2020-01"
    assert normalizer.normalize("04/2021") == "2021-04"
    assert normalizer.normalize("2020") == "2020-01"
    assert normalizer.normalize("present") == "Present"
    assert normalizer.normalize("Current") == "Present"
    assert normalizer.normalize("random-string-2018") == "2018-01"
    assert normalizer.normalize(None) == ""

def test_skill_normalizer():
    normalizer = SkillNormalizer(similarity_threshold=85.0)
    # Direct alias match
    assert normalizer.normalize("py") == "Python"
    assert normalizer.normalize("CPP") == "C++"
    assert normalizer.normalize("c plus plus") == "C++"
    # Case insensitivity direct match
    assert normalizer.normalize("javascript") == "JavaScript"
    # Fuzzy match with RapidFuzz
    assert normalizer.normalize("Pythn") == "Python"
    assert normalizer.normalize("Javascrpt") == "JavaScript"
    # Unknown skills (capitalized or uppercased if short)
    assert normalizer.normalize("kubernetes-operators") == "Kubernetes-Operators"
    assert normalizer.normalize("sql") == "SQL"
    assert normalizer.normalize(None) == ""
