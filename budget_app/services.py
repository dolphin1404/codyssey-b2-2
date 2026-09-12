"""업무 규칙을 담당하는 서비스 계층."""

from __future__ import annotations

import csv
import heapq
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

from .models import (
    AppError,
    Transaction,
    ValidationError,
    validate_amount,
    validate_date,
    validate_month,
    validate_type,
)
from .repositories import BudgetStore, CategoryStore, TransactionRepository


CSV_COLUMNS = ("date", "type", "category", "amount", "memo", "tags")


class BudgetService:
    def __init__(self, data_dir: Path) -> None:
        self.transactions = TransactionRepository(data_dir)
        self.categories = CategoryStore(data_dir)
        self.budgets = BudgetStore(data_dir)

    def _validate_category(self, category: str) -> str:
        if not self.categories.contains(category):
            raise ValidationError(
                f"등록되지 않은 카테고리입니다: {category}. "
                "'category add'로 먼저 등록하세요."
            )
        return category

    def add_transaction(
        self,
        *,
        transaction_date: str,
        transaction_type: str,
        category: str,
        amount: int,
        memo: str = "",
        tags: tuple[str, ...] = (),
    ) -> Transaction:
        transaction = Transaction(
            id=self.transactions.next_id(),
            type=validate_type(transaction_type),
            date=validate_date(transaction_date),
            amount=validate_amount(amount),
            category=self._validate_category(category),
            memo=memo,
            tags=tags,
        )
        self.transactions.add(transaction)
        return transaction

    def list_transactions(self, limit: int) -> list[Transaction]:
        if limit <= 0:
            raise ValidationError("--limit은 1 이상의 정수여야 합니다.")
        return heapq.nlargest(limit, self.transactions.iter_all(), key=self._sort_key)

    @staticmethod
    def _sort_key(transaction: Transaction) -> tuple[str, str]:
        return transaction.date, transaction.id

    def search(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        category: str | None = None,
        transaction_type: str | None = None,
        query: str | None = None,
        tag: str | None = None,
    ) -> list[Transaction]:
        if date_from:
            validate_date(date_from)
        if date_to:
            validate_date(date_to)
        if date_from and date_to and date_from > date_to:
            raise ValidationError("--from은 --to보다 늦을 수 없습니다.")
        if transaction_type:
            validate_type(transaction_type)

        def matches(transaction: Transaction) -> bool:
            return not any(
                (
                    date_from and transaction.date < date_from,
                    date_to and transaction.date > date_to,
                    category and transaction.category != category,
                    transaction_type and transaction.type != transaction_type,
                    query and query.casefold() not in transaction.memo.casefold(),
                    tag and tag not in transaction.tags,
                )
            )

        return sorted(
            (item for item in self.transactions.iter_all() if matches(item)),
            key=self._sort_key,
            reverse=True,
        )

    def update_transaction(self, transaction_id: str, **changes: object) -> bool:
        current = next(
            (item for item in self.transactions.iter_all() if item.id == transaction_id),
            None,
        )
        if current is None:
            return False
        if "date" in changes:
            validate_date(str(changes["date"]))
        if "type" in changes:
            validate_type(str(changes["type"]))
        if "amount" in changes:
            validate_amount(int(changes["amount"]))
        if "category" in changes:
            self._validate_category(str(changes["category"]))
        updated = replace(current, **changes)
        return self.transactions.replace(transaction_id, updated)

    def delete_transaction(self, transaction_id: str) -> bool:
        return self.transactions.replace(transaction_id, None)

    def monthly_summary(self, month: str, top: int) -> dict[str, object] | None:
        validate_month(month)
        if top <= 0:
            raise ValidationError("--top은 1 이상의 정수여야 합니다.")
        income = 0
        expense = 0
        category_expenses: dict[str, int] = defaultdict(int)
        count = 0
        for transaction in self.transactions.iter_all():
            if not transaction.date.startswith(f"{month}-"):
                continue
            count += 1
            if transaction.type == "income":
                income += transaction.amount
            else:
                expense += transaction.amount
                category_expenses[transaction.category] += transaction.amount
        if count == 0:
            return None
        return {
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "top": sorted(
                category_expenses.items(), key=lambda item: item[1], reverse=True
            )[:top],
            "budget": self.budgets.get(month),
        }

    def set_budget(self, month: str, amount: int) -> None:
        self.budgets.set(validate_month(month), validate_amount(amount))

    def get_budget(self, month: str) -> int | None:
        return self.budgets.get(validate_month(month))

    def add_category(self, name: str) -> bool:
        clean_name = name.strip()
        if not clean_name:
            raise ValidationError("카테고리 이름은 비어 있을 수 없습니다.")
        if any(character.isspace() for character in clean_name):
            raise ValidationError("카테고리 이름에는 공백을 사용할 수 없습니다.")
        return self.categories.add(clean_name)

    def remove_category(self, name: str) -> bool:
        if any(item.category == name for item in self.transactions.iter_all()):
            raise ValidationError(
                f"'{name}' 카테고리를 사용하는 거래가 있어 삭제할 수 없습니다."
            )
        return self.categories.remove(name)

    def import_csv(self, source: Path) -> int:
        if not source.is_file():
            raise ValidationError(f"가져올 CSV 파일을 찾을 수 없습니다: {source}")
        count = 0
        try:
            with source.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                if reader.fieldnames is None or not set(CSV_COLUMNS).issubset(reader.fieldnames):
                    raise ValidationError(
                        "CSV 헤더는 date,type,category,amount,memo,tags를 포함해야 합니다."
                    )
                for row_number, row in enumerate(reader, start=2):
                    try:
                        amount = int(row["amount"])
                        tags = tuple(
                            tag.strip() for tag in row.get("tags", "").split(",") if tag.strip()
                        )
                        self.add_transaction(
                            transaction_date=row["date"],
                            transaction_type=row["type"],
                            category=row["category"],
                            amount=amount,
                            memo=row.get("memo", ""),
                            tags=tags,
                        )
                    except (ValidationError, ValueError) as exc:
                        raise ValidationError(f"CSV {row_number}행 오류: {exc}") from exc
                    count += 1
        except OSError as exc:
            raise AppError(f"CSV 파일을 읽을 수 없습니다: {source}") from exc
        return count

    def export_csv(
        self,
        destination: Path,
        *,
        month: str | None,
        date_from: str | None,
        date_to: str | None,
    ) -> int:
        if month:
            validate_month(month)
        if not any((month, date_from, date_to)):
            raise ValidationError(
                "export에는 --month 또는 --from/--to 조건이 하나 이상 필요합니다."
            )
        items = self.search(date_from=date_from, date_to=date_to)
        if month:
            items = [item for item in items if item.date.startswith(f"{month}-")]
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
                writer.writeheader()
                for item in items:
                    writer.writerow(
                        {
                            "date": item.date,
                            "type": item.type,
                            "category": item.category,
                            "amount": item.amount,
                            "memo": item.memo,
                            "tags": ",".join(item.tags),
                        }
                    )
        except OSError as exc:
            raise AppError(f"CSV 파일을 쓸 수 없습니다: {destination}") from exc
        return len(items)

