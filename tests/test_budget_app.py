from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from budget_app.models import ValidationError
from budget_app.services import BudgetService


class BudgetServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary_directory.name)
        self.service = BudgetService(self.data_dir)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def add_expense(self, amount: int = 15000):
        return self.service.add_transaction(
            transaction_date="2024-01-15",
            transaction_type="expense",
            category="food",
            amount=amount,
            memo="점심",
            tags=("meal",),
        )

    def test_initializes_three_storage_files_and_categories(self) -> None:
        self.assertTrue((self.data_dir / "transactions.jsonl").exists())
        self.assertTrue((self.data_dir / "categories.jsonl").exists())
        self.assertTrue((self.data_dir / "budgets.jsonl").exists())
        self.assertIn("food", list(self.service.categories.iter_all()))

    def test_add_list_search_update_and_delete(self) -> None:
        transaction = self.add_expense()
        self.assertEqual("TX-000001", transaction.id)
        self.assertEqual([transaction], self.service.list_transactions(10))
        self.assertEqual([transaction], self.service.search(tag="meal", query="점심"))
        self.assertTrue(self.service.update_transaction(transaction.id, amount=20000))
        self.assertEqual(20000, self.service.list_transactions(1)[0].amount)
        self.assertTrue(self.service.delete_transaction(transaction.id))
        self.assertEqual([], self.service.list_transactions(10))

    def test_summary_and_budget_warning_data(self) -> None:
        self.add_expense(15000)
        self.service.set_budget("2024-01", 10000)
        result = self.service.monthly_summary("2024-01", 3)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(15000, result["expense"])
        self.assertEqual(10000, result["budget"])
        self.assertEqual([("food", 15000)], result["top"])

    def test_category_in_use_cannot_be_removed(self) -> None:
        self.add_expense()
        with self.assertRaises(ValidationError):
            self.service.remove_category("food")

    def test_export_and_import_csv(self) -> None:
        self.add_expense()
        output = self.data_dir / "output.csv"
        self.assertEqual(
            1,
            self.service.export_csv(
                output, month="2024-01", date_from=None, date_to=None
            ),
        )
        other = BudgetService(self.data_dir / "other")
        self.assertEqual(1, other.import_csv(output))
        self.assertEqual(1, len(other.list_transactions(10)))
        with output.open(encoding="utf-8") as file:
            self.assertEqual(
                ["date", "type", "category", "amount", "memo", "tags"],
                next(csv.reader(file)),
            )


if __name__ == "__main__":
    unittest.main()

