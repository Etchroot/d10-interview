"""질문 고르기 · 점수 계산 · 비교 · 리포트. AI 호출 없이 코드로만 계산한다."""

import random
from pathlib import Path

import pandas as pd

TOTAL_QUESTIONS = 5
MAX_FOLLOW_UPS = 1          # 질문 하나당 꼬리 질문 최대 개수
MAX_CLARIFY = 1             # 질문 하나당 "무슨 뜻이에요?" 다시 설명 최대 개수 (꼬리 질문과 따로 셈)
CODE_QUESTION_COUNT = 2     # 코드 면접 꼬리 질문 개수
CODE_MIN_LINES, CODE_MAX_LINES = 10, 20
PASS_SCORE = 14             # 답변 점수(0~20)가 이보다 낮으면 고친 답을 보여 준다
CRITERIA = {"specific": "구체성", "relevance": "직무 연관", "structure": "구조", "evidence": "근거 · 검증"}
MIN_EXPERIENCE_CHARS = 30

# 화면에 보이는 직군 → (질문 은행의 직무 질문 직군, 경험 · 상황 질문 직군 목록)
TRACKS = {
    "백엔드 개발": ("백엔드", ["백엔드", "개발"]),
    "프론트엔드 개발": ("프론트엔드", ["프론트엔드", "개발"]),
    "디자인": ("디자인", ["디자인"]),
    "PO": ("PO", ["PO"]),
    "마케팅": ("마케팅", ["마케팅"]),
}
DEV_TRACKS = {"백엔드 개발", "프론트엔드 개발"}

DATA_PATH = Path(__file__).parent / "data" / "questions.csv"


def load_questions(path=DATA_PATH):
    return pd.read_csv(path, encoding="utf-8-sig")


def persona_key(track):
    return TRACKS[track][0]


def pick_questions(df, track, seed=None):
    """자기소개 1 + 공통 1 + 직무 1 + 경험 1 + 상황 1 = 5개. 순서도 코드가 정한다."""
    rnd = random.Random(seed)
    job_key, pool = TRACKS[track]
    common = df[df["직군"] == "공통"]
    intro = common[common["질문"].str.contains("자기소개")]
    others = common.drop(intro.index)

    def one(rows):
        return rows.iloc[rnd.randrange(len(rows))]

    picked = [
        intro.iloc[0],
        one(others),
        one(df[(df["직군"] == job_key) & (df["유형"] == "직무")]),
        one(df[df["직군"].isin(pool) & (df["유형"] == "경험")]),
        one(df[df["직군"].isin(pool) & (df["유형"] == "상황")]),
    ]
    return [
        {"no": i + 1, "type": row["유형"], "question": row["질문"], "point": row["보는 점"]}
        for i, row in enumerate(picked[:TOTAL_QUESTIONS])
    ]


def can_follow_up(follow_ups_done):
    return follow_ups_done < MAX_FOLLOW_UPS


def can_clarify(clarify_done):
    return clarify_done < MAX_CLARIFY


def clamp(value, low, high):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, value))


def experience_ok(text):
    return len((text or "").strip()) >= MIN_EXPERIENCE_CHARS


def code_line_count(code):
    return len([line for line in (code or "").splitlines() if line.strip()])


def format_turns(turns):
    return "\n".join(f"{'면접관' if t['role'] == 'assistant' else '지원자'}: {t['content']}" for t in turns)


def format_transcript(questions, transcript):
    """평가 위원회에 넘길 면접 기록. 질문 번호는 코드가 붙인다."""
    blocks = []
    for q in questions:
        turns = transcript.get(q["no"], [])
        if turns:
            blocks.append(f"[질문 {q['no']}] {q['question']}\n[보는 점] {q['point']}\n{format_turns(turns)}")
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# 점수 — AI가 준 점수는 범위로 자르고, 합계 · 평균은 여기서 다시 계산
# ---------------------------------------------------------------------------
def clean_panel(panel):
    return [{**p, "score": clamp(p.get("score"), 0, 10)} for p in panel]


def panel_average(panel):
    scores = [clamp(p.get("score"), 0, 10) for p in panel]
    return round(sum(scores) / len(scores), 1) if scores else 0.0


def criteria_scores(answer):
    return {key: clamp(answer.get(key), 0, 5) for key in CRITERIA}


def answer_total(answer):
    return sum(criteria_scores(answer).values())


def needs_rewrite(answer):
    return answer_total(answer) < PASS_SCORE


def clean_evaluation(result, questions):
    """위원 점수 · 기준 점수를 잘라 쓰고, 면접에 없는 질문 번호는 버린다."""
    valid = {q["no"] for q in questions}
    answers = []
    for a in result.get("answers", []):
        if a.get("no") in valid and a["no"] not in {x["no"] for x in answers}:
            answers.append({**a, **criteria_scores(a), "total": answer_total(a)})
    return {
        **result,
        "panel": clean_panel(result.get("panel", [])),
        "panel_avg": panel_average(result.get("panel", [])),
        "answers": sorted(answers, key=lambda a: a["no"]),
        "answers_total": sum(a["total"] for a in answers),
        "answers_max": 20 * len(answers),
    }


def weakest_first(answers):
    return sorted(answers, key=lambda a: (a["total"], a["no"]))


def compare(before, after):
    """전 → 후 비교. 기준별 점수와 합계 차이를 코드가 계산한다."""
    b, a = criteria_scores(before), criteria_scores(after)
    rows = [{"기준": CRITERIA[k], "전": b[k], "후": a[k], "차이": a[k] - b[k]} for k in CRITERIA]
    return {
        "before_total": sum(b.values()),
        "after_total": sum(a.values()),
        "delta": sum(a.values()) - sum(b.values()),
        "rows": rows,
    }


def clean_code_questions(result):
    return {**result, "questions": result.get("questions", [])[:CODE_QUESTION_COUNT]}


def clean_code_review(result):
    answers = [{**a, "score": clamp(a.get("score"), 0, 5)} for a in result.get("answers", [])][:CODE_QUESTION_COUNT]
    facts = [{**f, "confidence": clamp(f.get("confidence"), 0, 100)} for f in result.get("fact_check", [])]
    return {
        **result,
        "answers": answers,
        "fact_check": facts,
        "total": sum(a["score"] for a in answers),
        "max": 5 * len(answers),
    }


# ---------------------------------------------------------------------------
# 리포트 (BAB: 전 → 후 → 다음) — 숫자는 모두 위에서 코드가 계산한 값
# ---------------------------------------------------------------------------
def build_report(profile, questions, transcript, evaluation, retries, code_result=None, last_questions=None):
    lines = [
        f"# 면접 리포트 — {profile['name']} ({profile['track']} 신입)",
        "",
        f"- 회사: {profile['company']}",
        f"- 질문 수: {len(questions)} / {TOTAL_QUESTIONS}",
        "",
    ]
    if evaluation:
        lines += [
            "## 위원 4명 평가",
            f"- 위원 평균: **{evaluation['panel_avg']} / 10**",
            f"- 답변 합계: **{evaluation['answers_total']} / {evaluation['answers_max']}**",
            "",
            "| 위원 | 점수 | 뽑지 말아야 할 이유 | 좋은 점 |",
            "| --- | --- | --- | --- |",
        ]
        lines += [f"| {p['role']} | {p['score']} | {p['against']} | {p['good']} |" for p in evaluation["panel"]]
        lines += ["", f"- 갈린 곳: {evaluation.get('conflict', '')}", f"- 같은 판단: {evaluation.get('agree', '')}", ""]
        lines += ["## 답변별 점수", "", "| 질문 | 구체성 | 직무 연관 | 구조 | 근거 · 검증 | 합계 |", "| --- | --- | --- | --- | --- | --- |"]
        for a in evaluation["answers"]:
            lines.append(f"| Q{a['no']} | {a['specific']} | {a['relevance']} | {a['structure']} | {a['evidence']} | {a['total']}/20 |")
        lines += ["", "## 다음 연습에서 고칠 것"] + [f"- {n}" for n in evaluation.get("next", [])] + [""]
    if retries:
        lines += ["## 재도전 (전 → 후)", "", "| 질문 | 전 | 후 | 차이 |", "| --- | --- | --- | --- |"]
        for r in retries:
            c = r["compare"]
            lines.append(f"| Q{r['no']} | {c['before_total']} | {c['after_total']} | {c['delta']:+d} |")
        lines.append("")
    if code_result:
        lines += [f"## 코드 면접", f"- 점수: {code_result['total']} / {code_result['max']}", ""]
    if last_questions:
        lines += ["## 면접관에게 할 마지막 질문"] + [f"- {q}" for q in last_questions] + [""]
    lines += ["## 면접 기록", ""]
    for q in questions:
        lines.append(f"### Q{q['no']}. {q['question']}")
        for turn in transcript.get(q["no"], []):
            who = "면접관" if turn["role"] == "assistant" else "나"
            lines.append(f"- **{who}**: {turn['content']}")
        lines.append("")
    return "\n".join(lines)
