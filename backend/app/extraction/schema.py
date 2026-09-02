import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, Field, model_validator

_PAREN_MONEY = re.compile(
    r"\((?:US\$|USD|\$)?\s*([\d,]+(?:\.\d+)?)\s*\)", re.IGNORECASE
)
_PREFIX_MONEY = re.compile(r"(?:US\$|USD|\$)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_PLAIN_NUMBER = re.compile(r"^\s*([\d,]+(?:\.\d+)?)\s*$")


def parse_money_amount(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    match = (
        _PAREN_MONEY.search(text)
        or _PREFIX_MONEY.search(text)
        or _PLAIN_NUMBER.fullmatch(text)
    )
    if match is None:
        return None
    try:
        return Decimal(match.group(1).replace(",", ""))
    except InvalidOperation:
        return None


MoneyAmount = Annotated[Decimal | None, BeforeValidator(parse_money_amount)]


class Deductible(BaseModel):
    peril: str | None = None
    amount: MoneyAmount = None


class Location(BaseModel):
    label: str | None = None
    address: str | None = None


class FieldConfidence(BaseModel):
    policy_number: float = 0
    named_insured: float = 0
    broker: float = 0
    effective_date: float = 0
    renewal_date: float = 0
    term_premium: float = 0
    policy_fee: float = 0
    total_premium: float = 0
    limit_of_insurance: float = 0
    coverage_type: float = 0
    carriers: float = 0
    deductibles: float = 0
    locations: float = 0


class ExtractedPolicy(BaseModel):
    policy_number: str | None = None
    named_insured: str | None = None
    broker: str | None = None
    effective_date: date | None = None
    renewal_date: date | None = None
    term_premium: MoneyAmount = None
    policy_fee: MoneyAmount = None
    total_premium: MoneyAmount = None
    limit_of_insurance: MoneyAmount = None
    coverage_type: str | None = None
    carriers: list[str] = Field(default_factory=list)
    deductibles: list[Deductible] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=list)
    confidence: FieldConfidence = Field(default_factory=FieldConfidence)

    @model_validator(mode="after")
    def zero_confidence_when_scalar_missing(self) -> Self:
        scalars = {
            "policy_number": self.policy_number,
            "named_insured": self.named_insured,
            "broker": self.broker,
            "effective_date": self.effective_date,
            "renewal_date": self.renewal_date,
            "term_premium": self.term_premium,
            "policy_fee": self.policy_fee,
            "total_premium": self.total_premium,
            "limit_of_insurance": self.limit_of_insurance,
            "coverage_type": self.coverage_type,
        }
        for name, value in scalars.items():
            if value is None:
                setattr(self.confidence, name, 0)
        return self
