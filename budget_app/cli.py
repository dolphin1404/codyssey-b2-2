"""명령행 인터페이스."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .decorators import cli_error_boundary
from .models import Transaction, ValidationError, validate_amount, validate_date, validate_type
from .services import BudgetService


def positive_int(value: str) -> int:
    try:
        return validate_amount(int(value))
    except (ValueError, ValidationError) as exc:
        raise argparse.ArgumentTypeError("0보다 큰 정수를 입력하세요.") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="나만의 용돈 기입장")
    parser.add_argument(
        "--data-dir", type=Path, default=Path("data"), help="저장 폴더 (기본: ./data)"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("add", help="거래를 대화형으로 추가")

    list_parser = commands.add_parser("list", help="최신 거래 목록")
    list_parser.add_argument("--limit", type=positive_int, default=10)

    search = commands.add_parser("search", help="조건으로 거래 검색")
    search.add_argument("--from", dest="date_from")
    search.add_argument("--to", dest="date_to")
    search.add_argument("--category")
    search.add_argument("--type", choices=("income", "expense"))
    search.add_argument("--q", help="메모 키워드")
    search.add_argument("--tag")

    summary = commands.add_parser("summary", help="월별 요약")
    summary.add_argument("--month", required=True)
    summary.add_argument("--top", type=positive_int, default=3)

    budget = commands.add_parser("budget", help="월 예산 설정/조회")
    budget_commands = budget.add_subparsers(dest="budget_command", required=True)
    budget_set = budget_commands.add_parser("set", help="예산 설정")
    budget_set.add_argument("--month", required=True)
    budget_set.add_argument("--amount", type=positive_int, required=True)
    budget_get = budget_commands.add_parser("get", help="예산 조회")
    budget_get.add_argument("--month", required=True)

    category = commands.add_parser("category", help="카테고리 관리")
    category_commands = category.add_subparsers(dest="category_command", required=True)
    category_add = category_commands.add_parser("add", help="카테고리 추가")
    category_add.add_argument("--name")
    category_commands.add_parser("list", help="카테고리 목록")
    category_remove = category_commands.add_parser("remove", help="카테고리 삭제")
    category_remove.add_argument("--name", required=True)

    update = commands.add_parser("update", help="id로 거래 수정")
    update.add_argument("--id", required=True)
    update.add_argument("--date")
    update.add_argument("--type", choices=("income", "expense"))
    update.add_argument("--category")
    update.add_argument("--amount", type=positive_int)
    update.add_argument("--memo")
    update.add_argument("--tags", help="쉼표로 구분")

    delete = commands.add_parser("delete", help="id로 거래 삭제")
    delete.add_argument("--id", required=True)

    importer = commands.add_parser("import", help="CSV 가져오기")
    importer.add_argument("--from", dest="source", type=Path, required=True)

    exporter = commands.add_parser("export", help="CSV 내보내기")
    exporter.add_argument("--out", type=Path, required=True)
    exporter.add_argument("--month")
    exporter.add_argument("--from", dest="date_from")
    exporter.add_argument("--to", dest="date_to")
    return parser


def _ask(prompt: str, validator: object | None = None) -> str:
    while True:
        value = input(prompt).strip()
        try:
            if callable(validator):
                validator(value)
            return value
        except ValidationError as exc:
            print(f"[입력 오류] {exc}")


def _ask_amount() -> int:
    while True:
        raw = input("금액(양수 정수): ").strip()
        try:
            return validate_amount(int(raw))
        except (ValueError, ValidationError):
            print("[입력 오류] 금액은 0보다 큰 정수여야 합니다.")


def _print_transactions(items: list[Transaction]) -> None:
    if not items:
        print("거래 내역이 없습니다.")
        return
    for item in items:
        tags = f" [{','.join(item.tags)}]" if item.tags else ""
        print(
            f"{item.id} | {item.date} | {item.type} | {item.category} | "
            f"{item.amount} | {item.memo}{tags}"
        )


@cli_error_boundary
def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = BudgetService(args.data_dir)

    if args.command == "add":
        transaction_date = _ask("날짜(YYYY-MM-DD): ", validate_date)
        transaction_type = _ask("타입(income/expense): ", validate_type)
        while True:
            category = _ask("카테고리: ")
            if service.categories.contains(category):
                break
            print("[입력 오류] 등록되지 않은 카테고리입니다. category list를 확인하세요.")
        transaction = service.add_transaction(
            transaction_date=transaction_date,
            transaction_type=transaction_type,
            category=category,
            amount=_ask_amount(),
            memo=input("메모(선택): ").strip(),
            tags=tuple(
                tag.strip()
                for tag in input("태그(쉼표 구분, 선택): ").split(",")
                if tag.strip()
            ),
        )
        print(f"[저장 완료] id={transaction.id}")
    elif args.command == "list":
        _print_transactions(service.list_transactions(args.limit))
    elif args.command == "search":
        _print_transactions(
            service.search(
                date_from=args.date_from,
                date_to=args.date_to,
                category=args.category,
                transaction_type=args.type,
                query=args.q,
                tag=args.tag,
            )
        )
    elif args.command == "summary":
        result = service.monthly_summary(args.month, args.top)
        if result is None:
            print(f"{args.month}: 데이터 없음")
        else:
            print(f"총 수입: {result['income']}원")
            print(f"총 지출: {result['expense']}원")
            print(f"잔액: {result['balance']}원")
            budget = result["budget"]
            if isinstance(budget, int):
                rate = float(result["expense"]) / budget * 100
                print(f"예산: {budget}원 (사용률 {rate:.1f}%)")
                if int(result["expense"]) > budget:
                    print("[경고] 월 예산을 초과했습니다.")
            print(f"\n지출 TOP {args.top}")
            for rank, (category, amount) in enumerate(result["top"], start=1):
                print(f"{rank}) {category} {amount}원")
    elif args.command == "budget":
        if args.budget_command == "set":
            service.set_budget(args.month, args.amount)
            print(f"[저장 완료] {args.month} 예산 {args.amount}원")
        else:
            amount = service.get_budget(args.month)
            print(f"{args.month} 예산: {amount}원" if amount is not None else "설정된 예산이 없습니다.")
    elif args.command == "category":
        if args.category_command == "list":
            for category in service.categories.iter_all():
                print(f"- {category}")
        elif args.category_command == "add":
            name = args.name or input("카테고리명: ").strip()
            if service.add_category(name):
                print(f"[저장 완료] category={name}")
            else:
                print(f"[안내] 이미 존재하는 카테고리입니다: {name}")
        elif service.remove_category(args.name):
            print(f"[삭제 완료] category={args.name}")
        else:
            print(f"[안내] 없는 카테고리입니다: {args.name}")
    elif args.command == "update":
        changes = {
            key: value
            for key, value in {
                "date": args.date,
                "type": args.type,
                "category": args.category,
                "amount": args.amount,
                "memo": args.memo,
                "tags": tuple(tag.strip() for tag in args.tags.split(",") if tag.strip())
                if args.tags is not None
                else None,
            }.items()
            if value is not None
        }
        if not changes:
            raise ValidationError("수정할 옵션을 하나 이상 지정하세요.")
        print("[수정 완료]" if service.update_transaction(args.id, **changes) else "[실패] 없는 id입니다.")
    elif args.command == "delete":
        print("[삭제 완료]" if service.delete_transaction(args.id) else "[실패] 없는 id입니다.")
    elif args.command == "import":
        count = service.import_csv(args.source)
        print(f"[완료] {count} records imported")
    elif args.command == "export":
        count = service.export_csv(
            args.out, month=args.month, date_from=args.date_from, date_to=args.date_to
        )
        print(f"[완료] {args.out} ({count} records)")
    return 0
