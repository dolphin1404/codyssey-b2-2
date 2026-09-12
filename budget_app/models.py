"""애플리케이션 데이터 모델과 값 검증."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


class AppError(Exception):
    """사용자에게 해결 방법과 함께 보여 줄 수 있는 오류."""


class ValidationError(AppError):
    """입력값이 애플리케이션 규칙에 맞지 않을 때 발생한다."""


def validate_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError("날짜는 YYYY-MM-DD 형식의 실제 날짜여야 합니다.") from exc
    return value


def validate_month(value: str) -> str:
    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as exc:
        raise ValidationError("월은 YYYY-MM 형식이어야 합니다.") from exc
    if value != parsed.strftime("%Y-%m"):
        raise ValidationError("월은 YYYY-MM 형식이어야 합니다.")
    return value


def validate_type(value: str) -> str:
    if value not in {"income", "expense"}:
        raise ValidationError("타입은 income 또는 expense여야 합니다.")
    return value


def validate_amount(value: int) -> int:
    if isinstance(value, bool) or value <= 0:
        raise ValidationError("금액은 0보다 큰 정수여야 합니다.")
    return value


@dataclass(frozen=True, slots=True)
class Transaction:
    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_date(self.date)
        validate_type(self.type)
        validate_amount(self.amount)
        if not self.id:
            raise ValidationError("거래 id가 비어 있습니다.")
        if not self.category.strip():
            raise ValidationError("카테고리가 비어 있습니다.")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["tags"] = list(self.tags)
        return result

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Transaction":
        try:
            return cls(
                id=str(raw["id"]),
                type=str(raw["type"]),
                date=str(raw["date"]),
                amount=int(raw["amount"]),
                category=str(raw["category"]),
                memo=str(raw.get("memo", "")),
                tags=tuple(str(tag) for tag in raw.get("tags", [])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("저장된 거래 데이터 형식이 올바르지 않습니다.") from exc

