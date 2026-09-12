# 나만의 용돈 기입장

Python 표준 라이브러리만 사용하는 JSONL 기반 콘솔 가계부입니다. 거래 CRUD, 검색,
월별 요약, 예산, 카테고리 관리, CSV 가져오기/내보내기를 지원합니다.

## 실행 환경과 방법

- Python 3.10 이상
- 외부 패키지 설치 불필요

```bash
python -m budget_app --help
python -m budget_app <command> --help
```

저장 위치를 바꾸려면 명령 앞에 전역 옵션을 지정합니다.

```bash
python -m budget_app --data-dir ./my-data list
```

## 저장 파일

기본 저장 폴더는 `./data`이며 처음 실행할 때 자동 생성됩니다.

- `data/transactions.jsonl`: 거래 객체를 한 줄에 하나씩 저장
- `data/categories.jsonl`: `{"name": "food"}` 형태의 카테고리
- `data/budgets.jsonl`: `{"month": "2024-01", "amount": 500000}` 형태의 예산

카테고리가 비어 있으면 `food`, `transport`, `rent`, `salary`, `etc`가 자동 생성됩니다.
거래 조회는 JSONL 파일을 한 줄씩 읽는 제너레이터를 사용합니다.

## 주요 명령

`add`는 대화형으로 입력합니다. `update`는 옵션 방식으로 고정했습니다.

```bash
python -m budget_app add
python -m budget_app list --limit 10
python -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food
python -m budget_app search --type expense --q 점심 --tag meal
python -m budget_app update --id TX-000001 --amount 20000 --memo 저녁
python -m budget_app delete --id TX-000001

python -m budget_app summary --month 2024-01 --top 3
python -m budget_app budget set --month 2024-01 --amount 500000
python -m budget_app budget get --month 2024-01

python -m budget_app category list
python -m budget_app category add
python -m budget_app category add --name health
python -m budget_app category remove --name health
```

사용 중인 카테고리는 삭제할 수 없습니다. 모든 명령은 오류 시 원인과 확인 방법을
표시하고 0이 아닌 종료 코드로 끝납니다.

## CSV 가져오기/내보내기

```bash
python -m budget_app import --from transactions.csv
python -m budget_app export --out january.csv --month 2024-01
python -m budget_app export --out range.csv --from 2024-01-01 --to 2024-01-31
```

내보내기에는 `--month` 또는 `--from`/`--to` 조건이 하나 이상 필요합니다.
파일은 UTF-8, 헤더 포함 CSV이고 다음 스키마를 사용합니다.

| column | required | 설명 |
| --- | --- | --- |
| date | Y | YYYY-MM-DD |
| type | Y | `income` 또는 `expense` |
| category | Y | 등록된 카테고리 |
| amount | Y | 양수 정수 |
| memo | N | 문자열 |
| tags | N | 쉼표로 구분한 문자열 |

## 테스트

```bash
python -m unittest discover -v
```

## 구조

- `models.py`: dataclass 모델과 값 검증
- `repositories.py`: 제너레이터 기반 JSONL 파일 입출력
- `services.py`: CRUD, 검색, 요약, 예산, CSV 업무 규칙
- `cli.py`: argparse 명령과 대화형 입력/출력
- `decorators.py`: 공통 예외 처리와 종료 코드 변환 데코레이터

보너스 과제(백업, 반복 내역, 별도 테이블 정렬, 저장 원자성 강화)는 포함하지 않았습니다.
