from datetime import UTC, datetime
from uuid import UUID

from app.extraction.schema import ExtractedPolicy
from app.models import Document, Policy, Property
from app.schemas import DocumentOut, PolicyOut, PropertyOut


def apply_extracted(policy: Policy, extracted: ExtractedPolicy) -> None:
    policy.policy_number = extracted.policy_number
    policy.named_insured = extracted.named_insured
    policy.broker = extracted.broker
    policy.effective_date = extracted.effective_date
    policy.renewal_date = extracted.renewal_date
    policy.term_premium = extracted.term_premium
    policy.policy_fee = extracted.policy_fee
    policy.total_premium = extracted.total_premium
    policy.limit_of_insurance = extracted.limit_of_insurance
    policy.coverage_type = extracted.coverage_type
    policy.carriers = list(extracted.carriers)
    policy.deductibles = [
        item.model_dump(mode="json") for item in extracted.deductibles
    ]
    policy.locations = [item.model_dump(mode="json") for item in extracted.locations]
    policy.extraction_confidence = extracted.confidence.model_dump()
    policy.updated_at = datetime.now(UTC)


def extracted_from_policy(policy: Policy) -> ExtractedPolicy:
    return ExtractedPolicy.model_validate(
        {
            "policy_number": policy.policy_number,
            "named_insured": policy.named_insured,
            "broker": policy.broker,
            "effective_date": policy.effective_date,
            "renewal_date": policy.renewal_date,
            "term_premium": policy.term_premium,
            "policy_fee": policy.policy_fee,
            "total_premium": policy.total_premium,
            "limit_of_insurance": policy.limit_of_insurance,
            "coverage_type": policy.coverage_type,
            "carriers": policy.carriers or [],
            "deductibles": policy.deductibles or [],
            "locations": policy.locations or [],
            "confidence": policy.extraction_confidence or {},
        }
    )


def policy_to_out(policy: Policy, property_ids: list[UUID] | None = None) -> PolicyOut:
    extracted = extracted_from_policy(policy)
    return PolicyOut(
        id=policy.id,
        user_id=policy.user_id,
        source_document_id=policy.source_document_id,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
        property_ids=list(property_ids or []),
        **extracted.model_dump(),
    )


def property_to_out(
    prop: Property, policy_ids: list[UUID] | None = None
) -> PropertyOut:
    return PropertyOut(
        id=prop.id,
        user_id=prop.user_id,
        label=prop.label,
        address=prop.address,
        stated_value=prop.stated_value,
        created_at=prop.created_at,
        updated_at=prop.updated_at,
        policy_ids=list(policy_ids or []),
    )


def document_to_out(document: Document, policy_id: UUID | None = None) -> DocumentOut:
    return DocumentOut.model_validate(document).model_copy(
        update={"policy_id": policy_id}
    )
