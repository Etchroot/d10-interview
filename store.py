"""랭킹 · 비교 대시보드용 점수 저장소.

- SUPABASE_URL · SUPABASE_KEY 가 있으면 Supabase(무료 Postgres)의 interview_results 표에 저장 → 배포 앱에서 모두가 같이 봄
- 없으면 data/results.jsonl 에 저장 → 내 PC에서 연습용 (배포 앱에서는 재시작하면 사라짐)

면접 답변 원문은 저장하지 않는다. 별명 · 직군 · 점수(코드가 계산한 숫자)만.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from llm import _setting

LOCAL_PATH = Path(__file__).parent / "data" / "results.jsonl"
TABLE = "interview_results"


class StoreError(Exception):
    """화면에 그대로 보여 줄 한국어 한 줄 에러."""


def _supabase():
    url, key = _setting("SUPABASE_URL"), _setting("SUPABASE_KEY")
    if url and key:
        return url.rstrip("/"), {"apikey": key, "Authorization": f"Bearer {key}"}
    return None


def is_shared():
    return _supabase() is not None


def save(record):
    record = {**record, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    sb = _supabase()
    if sb:
        url, headers = sb
        try:
            r = requests.post(f"{url}/rest/v1/{TABLE}", json=record,
                           headers={**headers, "Prefer": "return=minimal"}, timeout=15)
            r.raise_for_status()
        except requests.RequestException:
            raise StoreError("점수를 저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.") from None
        return record
    LOCAL_PATH.parent.mkdir(exist_ok=True)
    with LOCAL_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load(limit=1000):
    sb = _supabase()
    if sb:
        url, headers = sb
        try:
            r = requests.get(f"{url}/rest/v1/{TABLE}", headers=headers, timeout=15,
                          params={"select": "*", "order": "created_at.desc", "limit": str(limit)})
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            raise StoreError("다른 사람 점수를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.") from None
    if not LOCAL_PATH.exists():
        return []
    rows = []
    for line in LOCAL_PATH.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows[-limit:][::-1]
