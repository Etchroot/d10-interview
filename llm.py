"""OpenAI 호출은 이 파일 한 곳에서만. 화면 코드는 두지 않는다.

키 · 요청 내용은 화면과 터미널에 찍지 않는다. 에러는 한국어 한 줄(LLMError)로 올린다.
DEMO_MODE=1 이면 API를 부르지 않고 스키마 모양의 연습용 답을 돌려준다 (키 없이 화면 점검용).
"""

import json
import os
import random

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gpt-6-luna"


class LLMError(Exception):
    """화면에 그대로 보여 줄 한국어 한 줄 에러."""


def _setting(name, default=""):
    # 로컬은 .env, 배포(Streamlit Community Cloud)는 Secrets
    value = os.getenv(name)
    if value:
        return value
    try:
        import streamlit as st

        return st.secrets.get(name, default)
    except Exception:
        return default


def is_demo():
    return _setting("DEMO_MODE", "0") == "1"


def model_name(kind="main"):
    if kind == "eval":
        return _setting("OPENAI_EVAL_MODEL") or _setting("OPENAI_MODEL", DEFAULT_MODEL)
    return _setting("OPENAI_MODEL", DEFAULT_MODEL)


def ask_json(instructions, user_input, schema, name, kind="main"):
    """instructions + user_input 을 보내고 strict JSON 스키마로 받은 dict 를 돌려준다."""
    if is_demo():
        return _demo_answer(name, user_input)

    api_key = _setting("OPENAI_API_KEY")
    if not api_key:
        raise LLMError("OpenAI 키가 없어요. .env 에 OPENAI_API_KEY 를 넣고 앱을 다시 실행해 주세요.")

    import openai

    client = openai.OpenAI(api_key=api_key, timeout=120)
    try:
        response = client.responses.create(
            model=model_name(kind),
            instructions=instructions,
            input=user_input,
            text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
        )
    except openai.AuthenticationError:
        raise LLMError("OpenAI 키가 틀렸어요. .env 의 OPENAI_API_KEY 를 다시 확인해 주세요.") from None
    except openai.RateLimitError as e:
        if "insufficient_quota" in str(getattr(e, "code", "")) or "quota" in str(e).lower():
            raise LLMError("OpenAI 크레딧이 부족해요. 결제 · 사용 한도를 확인해 주세요.") from None
        raise LLMError("요청이 너무 많아요. 잠시 뒤 다시 시도해 주세요.") from None
    except openai.NotFoundError:
        raise LLMError(f"모델 '{model_name(kind)}' 을 찾을 수 없어요. .env 의 OPENAI_MODEL 을 확인해 주세요.") from None
    except (openai.APIConnectionError, openai.APITimeoutError):
        raise LLMError("OpenAI 서버에 연결하지 못했어요. 인터넷 연결을 확인하고 다시 시도해 주세요.") from None
    except openai.APIError:
        raise LLMError("OpenAI 요청이 실패했어요. 잠시 뒤 다시 시도해 주세요.") from None

    try:
        return json.loads(response.output_text)
    except (json.JSONDecodeError, TypeError):
        raise LLMError("AI 답을 읽지 못했어요. 한 번 더 시도해 주세요.") from None


# ---------------------------------------------------------------------------
# 데모 응답 — API 없이 화면 흐름만 점검할 때. 일부러 범위 밖 점수도 섞어서
# coach.py 의 '잘라 쓰기'가 동작하는지 볼 수 있게 한다.
# ---------------------------------------------------------------------------
def _demo_answer(name, user_input):
    rnd = random.Random(len(user_input))
    if name == "interviewer":
        short = len(user_input.strip().splitlines()[-1]) < 40 if user_input.strip() else True
        return {
            "reaction": "(데모) 말씀 잘 들었습니다.",
            "clarify": "뜻" in user_input.strip().splitlines()[-1] if user_input.strip() else False,
            "follow_up": short or rnd.random() < 0.5,
            "follow_up_question": "(데모) 방금 말한 부분, 어떻게 확인했는지 구체적으로 말해 줄래요?",
            "understanding": rnd.randint(30, 90),
        }
    if name == "evaluator":
        count = user_input.count("[질문 ")
        return {
            "panel": [
                {"role": r, "against": "(데모) 근거가 되는 숫자가 부족합니다.",
                 "good": "(데모) 문제를 끝까지 추적하려는 태도가 보입니다.", "score": rnd.randint(4, 12)}
                for r in ["실무자", "팀장", "HR", "대표"]
            ],
            "conflict": "(데모) 실무자는 기술 깊이를, HR은 성장 태도를 더 높게 봤습니다.",
            "agree": "(데모) 모두 '확인 방법'을 더 말해야 한다고 봤습니다.",
            "answers": [
                {"no": i + 1, "specific": rnd.randint(0, 6), "relevance": rnd.randint(1, 5),
                 "structure": rnd.randint(1, 5), "evidence": rnd.randint(0, 5),
                 "weak": "(데모) 결과를 어떻게 확인했는지가 빠졌습니다.",
                 "rewrite": "(데모) [상황] … [행동] … [결과] [확인 필요: 개선 수치] … [확인] 로그로 재현해 확인했습니다.",
                 "check": ["(데모) 개선 수치를 실제 기록에서 확인"]}
                for i in range(max(count, 1))
            ],
            "next": ["(데모) 답마다 숫자 하나 넣기", "(데모) 상황 → 행동 → 결과 순서 지키기", "(데모) 확인 방법으로 끝내기"],
        }
    if name == "retry":
        return {"specific": rnd.randint(2, 5), "relevance": rnd.randint(3, 5), "structure": rnd.randint(3, 5),
                "evidence": rnd.randint(2, 5), "weak": "(데모) 근거 숫자를 하나 더 넣으면 좋겠습니다."}
    if name == "code_questions":
        return {
            "summary": "(데모) 입력을 받아 외부 API를 호출하고 결과를 돌려주는 코드로 보입니다 [가정].",
            "questions": [
                {"line": "(데모) 코드의 한 줄", "q": "(데모) 이 호출이 실패하면 사용자에게 무엇이 보이나요?", "point": "예외 처리"},
                {"line": "(데모) 코드의 한 줄", "q": "(데모) 입력이 비어 있으면 어떻게 되나요?", "point": "입력 검증"},
                {"line": "(데모) 세 번째는 코드가 잘라야 함", "q": "(데모) 잘려야 하는 질문", "point": "-"},
            ],
        }
    if name == "code_review":
        return {
            "answers": [{"no": 1, "score": rnd.randint(1, 5), "comment": "(데모) 실패 경로를 설명했습니다."},
                        {"no": 2, "score": rnd.randint(1, 5), "comment": "(데모) 빈 입력 처리가 빠졌습니다."}],
            "risks": ["(데모) 타임아웃이 없어 요청이 오래 멈출 수 있습니다."],
            "fact_check": [{"name": "(데모) requests.get(timeout=...)", "level": "🟢", "confidence": 95, "where": "Requests 공식 문서"}],
        }
    if name == "last_question":
        return {"questions": ["(데모) 회사 관점 질문", "(데모) 직무 관점 질문", "(데모) 성장 관점 질문"],
                "why": "(데모) 원래 질문은 대상과 목적이 빠져 있었습니다."}
    raise LLMError("알 수 없는 요청이에요.")
