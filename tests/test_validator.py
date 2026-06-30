import pytest
from candidate_transformer.validators.validator import ValidationRule, ValidationSchema, OutputValidator

def test_validator_required_fields():
    # Schema: full_name and primary_email are required.
    schema = ValidationSchema(rules=[
        ValidationRule(field="full_name", required=True, type="string"),
        ValidationRule(field="primary_email", required=True, type="email"),
        ValidationRule(field="phone", required=False, type="phone")
    ])
    validator = OutputValidator(schema)

    # 1. Valid data
    valid_data = {
        "full_name": "Jane Doe",
        "primary_email": "jane@example.com",
        "phone": "+14155552671"
    }
    is_valid, errors = validator.validate(valid_data)
    assert is_valid
    assert len(errors) == 0

    # 2. Omitted required field
    missing_email_data = {
        "full_name": "Jane Doe",
        "phone": "+14155552671"
    }
    is_valid, errors = validator.validate(missing_email_data)
    assert not is_valid
    assert any("primary_email" in err and "omitted" in err for err in errors)

    # 3. Null required field
    null_name_data = {
        "full_name": None,
        "primary_email": "jane@example.com"
    }
    is_valid, errors = validator.validate(null_name_data)
    assert not is_valid
    assert any("full_name" in err and "null" in err for err in errors)

def test_validator_type_and_formats():
    schema = ValidationSchema(rules=[
        ValidationRule(field="age", required=False, type="number"),
        ValidationRule(field="skills", required=True, type="list", min_length=2),
        ValidationRule(field="primary_email", required=True, type="email"),
        ValidationRule(field="phone", required=True, type="phone")
    ])
    validator = OutputValidator(schema)

    # Invalid email and phone formats, invalid age type, too short list
    invalid_data = {
        "age": "thirty",  # Expected number
        "skills": ["Python"],  # Expected min length 2
        "primary_email": "not-an-email",  # Expected email format
        "phone": "415-555-1234"  # Expected E.164 starting with '+'
    }
    is_valid, errors = validator.validate(invalid_data)
    assert not is_valid
    assert len(errors) == 4
    assert any("age" in err and "number" in err for err in errors)
    assert any("skills" in err and "minimum" in err for err in errors)
    assert any("primary_email" in err and "invalid email" in err for err in errors)
    assert any("phone" in err and "E.164" in err for err in errors)

def test_validator_with_confidence_wrappers():
    # When include_confidence is True, fields in the data are dictionaries containing "value" and "confidence"
    schema = ValidationSchema(rules=[
        ValidationRule(field="full_name", required=True, type="string"),
        ValidationRule(field="primary_email", required=True, type="email")
    ])
    validator = OutputValidator(schema)

    wrapped_data = {
        "full_name": {
            "value": "Jane Doe",
            "confidence": 0.99
        },
        "primary_email": {
            "value": "invalid-email",
            "confidence": 0.95
        }
    }
    is_valid, errors = validator.validate(wrapped_data)
    assert not is_valid
    assert len(errors) == 1
    assert "primary_email" in errors[0]
