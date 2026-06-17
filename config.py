"""
SWING Portfolio 설정 파일
- 매매일지(TRADE_LOGS)와 관심종목(WATCH_LIST)을 여기서 관리합니다.
- 새 매매를 등록하려면 TRADE_LOGS에 한 줄 추가 후 git push 하면 자동 반영됩니다.
- 토큰/페이지ID는 코드에 직접 넣지 않고 GitHub Secrets(환경변수)로 주입됩니다.
"""

import os

# ── 노션 설정 (GitHub Secrets에서 주입) ──
NOTION_TOKEN   = os.environ.get("NOTION_TOKEN", "")
PARENT_PAGE_ID = os.environ.get("PARENT_PAGE_ID", "")
SWING_PAGE_ID  = os.environ.get("SWING_PAGE_ID", "")

# ── 하위 페이지 ID (최초 실행 후 GitHub Secrets에 등록) ──
TRADE_JOURNAL_PAGE_ID = os.environ.get("TRADE_JOURNAL_PAGE_ID", "")
WATCHLIST_PAGE_ID     = os.environ.get("WATCHLIST_PAGE_ID", "")
PERFORMANCE_PAGE_ID   = os.environ.get("PERFORMANCE_PAGE_ID", "")

# ── GitHub 저장소 정보 (이미지 raw 링크 생성용) ──
# 예: "username/swing-portfolio"
GITHUB_REPO   = os.environ.get("GITHUB_REPOSITORY", "USERNAME/swing-portfolio")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

# ── 매매일지 ──
# (날짜, 종목명, 티커, 매수/매도, 수량, 단가, 분류, 사유)
TRADE_LOGS = [
    ("20250519", "삼성전자우",        "005935", "매수", 1, 177900, "국내종목",     "국내 대장주&주도주의 대표종목으로 매수결정"),
    ("20260519", "TIGER 200",         "102110", "매수", 1, 113190, "국내ETF",      "국내 대표지수로 매수결정"),
    ("20260519", "TIGER 미국S&P500",  "360750", "매수", 3,  27563, "국내ETF-해외", "미국 대표지수로 매수결정"),
    ("20260519", "ACE 미국나스닥100", "367380", "매수", 3,  33060, "국내ETF-해외", "기술/성장 대표지수로 매수결정"),
]

# ── 관심종목 ──
# (종목명, 티커, 기준지수)
WATCH_LIST = [
    ("테슬라",         "TSLA",   "나스닥100"),
    ("구글(알파벳)",   "GOOG",   "나스닥100"),
    ("엔비디아",       "NVDA",   "나스닥100"),
    ("SK하이닉스",     "000660", "코스피200"),
    ("현대자동차",     "005380", "코스피200"),
    ("삼성전자",       "005930", "코스피200"),
    ("삼성전자우",     "005935", "코스피200"),
    ("삼성전기",       "009150", "코스피200"),
    ("타이거200",      "102110", "코스피200"),
    ("월마트",         "WMT",    "S&P500"),
    ("존슨앤드존슨",   "JNJ",    "S&P500"),
    ("코카콜라",       "KO",     "S&P500"),
]

# ── 분류별 목표 비중 (리밸런싱용, %) ──
TARGET_ALLOCATION = {
    "국내종목":     15,
    "국내ETF":      25,
    "국내ETF-해외": 35,
    "해외종목":     15,
    "해외ETF":      10,
}

# ── 무위험수익률 (샤프지수 계산용) ──
RISK_FREE_RATE = 0.035

# ── 차트 저장 폴더 ──
CHART_DIR = "charts"

# ── 과제 헤더 (노션 페이지 상단 표시) ──
STUDENT_LINE = "컴퓨터과학전공 2216978 장희진"
COURSE_LINE  = "AI코딩을통한금융세상읽기 (001) 기말 프로젝트 과제"
STUDENT_ID   = "2216978"  # 노션 헤더 존재 여부 확인용
