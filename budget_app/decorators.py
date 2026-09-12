"""CLI의 공통 관심사를 분리하는 데코레이터."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec

from .models import AppError


P = ParamSpec("P")


def cli_error_boundary(function: Callable[P, int]) -> Callable[P, int]:
    """예상 가능한 오류를 스택트레이스 없이 일관된 종료 코드로 바꾼다."""

    @wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> int:
        try:
            return function(*args, **kwargs)
        except (AppError, OSError) as exc:
            print(f"[오류] {exc}")
            print("입력값과 --help 사용법을 확인한 뒤 다시 시도하세요.")
            return 1
        except (EOFError, KeyboardInterrupt):
            print("\n[취소] 입력이 중단되었습니다.")
            return 130

    return wrapper

