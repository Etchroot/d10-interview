"""AI 면접 코치 — Streamlit 화면만. 프롬프트는 prompts.py, API 호출은 llm.py, 계산은 coach.py."""

import pandas as pd
import streamlit as st

import coach
import prompts
from llm import LLMError, ask_json, is_demo, model_name

st.set_page_config(page_title="AI 면접 코치", page_icon="🎤", layout="wide")

DEFAULTS = {
    "stage": "start",          # start → interview → done
    "profile": None,
    "questions": [],
    "idx": 0,                  # 지금 질문 (0부터)
    "follow_ups": 0,           # 지금 질문에서 한 꼬리 질문 수
    "clarifies": 0,            # 지금 질문에서 "무슨 뜻이에요?"에 다시 설명한 수
    "messages": [],
    "transcript": {},          # {질문 번호: [대화]}
    "understanding": 0,
    "evaluation": None,
    "retries": [],
    "code": None,
    "code_review": None,
    "last_questions": None,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value
ss = st.session_state


def reset():
    for key, value in DEFAULTS.items():
        ss[key] = value.copy() if isinstance(value, (list, dict)) else value


def call(instructions, user_input, schema, name, kind="main", waiting="면접관이 생각 중이에요…"):
    """AI 호출 + 한국어 한 줄 에러. 실패하면 None."""
    try:
        with st.spinner(waiting):
            return ask_json(instructions, user_input, schema, name, kind)
    except LLMError as e:
        st.error(str(e))
        return None


def context():
    p = ss.profile
    return prompts.CONTEXT.format(company=p["company"], job=p["track"], experience=p["experience"])


def persona():
    return prompts.PERSONAS[coach.persona_key(ss.profile["track"])]


def say(content, role="assistant"):
    no = ss.questions[min(ss.idx, len(ss.questions) - 1)]["no"]
    ss.messages.append({"role": role, "content": content})
    ss.transcript.setdefault(no, []).append({"role": role, "content": content})


def ask_current():
    q = ss.questions[ss.idx]
    say(f"**Q{q['no']}/{coach.TOTAL_QUESTIONS}.** {q['question']}")


# ---------------------------------------------------------------------------
# 사이드바 상태창
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("📟 상태창")
    if ss.profile:
        st.caption(f"{ss.profile['name']} · {ss.profile['track']} · {ss.profile['company']}")
    done_count = coach.TOTAL_QUESTIONS if ss.stage == "done" else ss.idx
    st.progress(done_count / coach.TOTAL_QUESTIONS, text=f"질문 {min(done_count + (ss.stage == 'interview'), coach.TOTAL_QUESTIONS)}/{coach.TOTAL_QUESTIONS}")
    st.metric("면접관이 본 직무 이해도", f"{ss.understanding} / 100")
    if ss.stage == "interview":
        st.caption(f"이번 질문 꼬리 질문: {ss.follow_ups}/{coach.MAX_FOLLOW_UPS}")
    if st.button("🔄 처음부터 다시", use_container_width=True):
        reset()
        st.rerun()
    st.divider()
    st.caption("🧪 데모 모드 (API 호출 없음)" if is_demo() else f"모델: {model_name()}")

st.title("🎤 AI 면접 코치")
st.caption("클래스로(수업용 가상 회사) 신입 모의면접 · 면접 5문제 → 위원 4명 평가 → 재도전")

# ---------------------------------------------------------------------------
# ① 시작
# ---------------------------------------------------------------------------
if ss.stage == "start":
    with st.form("start"):
        col1, col2 = st.columns(2)
        name = col1.text_input("이름 (별명 가능)", placeholder="실제 개인정보는 넣지 마세요")
        track = col2.selectbox("지원 직군", list(coach.TRACKS), index=0)
        company = st.text_input("회사", value="클래스로")
        experience = st.text_area(
            f"내 경험 ({coach.MIN_EXPERIENCE_CHARS}자 이상)",
            height=140,
            placeholder="예: 팀 프로젝트로 FastAPI + SQLite 수강 신청 API를 만들었고, 동시에 신청하면 정원이 넘는 버그를 트랜잭션으로 고쳤어요. AI가 짠 코드는 pytest로 확인했어요.",
        )
        submitted = st.form_submit_button("면접 시작", type="primary")
    if submitted:
        if not name.strip() or not company.strip():
            st.warning("이름과 회사를 채워 주세요.")
        elif not coach.experience_ok(experience):
            st.warning(f"경험을 {coach.MIN_EXPERIENCE_CHARS}자 이상 적어 주세요. 지금 {len(experience.strip())}자예요. 경험이 구체적일수록 꼬리 질문이 좋아져요.")
        else:
            reset()
            ss.profile = {"name": name.strip(), "track": track, "company": company.strip(), "experience": experience.strip()}
            ss.questions = coach.pick_questions(coach.load_questions(), track)
            ss.stage = "interview"
            say(f"안녕하세요, {ss.profile['name']}님. {track} 면접을 시작할게요. 질문은 {coach.TOTAL_QUESTIONS}개예요.")
            ask_current()
            st.rerun()
    with st.expander("면접관 미리 보기"):
        for label, (key, _) in coach.TRACKS.items():
            st.markdown(f"**{label}** — {prompts.PERSONAS[key]}")
    st.stop()

# ---------------------------------------------------------------------------
# 탭
# ---------------------------------------------------------------------------
tab_names = ["🎤 면접", "📊 평가", "🔁 재도전"]
is_dev = ss.profile["track"] in coach.DEV_TRACKS
if is_dev:
    tab_names.append("💻 코드 면접")
tab_names.append("📄 리포트")
tabs = st.tabs(tab_names)
tab_interview, tab_eval, tab_retry = tabs[:3]
tab_code = tabs[3] if is_dev else None
tab_report = tabs[-1]

# ---------------------------------------------------------------------------
# ② 면접
# ---------------------------------------------------------------------------
with tab_interview:
    for m in ss.messages:
        with st.chat_message(m["role"], avatar="🧑‍💼" if m["role"] == "assistant" else "🙋"):
            st.markdown(m["content"])

    if ss.stage == "interview":
        answer = st.chat_input("답변을 입력하세요 (질문 뜻을 되물어도 돼요)")
        if answer:
            say(answer, role="user")
            q = ss.questions[ss.idx]
            result = call(
                prompts.INTERVIEWER.format(persona=persona(), context=context(), question=q["question"], point=q["point"]),
                coach.format_turns(ss.transcript[q["no"]]),
                prompts.INTERVIEWER_SCHEMA,
                "interviewer",
            )
            if result is None:
                # 실패하면 방금 답을 되돌려 다시 입력할 수 있게
                ss.messages.pop()
                ss.transcript[q["no"]].pop()
            else:
                ss.understanding = coach.clamp(result["understanding"], 0, 100)
                wants_more = result["follow_up"] and result["follow_up_question"].strip()
                # 되묻기("무슨 뜻이에요?")에 다시 설명하는 건 꼬리 질문 횟수와 따로 센다
                if wants_more and result["clarify"] and coach.can_clarify(ss.clarifies):
                    ss.clarifies += 1
                    say(f"{result['reaction']}\n\n↳ {result['follow_up_question']}")
                # 꼬리 질문 횟수는 코드가 막는다 — AI가 더 묻자고 해도 MAX_FOLLOW_UPS 를 넘지 않음
                elif wants_more and not result["clarify"] and coach.can_follow_up(ss.follow_ups):
                    ss.follow_ups += 1
                    say(f"{result['reaction']}\n\n↳ {result['follow_up_question']}")
                else:
                    say(result["reaction"])
                    ss.idx += 1
                    ss.follow_ups = 0
                    ss.clarifies = 0
                    if ss.idx < len(ss.questions):
                        ask_current()
                    else:
                        ss.stage = "done"
                        ss.idx = len(ss.questions) - 1
                        say("면접은 여기까지예요. 수고하셨습니다. 📊 평가 탭에서 위원 4명에게 평가받아 보세요.")
                st.rerun()
    else:
        st.success("면접이 끝났어요. 📊 평가 탭으로 가 보세요.")

# ---------------------------------------------------------------------------
# ③ 평가 — 위원 4명 · 반론 먼저 · 점수 계산은 coach.py
# ---------------------------------------------------------------------------
with tab_eval:
    if st.button("위원 4명에게 평가받기", type="primary"):
        if ss.stage != "done":
            st.warning("면접 5문제를 끝까지 마친 뒤 평가받을 수 있어요.")
        else:
            result = call(
                prompts.EVALUATOR.format(context=context(), job=ss.profile["track"]),
                coach.format_transcript(ss.questions, ss.transcript),
                prompts.EVAL_SCHEMA,
                "evaluator",
                kind="eval",
                waiting="위원 4명이 면접 기록을 읽는 중이에요… (30초~1분)",
            )
            if result:
                ss.evaluation = coach.clean_evaluation(result, ss.questions)
                ss.retries = []

    ev = ss.evaluation
    if ev:
        c1, c2 = st.columns(2)
        c1.metric("위원 평균", f"{ev['panel_avg']} / 10")
        c2.metric("답변 합계", f"{ev['answers_total']} / {ev['answers_max']}")
        st.dataframe(
            pd.DataFrame(ev["panel"]).rename(columns={"role": "위원", "score": "점수", "against": "뽑지 말아야 할 이유 (반론 먼저)", "good": "좋은 점"})[
                ["위원", "점수", "뽑지 말아야 할 이유 (반론 먼저)", "좋은 점"]
            ],
            hide_index=True,
            use_container_width=True,
        )
        st.markdown(f"**⚡ 판단이 갈린 곳** — {ev['conflict']}")
        st.markdown(f"**🤝 모두 같은 판단** — {ev['agree']}")

        st.subheader("답변별 점수")
        q_by_no = {q["no"]: q for q in ss.questions}
        for a in ev["answers"]:
            flag = "🔧" if coach.needs_rewrite(a) else "✅"
            with st.expander(f"{flag} Q{a['no']} · {a['total']}/20 — {q_by_no[a['no']]['question']}"):
                st.dataframe(
                    pd.DataFrame([{coach.CRITERIA[k]: a[k] for k in coach.CRITERIA}]),
                    hide_index=True,
                    use_container_width=True,
                )
                st.markdown(f"**가장 약한 점** — {a['weak']}")
                if coach.needs_rewrite(a):
                    st.markdown("**고친 답** (내 경험으로만, `[확인 필요]`는 내가 채울 칸)")
                    st.info(a["rewrite"])
                    if a["check"]:
                        st.markdown("**사람이 확인할 것**")
                        for c in a["check"]:
                            st.markdown(f"- {c}")
                else:
                    st.caption(f"{coach.PASS_SCORE}점 이상이라 고친 답은 생략해요.")
        st.subheader("다음 연습에서 고칠 것")
        for n in ev["next"]:
            st.markdown(f"- {n}")

# ---------------------------------------------------------------------------
# ④⑤ 재도전 — 전 → 후 비교는 coach.compare()
# ---------------------------------------------------------------------------
with tab_retry:
    ev = ss.evaluation
    if not ev or not ev["answers"]:
        st.info("📊 평가를 먼저 받아 주세요.")
    else:
        q_by_no = {q["no"]: q for q in ss.questions}
        order = coach.weakest_first(ev["answers"])
        picked = st.selectbox(
            "다시 답할 질문 (점수 낮은 순)",
            order,
            format_func=lambda a: f"Q{a['no']} · {a['total']}/20 — {q_by_no[a['no']]['question']}",
        )
        st.markdown(f"**지난 점수** {picked['total']}/20 · **약한 점** {picked['weak']}")
        if coach.needs_rewrite(picked):
            with st.expander("참고: 고친 답 (그대로 베끼지 말고 내 말로)"):
                st.write(picked["rewrite"])
        new_answer = st.text_area("다시 답하기", key=f"retry_{picked['no']}", height=160)
        if st.button("다시 채점", type="primary"):
            if not new_answer.strip():
                st.warning("다시 답할 내용을 적어 주세요.")
            else:
                q = q_by_no[picked["no"]]
                result = call(
                    prompts.RETRY.format(context=context()),
                    f"[질문] {q['question']}\n[보는 점] {q['point']}\n[지원자의 답] {new_answer.strip()}",
                    prompts.RETRY_SCHEMA,
                    "retry",
                    kind="eval",
                    waiting="다시 채점하는 중이에요…",
                )
                if result:
                    ss.retries.append({"no": picked["no"], "answer": new_answer.strip(), "weak": result["weak"],
                                       "compare": coach.compare(picked, result)})

        for r in reversed(ss.retries):
            c = r["compare"]
            st.divider()
            col1, col2 = st.columns([1, 2])
            col1.metric(f"Q{r['no']} 재도전 점수", f"{c['after_total']} / 20", delta=c["delta"])
            col2.dataframe(pd.DataFrame(c["rows"]), hide_index=True, use_container_width=True)
            st.caption(f"남은 약점: {r['weak']}")

# ---------------------------------------------------------------------------
# ★★★ 개발 직군 모드 — 코드 면접
# ---------------------------------------------------------------------------
if tab_code is not None:
    with tab_code:
        st.markdown(
            f"내가 직접 짠 코드 **{coach.CODE_MIN_LINES}~{coach.CODE_MAX_LINES}줄**을 붙이면, 면접관이 **그 코드로만** 꼬리 질문 {coach.CODE_QUESTION_COUNT}개를 해요. "
            "API 키 · 비밀번호가 들어간 줄은 지우고 붙여 주세요."
        )
        language = st.selectbox("언어", ["Python", "JavaScript", "TypeScript", "Java", "SQL", "기타"])
        code = st.text_area("내 코드", height=260, key="code_input")
        if st.button("코드 면접 시작", type="primary"):
            n = coach.code_line_count(code)
            if not code.strip():
                st.warning("코드를 붙여 주세요.")
            elif not coach.CODE_MIN_LINES <= n <= coach.CODE_MAX_LINES:
                st.warning(f"빈 줄을 뺀 코드가 {n}줄이에요. {coach.CODE_MIN_LINES}~{coach.CODE_MAX_LINES}줄로 맞춰 주세요.")
            elif "sk-" in code:
                st.warning("코드에 API 키로 보이는 값(sk-)이 있어요. 지우고 다시 붙여 주세요.")
            else:
                result = call(
                    prompts.CODE_QUESTIONS.format(persona=persona(), context=context(), language=language, job=ss.profile["track"]),
                    code,
                    prompts.CODE_QUESTIONS_SCHEMA,
                    "code_questions",
                    waiting="면접관이 코드를 읽는 중이에요…",
                )
                if result:
                    ss.code = {"code": code, "language": language, **coach.clean_code_questions(result)}
                    ss.code_review = None

        if ss.code:
            st.code(ss.code["code"], language=ss.code["language"].lower() if ss.code["language"] != "기타" else None, line_numbers=True)
            st.markdown(f"**면접관이 읽은 코드** — {ss.code['summary']}")
            answers = []
            for i, q in enumerate(ss.code["questions"], start=1):
                st.markdown(f"**꼬리 질문 {i}.** {q['q']}")
                st.caption(f"근거 줄: `{q['line']}` · 보는 점: {q['point']}")
                answers.append(st.text_area(f"답 {i}", key=f"code_answer_{i}", height=100))
            if st.button("코드 면접 채점"):
                if any(not a.strip() for a in answers):
                    st.warning("두 질문에 모두 답해 주세요.")
                else:
                    qa = "\n".join(f"[질문 {i}] {q['q']}\n[답 {i}] {a}" for i, (q, a) in enumerate(zip(ss.code["questions"], answers), start=1))
                    result = call(
                        prompts.CODE_REVIEW.format(job=ss.profile["track"], context=context()),
                        f"[코드 · {ss.code['language']}]\n{ss.code['code']}\n\n{qa}",
                        prompts.CODE_REVIEW_SCHEMA,
                        "code_review",
                        kind="eval",
                        waiting="코드 면접을 채점하는 중이에요…",
                    )
                    if result:
                        ss.code_review = coach.clean_code_review(result)

        cr = ss.code_review
        if cr:
            st.metric("코드 면접 점수", f"{cr['total']} / {cr['max']}")
            for a in cr["answers"]:
                st.markdown(f"- 답 {a['no']}: **{a['score']}/5** — {a['comment']}")
            if cr["risks"]:
                st.markdown("**🐞 버그 위험 · 읽기 어려운 곳**")
                for r in cr["risks"]:
                    st.markdown(f"- {r}")
            if cr["fact_check"]:
                st.markdown("**⑩ 팩트 체크 — 공식 문서에서 직접 확인하세요**")
                st.dataframe(
                    pd.DataFrame(cr["fact_check"]).rename(columns={"level": "등급", "name": "함수 · 옵션", "confidence": "신뢰도(%)", "where": "확인할 곳"})[
                        ["등급", "함수 · 옵션", "신뢰도(%)", "확인할 곳"]
                    ],
                    hide_index=True,
                    use_container_width=True,
                )

# ---------------------------------------------------------------------------
# ⑥ 마지막 질문 다듬기 · 리포트
# ---------------------------------------------------------------------------
with tab_report:
    st.subheader("❓ 면접관에게 할 마지막 질문 다듬기")
    my_question = st.text_input("내가 하려던 질문", placeholder="예: 개발 문화가 어떤가요?")
    if st.button("질문 다듬기"):
        if not my_question.strip():
            st.warning("다듬을 질문을 적어 주세요.")
        else:
            result = call(
                prompts.LAST_QUESTION.format(context=context(), job=ss.profile["track"]),
                my_question.strip(),
                prompts.LAST_QUESTION_SCHEMA,
                "last_question",
                waiting="질문을 다듬는 중이에요…",
            )
            if result:
                ss.last_questions = {"questions": result["questions"][:3], "why": result["why"]}
    if ss.last_questions:
        for label, q in zip(["🏢 회사", "🛠 직무", "🌱 성장"], ss.last_questions["questions"]):
            st.markdown(f"- **{label}** {q}")
        st.caption(f"빠졌던 것: {ss.last_questions['why']}")

    st.divider()
    st.subheader("📄 면접 리포트")
    report = coach.build_report(
        ss.profile,
        ss.questions,
        ss.transcript,
        ss.evaluation,
        ss.retries,
        ss.code_review,
        ss.last_questions["questions"] if ss.last_questions else None,
    )
    st.download_button("면접리포트.md 내려받기", report, file_name="면접리포트.md", mime="text/markdown")
    with st.expander("미리 보기"):
        st.markdown(report)
