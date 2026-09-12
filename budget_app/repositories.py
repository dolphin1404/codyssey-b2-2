"""JSONL 파일을 사용하는 저장소 계층."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .models import AppError, Transaction


DEFAULT_CATEGORIES = ("food", "transport", "rent", "salary", "etc")


class JsonlStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def iter_records(self) -> Iterator[dict[str, Any]]:
        """파일 전체를 메모리에 올리지 않고 한 줄씩 반환한다."""
        try:
            with self.path.open("r", encoding="utf-8") as file:
                for line_number, line in enumerate(file, start=1):
                    if not line.strip():
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise AppError(
                            f"{self.path}의 {line_number}번째 줄이 올바른 JSON이 아닙니다."
                        ) from exc
                    if not isinstance(raw, dict):
                        raise AppError(
                            f"{self.path}의 {line_number}번째 줄은 JSON 객체여야 합니다."
                        )
                    yield raw
        except OSError as exc:
            raise AppError(f"저장 파일을 읽을 수 없습니다: {self.path}") from exc

    def append(self, record: dict[str, Any]) -> None:
        try:
            with self.path.open("a", encoding="utf-8") as file:
                json.dump(record, file, ensure_ascii=False)
                file.write("\n")
        except OSError as exc:
            raise AppError(f"저장 파일에 쓸 수 없습니다: {self.path}") from exc

    def rewrite(self, records: Iterator[dict[str, Any]]) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as file:
                for record in records:
                    json.dump(record, file, ensure_ascii=False)
                    file.write("\n")
        except OSError as exc:
            raise AppError(f"저장 파일을 다시 쓸 수 없습니다: {self.path}") from exc


class TransactionRepository:
    def __init__(self, data_dir: Path) -> None:
        self.store = JsonlStore(data_dir / "transactions.jsonl")

    def iter_all(self) -> Iterator[Transaction]:
        for raw in self.store.iter_records():
            yield Transaction.from_dict(raw)

    def add(self, transaction: Transaction) -> None:
        self.store.append(transaction.to_dict())

    def next_id(self) -> str:
        greatest = 0
        for transaction in self.iter_all():
            if transaction.id.startswith("TX-"):
                try:
                    greatest = max(greatest, int(transaction.id[3:]))
                except ValueError:
                    continue
        return f"TX-{greatest + 1:06d}"

    def replace(self, target_id: str, replacement: Transaction | None) -> bool:
        found = False

        def changed_records() -> Iterator[dict[str, Any]]:
            nonlocal found
            for transaction in self.iter_all():
                if transaction.id == target_id:
                    found = True
                    if replacement is not None:
                        yield replacement.to_dict()
                else:
                    yield transaction.to_dict()

        # 제너레이터가 소비되는 동안 같은 파일을 덮어쓰지 않도록 한 번만 수집한다.
        records = list(changed_records())
        if found:
            self.store.rewrite(iter(records))
        return found


class CategoryStore:
    def __init__(self, data_dir: Path) -> None:
        self.store = JsonlStore(data_dir / "categories.jsonl")
        if not any(self.store.iter_records()):
            for name in DEFAULT_CATEGORIES:
                self.store.append({"name": name})

    def iter_all(self) -> Iterator[str]:
        for record in self.store.iter_records():
            name = record.get("name")
            if isinstance(name, str) and name:
                yield name

    def contains(self, name: str) -> bool:
        return any(category == name for category in self.iter_all())

    def add(self, name: str) -> bool:
        if self.contains(name):
            return False
        self.store.append({"name": name})
        return True

    def remove(self, name: str) -> bool:
        categories = [category for category in self.iter_all() if category != name]
        if len(categories) == sum(1 for _ in self.iter_all()):
            return False
        self.store.rewrite(iter({"name": category} for category in categories))
        return True


class BudgetStore:
    def __init__(self, data_dir: Path) -> None:
        self.store = JsonlStore(data_dir / "budgets.jsonl")

    def get(self, month: str) -> int | None:
        result: int | None = None
        for record in self.store.iter_records():
            if record.get("month") == month:
                result = int(record["amount"])
        return result

    def set(self, month: str, amount: int) -> None:
        records = [
            record for record in self.store.iter_records() if record.get("month") != month
        ]
        records.append({"month": month, "amount": amount})
        self.store.rewrite(iter(records))

