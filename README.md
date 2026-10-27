# 🎤 AI 면접 코치 (D10)

클래스로(수업용 가상 회사) 신입 모의면접 서비스. Streamlit + OpenAI.
**개발 직군을 백엔드 / 프론트엔드로 나눠** 면접관 · 직무 질문이 따로 나와요. (디자인 · PO · 마케팅은 짝꿍 면접용)

## 흐름
시작(이름 · 직군 · 회사 · 경험 30자↑) → 면접 5문제(질문당 꼬리 질문 최대 1개, 코드가 막음)
→ 📊 위원 4명 평가(반론 먼저) → 🔁 재도전 전 → 후 비교 → 💻 코드 면접(개발 직군) → 🏆 대시보드(다른 사람과 비교) → 📄 리포트

## 실행
1. `.env.example` 을 복사해 `.env` 를 **직접** 만들고 `OPENAI_API_KEY` 를 채운다
2. 설치 · 실행
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
- 키 없이 화면만 보고 싶으면 `.env` 에 `DEMO_MODE=1` (AI 답 대신 연습용 답, 일부러 범위 밖 점수를 섞어 잘라 쓰기도 점검)

## 파일
| 파일 | 하는 일 |
| --- | --- |
| `prompts.py` | 프롬프트 · JSON 스키마만 (페르소나, CONTEXT, INTERVIEWER, EVALUATOR, RETRY, CODE_QUESTIONS, CODE_REVIEW, LAST_QUESTION) |
| `llm.py` | OpenAI 호출 한 곳 `ask_json()` · 한국어 한 줄 에러 · 데모 모드 |
| `coach.py` | 질문 고르기 · 꼬리 질문 제한 · 점수 자르기/합계/평균 · 전후 비교 · 리포트 |
| `app.py` | Streamlit 화면만 |
| `ui.py` | 화면 꾸미기 (MaterialM 느낌 카드 · 통계 카드 · 알약 탭). 색 · 글꼴은 `.streamlit/config.toml` |
| `store.py` | 랭킹 점수 저장 · 불러오기 (Supabase, 없으면 `data/results.jsonl`) |
| `data/questions.csv` | 질문 은행 52개 (공통 4 + 개발 공통 8 + 백엔드 8 + 프론트엔드 8 + 디자인 · PO · 마케팅 각 8) |

## 화면별 기법
| 화면 | 기법 |
| --- | --- |
| 시작 | ⑭ 컨텍스트 블록 |
| 면접 | ⑧ 게임 플레이 · ③ 페르소나 · ⑤ 숫자 규칙 · ⑨ 되물으면 쉬운 말로 |
| 평가 | ⑮ 다중 관점(위원 4명) · ⑯ 반론 먼저 · ⑫ 리플렉션 · ⑩ [확인 필요] |
| 재도전 | BAB · 전후 차이는 코드 |
| 코드 면접 (★★★) | ③ 페르소나 · ⑯ 단계별 + [가정] · ⑩ 🔴🟡🟢 팩트 체크 |
| 마지막 질문 · 리포트 (★★★) | ⑨ 질문 개선 · 숫자는 코드가 계산 |

## 🏆 다른 사람과 비교하는 대시보드 (Supabase 연결)
Streamlit 앱이 이미 서버라서 따로 서버를 만들 필요는 없고, **점수를 모아 둘 DB만** 있으면 돼요.
Streamlit Community Cloud 의 파일은 재시작 · 재배포 때 지워지기 때문에, 배포 앱에서는 무료 DB(Supabase)에 저장해요.
키가 없으면 내 PC의 `data/results.jsonl` 에 저장돼서 나 혼자 연습용으로만 보여요.

저장하는 것: 별명 · 직군 · 위원 평균 · 답변 점수(%) · 기준별 평균 · 재도전 최고 상승폭. **면접 답변 내용은 저장하지 않아요.**

1. [supabase.com](https://supabase.com) 가입 → New project
2. SQL Editor 에서 아래를 실행
   ```sql
   create table interview_results (
     id bigint generated always as identity primary key,
     created_at timestamptz not null default now(),
     nickname text not null check (char_length(nickname) <= 12),
     track text not null,
     panel_avg numeric,
     answer_pct int check (answer_pct between 0 and 100),
     specific numeric, relevance numeric, structure numeric, evidence numeric,
     retry_best int
   );
   alter table interview_results enable row level security;
   create policy "anyone can read" on interview_results for select using (true);
   create policy "anyone can add" on interview_results for insert with check (true);
   ```
3. Project Settings → API 에서 **Project URL** 과 **anon(public) 키**를 복사
4. Streamlit 앱 설정 → Secrets 에 추가 (로컬은 `.env` 에 같은 이름으로)
   ```toml
   SUPABASE_URL = "https://xxxx.supabase.co"
   SUPABASE_KEY = "anon 키"
   ```
- 키는 서버(Streamlit)에서만 쓰여 브라우저에 보이지 않아요. 그래도 수정 · 삭제 정책은 만들지 않아서 누구도 남의 점수를 고칠 수 없어요.
