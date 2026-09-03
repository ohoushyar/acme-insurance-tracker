import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, Field, model_validator

_MONEY = re.compile(
    r"^(?:(?:US\$|USD|\$)\s*)?([\d,]+(?:\.\d+)?)$",
    re.IGNORECASE,
)


def blank_to_none(value: object) -> object:
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def parse_deductible_amount(value: object) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(Decimal(str(value)), "f")
    raise ValueError("must be a deductible amount")


def parse_strict_money_amount(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, (bool, list, dict)):
        raise ValueError("must be a money amount")  # noqa: TRY004
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if not isinstance(value, str):
        raise ValueError("must be a money amount")  # noqa: TRY004
    text = value.strip()
    if not text:
        return None
    match = _MONEY.fullmatch(text)
    if match is None:
        raise ValueError("must be a money amount")
    try:
        return Decimal(match.group(1).replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError("must be a money amount") from exc


def parse_money_amount(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    try:
        return parse_strict_money_amount(value)
    except ValueError:
        if isinstance(value, str):
            return None
        raise


MoneyAmount = Annotated[Decimal | None, BeforeValidator(parse_money_amount)]
StrictMoneyAmount = Annotated[
    Decimal | None, BeforeValidator(parse_strict_money_amount)
]
OptionalStr = Annotated[str | None, BeforeValidator(blank_to_none)]
DeductibleAmount = Annotated[str | None, BeforeValidator(parse_deductible_amount)]


class Deductible(BaseModel):
    peril: OptionalStr = None
    amount: DeductibleAmount = None


class Location(BaseModel):
    label: OptionalStr = None
    address: OptionalStr = None


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
    policy_number: OptionalStr = None
    named_insured: OptionalStr = None
    broker: OptionalStr = None
    effective_date: date | None = None
    renewal_date: date | None = None
    term_premium: MoneyAmount = None
    policy_fee: MoneyAmount = None
    total_premium: MoneyAmount = None
    limit_of_insurance: MoneyAmount = None
    coverage_type: OptionalStr = None
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


class ConfirmExtractedPolicy(ExtractedPolicy):
    term_premium: StrictMoneyAmount = None
    policy_fee: StrictMoneyAmount = None
    total_premium: StrictMoneyAmount = None
    limit_of_insurance: StrictMoneyAmount = None
