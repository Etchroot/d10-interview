"""화면 꾸미기만 (MaterialM 느낌). 색 · 반경 · 글꼴은 .streamlit/config.toml, 여기는 카드 · 탭 모양."""

import html

import streamlit as st

# 디자인 토큰 — config.toml 과 같은 값
PRIMARY = "#00A1FF"
DARK = "#1F2A3D"
MUTED = "#98A4AE"
ME = "#0086D6"          # 차트: 나
OTHERS = "#E8618C"      # 차트: 같은 직군 평균
TONES = {               # 통계 카드 배경 (연한 색) · 아이콘 칩
    "blue": ("#00A1FF1F", "#00A1FF"),
    "teal": ("#83EBE840", "#16CDC7"),
    "pink": ("#FF66922E", "#FF6692"),
    "yellow": ("#F8C20A2E", "#C99A00"),
}

CSS = f"""
<style>
.block-container {{ padding-top: 2rem; max-width: 1200px; }}
h1, h2, h3 {{ color: {DARK}; letter-spacing: -0.01em; }}

/* 흰 카드: st.container(key="card_...") */
[class*="st-key-card"] {{
  background: #FFFFFF;
  border-radius: 12px;
  padding: 24px 24px 20px;
  box-shadow: 0 2px 4px -1px rgba(175, 182, 201, 0.2), 0 1px 12px rgba(175, 182, 201, 0.12);
}}

/* 탭을 사이드 메뉴처럼 알약 모양으로 */
[role="tablist"] {{ gap: 6px; background: #FFFFFF; padding: 6px; border-radius: 999px; border: none;
  box-shadow: 0 2px 4px -1px rgba(175, 182, 201, 0.2); width: fit-content; max-width: 100%; overflow-x: auto; }}
[role="tablist"] [role="tab"] {{ border-radius: 999px; padding: 6px 16px; height: auto; border: none; }}
[role="tablist"] [role="tab"][aria-selected="true"] {{ background: #00A1FF20; color: {PRIMARY}; }}
[role="tablist"] [role="tab"]::after {{ display: none; }}

/* 채팅 말풍선을 카드처럼 */
[data-testid="stChatMessage"] {{ background: #FFFFFF; border-radius: 12px;
  box-shadow: 0 2px 4px -1px rgba(175, 182, 201, 0.2); padding: 12px 16px; }}

/* 통계 카드 */
.stat {{ border-radius: 24px; padding: 20px 22px; height: 100%; }}
.stat .chip {{ display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px;
  border-radius: 12px; color: #fff; font-size: 18px; margin-right: 10px; vertical-align: middle; }}
.stat .label {{ font-size: 14px; color: {DARK}; font-weight: 600; vertical-align: middle; }}
.stat .value {{ font-size: 28px; font-weight: 700; color: {DARK}; margin-top: 16px; line-height: 1.2; }}
.stat .sub {{ font-size: 12px; color: #5A6A7A; margin-top: 4px; }}

.page-sub {{ color: {MUTED}; margin-top: -8px; }}
.pill {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
</style>
"""


def apply_style():
    st.markdown(CSS, unsafe_allow_html=True)


def header(title, subtitle):
    st.title(title)
    st.markdown(f'<p class="page-sub">{html.escape(subtitle)}</p>', unsafe_allow_html=True)


def stat_card(label, value, sub="", tone="blue", icon="●"):
    bg, chip = TONES[tone]
    st.markdown(
        f'<div class="stat" style="background:{bg}">'
        f'<span class="chip" style="background:{chip}">{icon}</span>'
        f'<span class="label">{html.escape(label)}</span>'
        f'<div class="value">{html.escape(str(value))}</div>'
        f'<div class="sub">{html.escape(sub)}</div></div>',
        unsafe_allow_html=True,
    )


def card(key):
    """흰 카드 컨테이너. with ui.card("이름"): ..."""
    return st.container(key=f"card_{key}")
