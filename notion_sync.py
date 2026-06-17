"""
SWING Portfolio 노션 동기화 모듈
- 페이지 생성 / 테이블 업데이트 / 이미지 블록 삽입
- 이미지는 GitHub raw 링크 사용 (커밋 해시로 캐시 무효화)
- 블록은 절대 삭제하지 않음 (내용만 업데이트하거나 신규 append)
"""

import time
from notion_client import Client

from config import (
    NOTION_TOKEN, GITHUB_REPO, GITHUB_BRANCH, TRADE_LOGS,
    STUDENT_LINE, COURSE_LINE, STUDENT_ID,
)
from analysis import fmt_won, fmt_pct

notion = Client(auth=NOTION_TOKEN)


def github_raw_url(chart_path, cache_bust=""):
    """charts/xxx.png → GitHub raw URL (+ 캐시버스터)"""
    # chart_path 예: "charts/pie_allocation.png"
    url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{chart_path}"
    if cache_bust:
        url += f"?v={cache_bust}"
    return url


# ───────────── 블록 헬퍼 ─────────────
def _cell(text):
    return [{"type": "text", "text": {"content": str(text)}}]


def _hcell(text):
    return [{"type": "text", "text": {"content": str(text)}, "annotations": {"bold": True}}]


def _heading(text, level=1):
    t = f"heading_{level}"
    return {"object": "block", "type": t,
            t: {"rich_text": [{"type": "text", "text": {"content": text}}]}}


def _divider():
    return {"object": "block", "type": "divider", "divider": {}}


def _callout(text, emoji="📊", color="gray_background"):
    return {"object": "block", "type": "callout", "callout": {
        "rich_text": [{"type": "text", "text": {"content": text}}],
        "icon": {"type": "emoji", "emoji": emoji}, "color": color}}


def _table(width, headers, rows):
    trows = [{"object": "block", "type": "table_row",
              "table_row": {"cells": [_hcell(h) for h in headers]}}]
    for r in rows:
        trows.append({"object": "block", "type": "table_row",
                      "table_row": {"cells": [_cell(c) for c in r]}})
    return {"object": "block", "type": "table",
            "table": {"table_width": width, "has_column_header": True,
                      "has_row_header": False, "children": trows}}


def _image(url):
    return {"object": "block", "type": "image",
            "image": {"type": "external", "external": {"url": url}}}


def get_all_blocks(page_id):
    blocks, cursor = [], None
    while True:
        params = {"block_id": page_id}
        if cursor:
            params["start_cursor"] = cursor
        r = notion.blocks.children.list(**params)
        blocks.extend(r["results"])
        if not r["has_more"]:
            break
        cursor = r["next_cursor"]
    return blocks


def find_table_after_heading(blocks, keyword, exclude=None):
    found = False
    for b in blocks:
        bt = b["type"]
        if bt.startswith("heading"):
            text = "".join(t["plain_text"] for t in b[bt].get("rich_text", []))
            found = keyword in text and (exclude is None or exclude not in text)
        elif bt == "table" and found:
            return b["id"]
    return None


def find_image_after_heading(blocks, keyword):
    found = False
    for b in blocks:
        bt = b["type"]
        if bt.startswith("heading"):
            text = "".join(t["plain_text"] for t in b[bt].get("rich_text", []))
            found = keyword in text
        elif bt == "image" and found:
            return b["id"]
    return None


def update_table_rows(table_id, rows):
    """헤더 제외 데이터 행만 업데이트 (삭제 없음, 부족하면 append)"""
    existing = notion.blocks.children.list(block_id=table_id)["results"]
    data_rows = existing[1:]
    for i, row in enumerate(rows):
        cells = {"cells": [_cell(c) for c in row]}
        if i < len(data_rows):
            notion.blocks.update(block_id=data_rows[i]["id"], table_row=cells)
        else:
            notion.blocks.children.append(
                block_id=table_id,
                children=[{"object": "block", "type": "table_row", "table_row": cells}])


def update_image(image_id, url):
    """이미지 블록 업데이트 — update 시 type 필드 제외"""
    notion.blocks.update(block_id=image_id, image={"external": {"url": url}})


def has_section(blocks, keyword):
    for b in blocks:
        bt = b["type"]
        if bt.startswith("heading"):
            text = "".join(t["plain_text"] for t in b[bt].get("rich_text", []))
            if keyword in text:
                return True
    return False


def append_blocks(page_id, children):
    """페이지 하단에 블록 추가 (100개 단위 분할)"""
    for i in range(0, len(children), 100):
        notion.blocks.children.append(
            block_id=page_id, children=children[i:i + 100])


def create_child_page(parent_id, title, icon="📄", children=None):
    """하위 페이지 생성"""
    props = {
        "parent": {"page_id": parent_id},
        "icon": {"type": "emoji", "emoji": icon},
        "properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}},
    }
    if children:
        props["children"] = children[:100]
    page = notion.pages.create(**props)
    return page["id"]


def block_plain_text(block):
    bt = block["type"]
    if bt not in block:
        return ""
    return "".join(t["plain_text"] for t in block[bt].get("rich_text", []))


def project_header_text():
    return f"🎓 {STUDENT_LINE}\n{COURSE_LINE}"


def has_project_header(blocks):
    return any(STUDENT_ID in block_plain_text(b) for b in blocks)


def ensure_project_header(page_id, blocks):
    """과제 헤더가 없으면 상단 callout에 추가 (기존 페이지 호환)"""
    if has_project_header(blocks):
        return False
    header = project_header_text()
    for b in blocks:
        if b["type"] == "callout":
            txt = block_plain_text(b)
            if "기준일" in txt or "작성일자" in txt:
                notion.blocks.update(block_id=b["id"], callout={
                    "rich_text": [{"type": "text", "text": {"content": f"{header}\n\n{txt}"}}],
                    "icon": {"type": "emoji", "emoji": "🎓"}, "color": "purple_background"})
                return True
    append_blocks(page_id, [
        _callout(project_header_text(), "🎓", "purple_background"),
        _divider(),
    ])
    return True


def update_callout_date(blocks, today):
    """기준일 callout 업데이트 (과제 헤더가 통합된 callout도 유지)"""
    date_line = f"📅 기준일: {today}   |   🔄 GitHub Actions가 매일 자동 업데이트합니다."
    for b in blocks:
        if b["type"] == "callout":
            txt = block_plain_text(b)
            if "기준일" in txt or "작성일자" in txt:
                if STUDENT_ID in txt:
                    content = f"{project_header_text()}\n\n{date_line}"
                    icon, color = "🎓", "purple_background"
                else:
                    content = date_line
                    icon, color = "📊", "blue_background"
                notion.blocks.update(block_id=b["id"], callout={
                    "rich_text": [{"type": "text", "text": {"content": content}}],
                    "icon": {"type": "emoji", "emoji": icon}, "color": color})
                return True
    return False
