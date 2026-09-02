from decimal import Decimal

HARBOR_COVE_EXTRACTED = {
    "policy_number": "HCL-2024-4412",
    "named_insured": "Harbor Cove LLC",
    "broker": "Northshore Risk Partners",
    "effective_date": "2024-01-01",
    "renewal_date": "2025-01-01",
    "term_premium": "185000.00",
    "policy_fee": "1500.00",
    "total_premium": "186500.00",
    "limit_of_insurance": "25000000.00",
    "coverage_type": "Property",
    "carriers": ["Acme Insurance Company", "Backup Mutual"],
    "deductibles": [
        {"peril": "Wind/Hail", "amount": "50000.00"},
        {"peril": "All Other Perils", "amount": "25000.00"},
    ],
    "locations": [
        {"label": "Building 1", "address": "100 Harbor Cove Drive, Tampa, FL"},
        {"label": "Building 2", "address": "110 Harbor Cove Drive, Tampa, FL"},
    ],
    "confidence": {
        "policy_number": 0.92,
        "named_insured": 0.95,
        "broker": 0.8,
        "effective_date": 0.9,
        "renewal_date": 0.9,
        "term_premium": 0.88,
        "policy_fee": 0.7,
        "total_premium": 0.88,
        "limit_of_insurance": 0.91,
        "coverage_type": 0.85,
        "carriers": 0.9,
        "deductibles": 0.93,
        "locations": 0.87,
    },
}


def test_missing_fields_are_null_and_arrays_are_lists() -> None:
    from app.extraction.schema import ExtractedPolicy

    result = ExtractedPolicy.model_validate({})
    assert result.policy_number is None
    assert result.named_insured is None
    assert result.broker is None
    assert result.effective_date is None
    assert result.renewal_date is None
    assert result.term_premium is None
    assert result.policy_fee is None
    assert result.total_premium is None
    assert result.limit_of_insurance is None
    assert result.coverage_type is None
    assert result.carriers == []
    assert result.deductibles == []
    assert result.locations == []


def test_null_scalar_confidence_is_zero() -> None:
    from app.extraction.schema import ExtractedPolicy

    result = ExtractedPolicy.model_validate(
        {
            "named_insured": None,
            "broker": "Northshore Risk Partners",
            "confidence": {"named_insured": 0.9, "broker": 0.8},
        }
    )
    assert result.named_insured is None
    assert result.confidence.named_insured == 0
    assert result.broker == "Northshore Risk Partners"
    assert result.confidence.broker == 0.8


def test_harbor_cove_fixture_keeps_multi_deductible_and_locations() -> None:
    from app.extraction.schema import ExtractedPolicy

    result = ExtractedPolicy.model_validate(HARBOR_COVE_EXTRACTED)
    assert result.named_insured == "Harbor Cove LLC"
    assert result.carriers == ["Acme Insurance Company", "Backup Mutual"]
    assert len(result.deductibles) == 2
    assert result.deductibles[0].peril == "Wind/Hail"
    assert result.deductibles[0].amount == Decimal("50000.00")
    assert result.deductibles[1].peril == "All Other Perils"
    assert result.deductibles[1].amount == Decimal("25000.00")
    assert len(result.locations) == 2
    assert result.locations[1].label == "Building 2"
    assert "Harbor Cove Drive" in (result.locations[1].address or "")
    assert result.confidence.deductibles == 0.93
    assert result.confidence.locations == 0.87


def test_percent_deductible_with_dollar_figure_is_coerced() -> None:
    from app.extraction.schema import ExtractedPolicy

    result = ExtractedPolicy.model_validate(
        {
            "deductibles": [
                {"peril": "Named Storm", "amount": "2% ($9620)"},
                {"peril": "Wind/Hail", "amount": "2% ($9,620.00)"},
                {"peril": "All Other Perils", "amount": "$25,000"},
                {"peril": "Flood", "amount": "2%"},
            ],
            "term_premium": "$185,000.00",
        }
    )
    assert result.deductibles[0].amount == Decimal(9620)
    assert result.deductibles[1].amount == Decimal("9620.00")
    assert result.deductibles[2].amount == Decimal(25000)
    assert result.deductibles[3].amount is None
    assert result.term_premium == Decimal("185000.00")
