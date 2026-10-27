"""AI 면접 코치 — Streamlit 화면만. 프롬프트는 prompts.py, API 호출은 llm.py, 계산은 coach.py."""

import altair as alt
import pandas as pd
import streamlit as st

import coach
import prompts
import store
import ui
from llm import LLMError, ask_json, is_demo, model_name

st.set_page_config(page_title="AI 면접 코치", page_icon="🎤", layout="wide")
ui.apply_style()

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
    "saved": False,            # 이번 면접 점수를 랭킹에 올렸는지
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value
ss = st.session_state


TAB_INTERVIEW, TAB_EVAL, TAB_RETRY, TAB_CODE, TAB_DASH, TAB_REPORT = (
    "🎤 면접", "📊 평가", "🔁 재도전", "💻 코드 면접", "🏆 대시보드", "📄 리포트")


def reset():
    for key, value in DEFAULTS.items():
        ss[key] = value.copy() if isinstance(value, (list, dict)) else value
    ss.pop("active_tab", None)


def go_to(tab, run_eval=False):
    # 버튼 콜백: 탭을 바꾸고, 필요하면 평가를 바로 시작하게 표시
    ss.active_tab = tab
    ss.run_eval = run_eval


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
    st.markdown("### 🎤 면접 코치")
    st.caption("📟 상태창")
    if ss.profile:
        st.caption(f"{ss.profile['name']} · {ss.profile['track']} · {ss.profile['company']}")
    done_count = coach.TOTAL_QUESTIONS if ss.stage == "done" else ss.idx
    st.progress(done_count / coach.TOTAL_QUESTIONS, text=f"질문 {min(done_count + (ss.stage == 'interview'), coach.TOTAL_QUESTIONS)}/{coach.TOTAL_QUESTIONS}")
    ui.stat_card("면접관이 본 직무 이해도", f"{ss.understanding} / 100", "답할 때마다 바뀌어요", tone="teal", icon="🧠")
    st.write("")
    if ss.stage == "interview":
        st.caption(f"이번 질문 꼬리 질문: {ss.follow_ups}/{coach.MAX_FOLLOW_UPS}")
    if st.button("🔄 처음부터 다시", width="stretch"):
        reset()
        st.rerun()
    st.divider()
    st.caption("🧪 데모 모드 (API 호출 없음)" if is_demo() else f"모델: {model_name()}")

ui.header("🎤 AI 면접 코치", "클래스로(수업용 가상 회사) 신입 모의면접 · 면접 5문제 → 위원 4명 평가 → 재도전 → 다른 사람과 비교")


def load_scores():
    try:
        return store.load()
    except store.StoreError as e:
        st.error(str(e))
        return []

# ---------------------------------------------------------------------------
# ① 시작
# ---------------------------------------------------------------------------
if ss.stage == "start":
    left, right = st.columns([3, 2], gap="large")
    left_card = left.container(key="card_start")
    left_card.subheader("면접 준비")
    form = left_card.form("start", border=False)
    with form:
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
    with right:
        with ui.card("rank_preview"):
            st.subheader("🏆 랭킹 미리 보기")
            rows = load_scores()
            if rows:
                st.dataframe(pd.DataFrame(coach.leaderboard(rows, top=5)), hide_index=True)
                st.caption(f"전체 {len(rows)}명 · 면접을 마치면 내 점수와 비교할 수 있어요")
            else:
                st.caption("아직 올라온 점수가 없어요. 첫 번째 주인공이 되어 보세요!")
        st.write("")
        with ui.card("personas"):
            st.subheader("면접관")
            for label, (key, _) in coach.TRACKS.items():
                with st.expander(label, expanded=label in coach.DEV_TRACKS):
                    st.write(prompts.PERSONAS[key])
    st.stop()

# ---------------------------------------------------------------------------
# 탭
# ---------------------------------------------------------------------------
tab_names = [TAB_INTERVIEW, TAB_EVAL, TAB_RETRY]
is_dev = ss.profile["track"] in coach.DEV_TRACKS
if is_dev:
    tab_names.append(TAB_CODE)
tab_names += [TAB_DASH, TAB_REPORT]
# key 로 지금 탭을 session_state 에 두면 버튼으로 탭을 옮길 수 있다
tabs = st.tabs(tab_names, key="active_tab", on_change="rerun")
tab_interview, tab_eval, tab_retry = tabs[:3]
tab_code = tabs[3] if is_dev else None
tab_dash, tab_report = tabs[-2], tabs[-1]

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
                        say("면접은 여기까지예요. 수고하셨습니다.")
                st.rerun()
    else:
        st.success("면접이 끝났어요. 이제 위원 4명에게 평가받아 보세요.")
        if ss.evaluation:
            st.button("📊 평가 결과 보러 가기", type="primary", on_click=go_to, args=(TAB_EVAL,))
        else:
            st.button("📊 위원 4명에게 평가받기", type="primary", on_click=go_to, args=(TAB_EVAL, True))

# ---------------------------------------------------------------------------
# ③ 평가 — 위원 4명 · 반론 먼저 · 점수 계산은 coach.py
# ---------------------------------------------------------------------------
with tab_eval:
    # 면접 탭의 '평가받기' 버튼으로 오면 바로 평가를 시작한다
    auto_eval = ss.pop("run_eval", False)
    label = "위원 4명에게 다시 평가받기" if ss.evaluation else "위원 4명에게 평가받기"
    if st.button(label, type="secondary" if ss.evaluation else "primary") or auto_eval:
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
                st.rerun()  # 버튼 문구('다시 평가받기' 등)를 바로 바꾸려고

    ev = ss.evaluation
    if ev:
        to_fix = [a for a in ev["answers"] if coach.needs_rewrite(a)]
        best = max(ev["answers"], key=lambda a: a["total"]) if ev["answers"] else None
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            ui.stat_card("위원 평균", f"{ev['panel_avg']} / 10", "위원 4명 점수의 평균", tone="blue", icon="👥")
        with c2:
            ui.stat_card("답변 합계", f"{ev['answers_total']} / {ev['answers_max']}", "기준 4개 × 질문 수", tone="teal", icon="📝")
        with c3:
            ui.stat_card("고칠 답", f"{len(to_fix)}개", f"{coach.PASS_SCORE}점 미만인 답", tone="pink", icon="🔧")
        with c4:
            ui.stat_card("가장 좋은 답", f"Q{best['no']} · {best['total']}/20" if best else "-", "이 답의 구조를 다른 답에도", tone="yellow", icon="⭐")
        st.write("")
        with ui.card("panel"):
            st.subheader("위원 4명 (반론 먼저)")
            st.dataframe(
                pd.DataFrame(ev["panel"]).rename(columns={"role": "위원", "score": "점수", "against": "뽑지 말아야 할 이유", "good": "좋은 점"})[
                    ["위원", "점수", "뽑지 말아야 할 이유", "좋은 점"]
                ],
                hide_index=True,
                            )
            st.markdown(f"**⚡ 판단이 갈린 곳** — {ev['conflict']}")
            st.markdown(f"**🤝 모두 같은 판단** — {ev['agree']}")
        st.write("")

        st.subheader("답변별 점수")
        q_by_no = {q["no"]: q for q in ss.questions}
        for a in ev["answers"]:
            flag = "🔧" if coach.needs_rewrite(a) else "✅"
            with st.expander(f"{flag} Q{a['no']} · {a['total']}/20 — {q_by_no[a['no']]['question']}"):
                st.dataframe(
                    pd.DataFrame([{coach.CRITERIA[k]: a[k] for k in coach.CRITERIA}]),
                    hide_index=True,
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
        weakest = coach.weakest_first(ev["answers"])[0] if ev["answers"] else None
        if weakest:
            b1, b2 = st.columns(2)
            b1.button(f"🔁 가장 약한 Q{weakest['no']}부터 다시 답하러 가기", type="primary", on_click=go_to, args=(TAB_RETRY,))
            b2.button("🏆 다른 사람과 비교하러 가기", on_click=go_to, args=(TAB_DASH,))

# ---------------------------------------------------------------------------
# ④⑤ 재도전 — 전 → 후 비교는 coach.compare()
# ---------------------------------------------------------------------------
with tab_retry:
    ev = ss.evaluation
    if not ev or not ev["answers"]:
        st.info("재도전은 평가를 받은 뒤에 할 수 있어요.")
        st.button("📊 평가 탭으로 가기", key="to_eval_from_retry", on_click=go_to, args=(TAB_EVAL,))
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
            col2.dataframe(pd.DataFrame(c["rows"]), hide_index=True)
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
                                    )

# ---------------------------------------------------------------------------
# 🏆 비교 대시보드 — 숫자는 coach.py, 저장은 store.py
# ---------------------------------------------------------------------------
def criteria_chart(mine, rows):
    data = pd.DataFrame(coach.criteria_compare(mine, rows)).melt("기준", var_name="대상", value_name="점수").dropna()
    order = ["나", "비교 대상 평균"]
    base = alt.Chart(data).encode(
        x=alt.X("기준:N", sort=list(coach.CRITERIA.values()), title=None, axis=alt.Axis(labelAngle=0)),
        xOffset=alt.XOffset("대상:N", sort=order),
        y=alt.Y("점수:Q", scale=alt.Scale(domain=[0, 5]), title="점수 (0~5)", axis=alt.Axis(tickCount=5, gridColor="#EEF2F6")),
        color=alt.Color("대상:N", sort=order, scale=alt.Scale(domain=order, range=[ui.ME, ui.OTHERS]),
                        legend=alt.Legend(orient="top", title=None)),
        tooltip=["기준", "대상", "점수"],
    )
    bars = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=22)
    labels = base.mark_text(dy=-8, fontSize=11, color=ui.DARK).encode(text=alt.Text("점수:Q", format=".1f"))
    return (bars + labels).properties(height=280, background="#FFFFFF").configure_view(stroke=None)


def distribution_chart(my_pct, rows):
    edges = list(range(0, 100, 10))
    counts = {b: 0 for b in edges}
    for r in rows:
        counts[min(int(r.get("answer_pct", 0)) // 10 * 10, 90)] += 1
    my_bin = min(my_pct // 10 * 10, 90) if my_pct is not None else None
    data = pd.DataFrame([{"구간": f"{b}~", "인원": counts[b], "내 구간": b == my_bin} for b in edges])
    base = alt.Chart(data).encode(
        x=alt.X("구간:N", sort=None, title="답변 점수 (%, 10점 구간)", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("인원:Q", title="인원", axis=alt.Axis(tickMinStep=1, gridColor="#EEF2F6")),
        tooltip=["구간", "인원"],
    )
    bars = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        color=alt.condition(alt.datum["내 구간"], alt.value(ui.ME), alt.value("#B8E2FB")))
    me = base.transform_filter(alt.datum["내 구간"]).mark_text(dy=-8, fontSize=11, fontWeight="bold", color=ui.DARK).encode(text=alt.value("나"))
    return (bars + me).properties(height=280, background="#FFFFFF").configure_view(stroke=None)


with tab_dash:
    track = ss.profile["track"]
    rows = load_scores()
    mine = coach.build_record(ss.profile, ss.evaluation, ss.retries) if ss.evaluation else None

    top = st.columns([3, 2])
    scope = top[0].segmented_control("비교 범위", [track, "전체 직군"], default=track, key="dash_scope") or track
    top[1].caption("🌐 모두와 같이 보는 랭킹 (Supabase)" if store.is_shared()
                   else "💻 이 PC에만 저장되는 연습용 랭킹 · 배포 앱에서 같이 보려면 Supabase 연결 필요")

    if mine and not ss.saved:
        with ui.card("save"):
            st.markdown(f"**🏆 내 점수를 랭킹에 올릴까요?** 별명 **{mine['nickname']}** · {track} · 점수만 저장돼요. 면접 답변 내용은 저장하지 않아요.")
            if st.button("랭킹에 내 점수 올리기", type="primary"):
                try:
                    ss.saved = store.save(mine)
                    st.rerun()
                except store.StoreError as e:
                    st.error(str(e))
        st.write("")
    elif not mine:
        st.info("평가를 받으면 내 점수를 다른 사람과 비교할 수 있어요. 지금은 다른 사람 점수만 보여요.")
        st.button("📊 평가받으러 가기", key="to_eval_from_dash", on_click=go_to, args=(TAB_EVAL,))

    # 비교 대상: 범위에 맞는 기록에서 방금 올린 내 기록은 뺀다
    pool = rows if scope == "전체 직군" else coach.track_rows(rows, track)
    saved_at = ss.saved["created_at"] if ss.saved else None
    others = [r for r in pool if not (saved_at and r.get("created_at") == saved_at and r.get("nickname") == mine["nickname"])]

    avg_pct = coach.mean([r.get("answer_pct") for r in others])
    rank = coach.top_percent(mine["answer_pct"], others) if mine else None
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.stat_card("내 답변 점수", f"{mine['answer_pct']}%" if mine else "-", "기준 4개 합계를 %로", tone="blue", icon="🙋")
    with c2:
        ui.stat_card("비교 대상 평균", f"{avg_pct}%" if avg_pct is not None else "-", scope, tone="teal", icon="👥")
    with c3:
        ui.stat_card("내 위치", f"상위 {rank}%" if rank else "-", "나보다 높은 사람 수 기준", tone="yellow", icon="🏅")
    with c4:
        ui.stat_card("비교 인원", f"{len(others)}명", "나를 뺀 기록 수", tone="pink", icon="📈")
    st.write("")

    if not others:
        st.info("아직 비교할 기록이 없어요. 짝꿍에게 면접을 보고 랭킹에 올려 달라고 해 보세요.")
    else:
        g1, g2 = st.columns(2, gap="medium")
        with g1, ui.card("chart_criteria"):
            st.subheader("기준별 점수 · 나 vs 평균")
            if mine:
                st.altair_chart(criteria_chart(mine, others))
                with st.expander("표로 보기"):
                    st.dataframe(pd.DataFrame(coach.criteria_compare(mine, others)), hide_index=True)
            else:
                st.caption("평가를 받으면 내 점수가 함께 보여요.")
                st.dataframe(pd.DataFrame([{"기준": label, "평균": coach.mean([r.get(k) for r in others])}
                                           for k, label in coach.CRITERIA.items()]), hide_index=True)
        with g2, ui.card("chart_dist"):
            st.subheader("답변 점수 분포")
            st.altair_chart(distribution_chart(mine["answer_pct"] if mine else None, others))
            st.caption("진한 막대가 내 점수가 속한 구간이에요.")
        st.write("")
        with ui.card("leaderboard"):
            st.subheader(f"🏆 랭킹 TOP 10 · {scope}")
            st.dataframe(pd.DataFrame(coach.leaderboard(pool)), hide_index=True)

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
