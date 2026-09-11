"""쇼핑 리스트 앱 — 아이템 추가 / 수정 / 삭제 / 체크.

PRD.md 기준 구현. FR-1 ~ FR-6.

목록은 같은 디렉터리의 JSON 파일에 저장한다. 상태를 바꾸는 함수는 모두
_save_items() 로 끝나므로, 새 함수를 추가하면 저장 호출도 함께 넣어야 한다.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")

# 마크다운 특수문자가 이름 표시를 깨뜨리지 않도록 이스케이프할 대상
_MD_SPECIALS = "\\`*_{}[]()#+-.!~<>|"


# 색은 3개만 쓴다. 회색 계열은 알파로 지정해 라이트/다크 어느 쪽에서도 대비가 유지되게 한다.
_ACCENT = "#34A06A"                       # 진행률 · 완료 표시
_HAIRLINE = "rgba(128, 128, 128, 0.22)"   # 행 구분선 · 테두리
_SOFT_BG = "rgba(128, 128, 128, 0.07)"    # 입력 카드 배경

# 목록 저장 파일. app.py 와 같은 디렉터리에 둔다.
_DATA_FILE = Path(__file__).with_name("shopping_list.json")


def _load_items() -> list[dict]:
    """저장 파일에서 아이템을 읽는다.

    파일이 없거나 내용이 깨졌으면 빈 목록으로 시작한다. 손으로 고칠 수 있는 파일이므로
    항목 하나하나의 형식을 확인하고, 어긋나는 항목은 조용히 버린다.
    """
    try:
        raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []

    if not isinstance(raw, dict):
        return []

    items: list[dict] = []
    seen_ids: set[int] = set()
    seen_names: set[str] = set()
    for entry in raw.get("items", []):
        if not isinstance(entry, dict):
            continue
        item_id, name = entry.get("id"), entry.get("name")
        # bool 은 int 의 하위 타입이라 따로 걸러야 한다.
        if not isinstance(item_id, int) or isinstance(item_id, bool) or item_id in seen_ids:
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        # 추가할 때와 같은 기준으로 중복 이름을 막는다. 먼저 나온 항목을 남긴다.
        if _normalize(name) in seen_names:
            continue
        seen_ids.add(item_id)
        seen_names.add(_normalize(name))
        items.append({"id": item_id, "name": name.strip(), "done": bool(entry.get("done"))})
    return items


def _save_items() -> None:
    """현재 목록을 저장 파일에 기록한다.

    임시 파일에 먼저 쓰고 교체하므로, 쓰는 도중 중단돼도 기존 파일이 깨지지 않는다.
    실패하면 화면에 알리기 위해 플래그만 남긴다.
    """
    payload = json.dumps(
        {"items": st.session_state.shopping_items}, ensure_ascii=False, indent=2
    )
    # 같은 목록을 여러 프로세스에서 열어도 임시 파일이 겹치지 않게 한다.
    tmp = _DATA_FILE.with_name(f"{_DATA_FILE.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(_DATA_FILE)
        st.session_state.save_failed = False
    except OSError:
        st.session_state.save_failed = True
        # 교체 전에 실패하면 임시 파일이 남는다. 쌓이지 않게 치운다.
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def init_state() -> None:
    """세션 상태를 최초 1회만 초기화한다. 이미 존재하는 키는 덮어쓰지 않는다."""
    if "shopping_items" not in st.session_state:
        # [{"id": int, "name": str, "done": bool}]
        st.session_state.shopping_items = _load_items()
    if "next_id" not in st.session_state:
        # 저장 파일에 있던 id 와 겹치지 않도록 가장 큰 id 다음부터 시작한다.
        st.session_state.next_id = (
            max((item["id"] for item in st.session_state.shopping_items), default=0) + 1
        )
    if "editing_id" not in st.session_state:
        st.session_state.editing_id = None


def _normalize(name: str) -> str:
    """중복 비교용 정규화. 대소문자와 앞뒤 공백을 무시한다."""
    return name.strip().casefold()


def _escape_md(text: str) -> str:
    """이름을 마크다운 리터럴로 표시하기 위해 특수문자를 이스케이프한다."""
    return "".join("\\" + ch if ch in _MD_SPECIALS else ch for ch in text)


def _find(item_id: int) -> dict | None:
    """id로 아이템을 찾는다. 없으면 None."""
    for item in st.session_state.shopping_items:
        if item["id"] == item_id:
            return item
    return None


def add_item(name: str) -> bool:
    """목록 맨 아래에 아이템을 추가한다.

    Args:
        name: 추가할 아이템 이름. 앞뒤 공백은 제거한다.

    Returns:
        추가에 성공하면 True. 빈 문자열이거나 기존 항목과 중복(대소문자·공백 무시)
        이면 추가하지 않고 False.
    """
    clean = name.strip()
    if not clean:
        return False
    clean_key = _normalize(clean)
    if any(_normalize(item["name"]) == clean_key for item in st.session_state.shopping_items):
        return False

    st.session_state.shopping_items.append(
        {"id": st.session_state.next_id, "name": clean, "done": False}
    )
    st.session_state.next_id += 1
    _save_items()
    return True


def update_item(item_id: int, name: str) -> bool:
    """아이템 이름을 수정한다. done 상태와 목록 순서는 유지된다.

    Args:
        item_id: 수정할 아이템의 id.
        name: 새 이름. 앞뒤 공백은 제거한다.

    Returns:
        수정에 성공하면 True. 이름이 비었거나 id가 없으면 False.
    """
    clean = name.strip()
    if not clean:
        return False

    target = _find(item_id)
    if target is None:
        return False

    # 자기 자신을 제외한 나머지와 중복되면 거부한다.
    for item in st.session_state.shopping_items:
        if item["id"] != item_id and _normalize(item["name"]) == _normalize(clean):
            return False

    target["name"] = clean
    _save_items()
    return True


def delete_item(item_id: int) -> None:
    """아이템을 목록에서 제거한다. 편집 중이던 항목이면 editing_id도 해제한다."""
    st.session_state.shopping_items = [
        item for item in st.session_state.shopping_items if item["id"] != item_id
    ]
    if st.session_state.editing_id == item_id:
        st.session_state.editing_id = None
    _save_items()


def toggle_item(item_id: int) -> None:
    """아이템의 done 상태를 반전시킨다. 목록 순서는 변하지 않는다."""
    target = _find(item_id)
    if target is not None:
        target["done"] = not target["done"]
        _save_items()


def clear_done() -> None:
    """done=True인 아이템을 모두 제거한다."""
    removed = {item["id"] for item in st.session_state.shopping_items if item["done"]}
    st.session_state.shopping_items = [
        item for item in st.session_state.shopping_items if not item["done"]
    ]
    if st.session_state.editing_id in removed:
        st.session_state.editing_id = None
    _save_items()


def get_summary() -> tuple[int, int, int]:
    """목록 요약을 반환한다.

    Returns:
        (전체 개수, 완료 개수, 남은 개수)
    """
    total = len(st.session_state.shopping_items)
    done = sum(1 for item in st.session_state.shopping_items if item["done"])
    return total, done, total - done


def _shorten(name: str, limit: int = 16) -> str:
    """알림 문구에 들어갈 이름을 짧게 줄인다."""
    return name if len(name) <= limit else name[:limit] + "…"


def _label(name: str, limit: int = 16) -> str:
    """알림 문구용 이름. 줄인 뒤 마크다운으로 해석되지 않게 이스케이프한다."""
    return _escape_md(_shorten(name, limit))


def _start_edit(item_id: int) -> None:
    """해당 행을 편집 모드로 전환한다. 동시에 한 행만 편집할 수 있다."""
    st.session_state.editing_id = item_id


def _on_delete(item_id: int) -> None:
    """FR-4의 삭제 콜백. 제거는 delete_item에 맡기고 알림 문구만 남긴다."""
    item = _find(item_id)
    name = item["name"] if item else ""
    delete_item(item_id)
    st.session_state.flash = ("🗑️", f"'{_label(name)}' 삭제")


def _on_clear_done() -> None:
    """FR-5의 완료 일괄 삭제 콜백."""
    _, done, _ = get_summary()
    clear_done()
    st.session_state.flash = ("🧺", f"완료한 {done}개 치움")


def _inject_css() -> None:
    """인라인 스타일 한 벌. 외부 CSS·폰트·스크립트는 쓰지 않는다."""
    st.markdown(
        f"""
        <style>
        .block-container {{ padding-top: 2.6rem; padding-bottom: 3rem; max-width: 44rem; }}

        /* 헤더: 크기와 자간으로만 위계를 만든다 */
        .list-head h1 {{
            font-size: 1.9rem; font-weight: 700; letter-spacing: -0.02em;
            margin: 0 0 0.15rem 0;
        }}
        .list-head p {{ margin: 0 0 1rem 0; font-size: 0.9rem; opacity: 0.65; }}

        /* 입력 영역만 카드로 띄우고 목록은 평평하게 둔다 */
        div[data-testid="stForm"] {{
            background: {_SOFT_BG};
            border: 1px solid {_HAIRLINE};
            border-radius: 10px;
            padding: 0.85rem 0.9rem 0.35rem 0.9rem;
        }}

        /* 목록 행: 카드 대신 얇은 구분선으로 밀도를 낮춘다 */
        div[data-testid="stHorizontalBlock"] {{
            align-items: center;
            border-bottom: 1px solid {_HAIRLINE};
            padding: 0.1rem 0;
        }}
        div[data-testid="stForm"] div[data-testid="stHorizontalBlock"],
        div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {{
            border-bottom: none;
            padding: 0;
        }}

        /* 행 안의 버튼은 행 높이를 키우지 않도록 납작하게 */
        div[data-testid="stHorizontalBlock"] .stButton button {{
            padding: 0.15rem 0.2rem;
            border: 1px solid transparent;
            background: transparent;
        }}
        div[data-testid="stHorizontalBlock"] .stButton button:hover {{
            border-color: {_HAIRLINE};
            background: {_SOFT_BG};
        }}

        /* 지표는 숫자만 남기고 장식을 걷어낸다 */
        div[data-testid="stMetricValue"] {{ font-size: 1.6rem; letter-spacing: -0.02em; }}
        div[data-testid="stMetricLabel"] p {{ font-size: 0.8rem; opacity: 0.65; }}
        div[data-testid="stProgressBarTrack"] > div {{ background-color: {_ACCENT}; }}

        /* 강조색은 완료 체크와 주요 버튼, 두 군데에만 쓴다 */
        /* 체크 표시의 실제 네모는 Streamlit 버전에 따라 span 이기도 하고 div 이기도 하다.
           레이블 텍스트를 담은 자식은 제외하고 둘 다 칠한다.
           transition: all 이 기본이라 그대로 두면 체크할 때 기본 빨강에서 번진다. */
        div[data-testid="stCheckbox"] label > span,
        div[data-testid="stCheckbox"] label > div:not(:has([data-testid="stWidgetLabel"])) {{
            transition: none;
        }}
        div[data-testid="stCheckbox"] label:has(input:checked) > span,
        div[data-testid="stCheckbox"] label:has(input:checked) > div:not(:has([data-testid="stWidgetLabel"])) {{
            background-color: {_ACCENT};
            border-color: {_ACCENT};
        }}
        button[data-testid="stBaseButton-primaryFormSubmit"] {{
            background-color: {_ACCENT};
            border-color: {_ACCENT};
            color: #FFFFFF;
            /* 기본 빨강에서 강조색으로 넘어가는 중간 프레임이 보이지 않게 색 전환은 끈다 */
            transition: filter 120ms ease;
        }}
        /* Streamlit 기본 hover 규칙이 우선순위가 높아, 상태별로 모두 덮어야 한다 */
        button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
        button[data-testid="stBaseButton-primaryFormSubmit"]:focus,
        button[data-testid="stBaseButton-primaryFormSubmit"]:focus-visible,
        button[data-testid="stBaseButton-primaryFormSubmit"]:active {{
            background-color: {_ACCENT};
            border-color: {_ACCENT};
            color: #FFFFFF;
            filter: brightness(0.93);
        }}
        button[data-testid="stBaseButton-secondaryFormSubmit"]:hover,
        button[data-testid="stBaseButton-secondary"]:hover {{
            border-color: {_ACCENT};
            color: {_ACCENT};
        }}

        /* 목록 밖(=컬럼에 들어가지 않은) 버튼은 목록과 간격을 둔다 */
        div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"] > div[data-testid="stButton"] {{
            margin-top: 0.9rem;
        }}

        /* 빈 화면은 상태 설명이 아니라 다음 행동을 가리키게 */
        .empty-state {{
            text-align: center; padding: 2.8rem 1rem 3.2rem 1rem;
            border: 1px dashed {_HAIRLINE}; border-radius: 12px;
        }}
        .empty-state .mark {{ font-size: 2.4rem; line-height: 1; }}
        .empty-state .head {{ margin-top: 0.7rem; font-weight: 600; }}
        .empty-state .sub {{ margin-top: 0.2rem; font-size: 0.88rem; opacity: 0.6; }}

        /* 좁은 화면에서 Streamlit은 컬럼을 세로로 쌓는다.
           한 손으로 쓰는 화면이므로 한 항목은 한 줄로 유지한다. */
        @media (max-width: 640px) {{
            div[data-testid="stHorizontalBlock"] {{ flex-wrap: nowrap; }}
            div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{ min-width: 0; }}
            div[data-testid="stMetricValue"] {{ font-size: 1.25rem; }}
            .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_flash() -> None:
    """직전 조작의 결과를 토스트로 한 번만 보여준다.

    저장에 실패했다면 성공 토스트를 띄우지 않는다. main() 끝의 경고가 대신 알린다.
    """
    flash = st.session_state.flash if "flash" in st.session_state else None
    if not flash:
        return
    st.session_state.flash = None
    if st.session_state.get("save_failed"):
        return
    icon, message = flash
    st.toast(message, icon=icon)


def _render_save_warning() -> None:
    """저장 실패를 알린다.

    화면을 다 그린 뒤에 호출해야 한다. 추가·수정은 화면을 그리는 도중에 저장하므로,
    앞에서 검사하면 방금 실패한 저장을 놓치고 다음 조작에서야 경고가 뜬다.
    """
    if not st.session_state.get("save_failed"):
        return
    st.warning(
        f"목록을 {_DATA_FILE.name} 에 저장하지 못했습니다. "
        "이 창을 닫으면 변경 내용이 사라집니다."
    )


def _render_add_form() -> None:
    """FR-1. 입력창과 추가 버튼. Enter 로도 제출된다."""
    with st.form("add_form", clear_on_submit=True):
        col_input, col_button = st.columns([0.78, 0.22])
        name = col_input.text_input(
            "아이템 이름",
            placeholder="살 물건을 입력하세요…",
            label_visibility="collapsed",
        )
        submitted = col_button.form_submit_button("추가", type="primary", use_container_width=True)

    if not submitted:
        return

    if not name.strip():
        st.warning("아이템 이름을 입력해주세요.")
    elif not add_item(name):
        st.warning(f"'{_label(name.strip(), 40)}'은(는) 이미 목록에 있습니다.")
    elif not st.session_state.get("save_failed"):
        # 저장에 실패했다면 성공 토스트 대신 main() 끝의 경고로 알린다.
        st.toast(f"'{_label(name.strip())}' 추가", icon="🛒")


def _render_summary(total: int, done: int, remaining: int) -> None:
    """FR-5. 전체 / 완료 / 남음 지표와 진행률."""
    col_total, col_done, col_remaining = st.columns(3)
    col_total.metric("전체", f"{total}개")
    col_done.metric("완료", f"{done}개")
    col_remaining.metric("남음", f"{remaining}개")
    st.progress(done / total if total else 0.0)


def _render_edit_row(item: dict) -> None:
    """FR-3. 편집 모드 행: 입력창 + 저장 / 취소."""
    with st.form(f"edit_form_{item['id']}"):
        # 일반 행과 컬럼 비율을 맞춰 좌우 정렬이 어긋나지 않게 한다.
        # 체크박스는 폼 제출 전까지 값이 반영되지 않으므로 편집 중에는 비활성화한다.
        col_check, col_name, col_save, col_cancel = st.columns([0.06, 0.64, 0.15, 0.15])
        col_check.checkbox(
            f"{_escape_md(item['name'])} 완료",
            value=item["done"],
            key=f"chk_edit_{item['id']}",
            label_visibility="collapsed",
            disabled=True,
        )
        new_name = col_name.text_input(
            "아이템 이름 수정",
            value=item["name"],
            label_visibility="collapsed",
        )
        saved = col_save.form_submit_button("저장", type="primary", use_container_width=True)
        cancelled = col_cancel.form_submit_button("취소", use_container_width=True)

    if cancelled:
        st.session_state.editing_id = None
        st.rerun()

    if saved:
        if not new_name.strip():
            st.warning("이름을 비울 수 없습니다.")
        elif not update_item(item["id"], new_name):
            st.warning(f"'{_label(new_name.strip(), 40)}'은(는) 이미 목록에 있습니다.")
        else:
            st.session_state.editing_id = None
            st.session_state.flash = ("✏️", f"'{_label(new_name.strip())}' 저장")
            st.rerun()


def _render_item_row(item: dict) -> None:
    """FR-2 / FR-4. 일반 행: 체크박스 | 이름 | 수정 | 삭제."""
    item_id = item["id"]
    label = _escape_md(item["name"])
    col_check, col_name, col_edit, col_delete = st.columns([0.06, 0.64, 0.15, 0.15])

    # 레이블은 화면에서는 숨겨져 있지만 화면 낭독기가 읽는다.
    # 이름을 그대로 넣으면 마크다운으로 해석돼 잘못 읽히므로 이스케이프한다.
    col_check.checkbox(
        f"{label} 완료",
        value=item["done"],
        key=f"chk_{item_id}",
        label_visibility="collapsed",
        on_change=toggle_item,
        args=(item_id,),
    )

    col_name.markdown(f":gray[~~{label}~~]" if item["done"] else label)

    col_edit.button(
        "✏️",
        key=f"edit_{item_id}",
        help="이름 수정",
        use_container_width=True,
        on_click=_start_edit,
        args=(item_id,),
    )
    col_delete.button(
        "🗑️",
        key=f"del_{item_id}",
        help="목록에서 삭제",
        use_container_width=True,
        on_click=_on_delete,
        args=(item_id,),
    )


def _render_empty_state() -> None:
    """FR-5. 빈 목록 안내. 고정 문구만 들어가므로 사용자 입력이 섞이지 않는다."""
    st.markdown(
        """
        <div class="empty-state">
          <div class="mark">🧺</div>
          <div class="head">아직 담은 물건이 없습니다</div>
          <div class="sub">위 입력창에 살 물건을 적으면 여기에 쌓입니다.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    """앱 진입점. 상태를 초기화하고 화면을 그린다."""
    init_state()
    _inject_css()
    _render_flash()

    st.markdown(
        '<div class="list-head"><h1>🛒 쇼핑 리스트</h1>'
        "<p>장 보면서 하나씩 지워 나가세요.</p></div>",
        unsafe_allow_html=True,
    )

    # --- 입력 영역 (FR-1) ---
    _render_add_form()

    # --- 요약 영역 (FR-5) ---
    total, done, remaining = get_summary()
    _render_summary(total, done, remaining)

    # --- 목록 영역 (FR-2 ~ FR-5) ---
    if total == 0:
        _render_empty_state()
    else:
        for item in list(st.session_state.shopping_items):
            if st.session_state.editing_id == item["id"]:
                _render_edit_row(item)
            else:
                _render_item_row(item)

        if done > 0:
            st.button("완료한 항목 치우기", on_click=_on_clear_done)

    # --- 저장 실패 경고 (FR-6). 이번 실행의 저장까지 반영하려면 맨 마지막이어야 한다 ---
    _render_save_warning()


if __name__ == "__main__":
    main()
