# 📊 SWING Portfolio — GitHub 자동화 대시보드

매일 자동으로 주가를 반영해 노션 대시보드를 갱신하는 **개인 스윙 포트폴리오** 자동화 프로젝트입니다.
Colab/Imgur 없이 **GitHub Actions + GitHub 이미지 저장**으로 동작합니다.

## ✨ 특징

- **매일 자동 실행**: GitHub Actions가 매일 오전 8시(KST) 전체 갱신
- **매매일지 등록 시 즉시 반영**: `config.py` 수정 후 push하면 메인·하위 페이지·차트 전부 재계산
- **이미지 직접 호스팅**: 차트 PNG를 GitHub에 커밋, 노션은 raw URL로 참조
- **블록 비파괴 업데이트**: 노션 블록을 삭제하지 않고 내용만 갱신
- **메인 + 하위 3페이지**: 대시보드·매매일지·관심종목·성과분석을 페이지별로 분리

## 📂 노션 페이지 구성

### 메인 — SWING Portfolio

| 섹션 | 내용 |
|------|------|
| 🌐 오늘의 시장 현황 | 코스피200 / S&P500 / 나스닥100 전일대비·5일 변동 |
| 💰 총자산 | 총평가금액·총수익·총수익률 (현재가 반영) |
| 💡 투자 인사이트 | 리밸런싱·손절·집중도·상관관계 기반 자동 알림 |
| 📈 보유주식 | 종목별 평가·수익·수익률·분류 |
| 📊 포트폴리오 vs 벤치마크 | 6개월 가중수익률 vs 분류별 벤치마크 |
| 📋 최근 매매일지 | 가장 최근 거래일 기록 |
| 📈 지수기반 종목분석 | 관심종목 6개월 월별수익률 vs 기준지수 |
| 🎯 고급 분석 | 리스크·상관관계·리밸런싱 추천 |

### 하위 페이지 (자동 생성·갱신)

| 페이지 | 내용 |
|--------|------|
| 📋 매매일지 전체보기 | 전체 매매 이력, 매매 통계, 실현손익 |
| 🔍 관심종목 모니터링 | 52주 고저 대비, 일간 변동, 급등/급락 판정 |
| 📈 포트폴리오 성과 분석 | 월말 평가액 추이, 월별 수익률, 벤치마크·리스크 |

## 📊 생성 차트 (8종)

| 파일 | 설명 |
|------|------|
| `pie_allocation.png` | 분류별 비중 파이차트 |
| `index_analysis.png` | 지수별 6개월 월별수익률 비교 (3단) |
| `correlation.png` | 보유종목 상관관계 히트맵 |
| `summary_card.png` | KPI 종합 요약 카드 |
| `market_snapshot.png` | 주요 지수 전일대비 막대 차트 |
| `benchmark_comparison.png` | 포트폴리오 vs 벤치마크 수익률 |
| `portfolio_history.png` | 월말 평가액·월별 수익률 추이 |
| `watchlist_monitor.png` | 관심종목 일간 변동률 |

## 📁 파일 구조

```
AIFinance-Dashboard-Project/
├── config.py              # 매매일지·관심종목·목표비중 (여기만 수정)
├── analysis.py            # 보유·리스크·지수·벤치마크·인사이트 계산
├── charts_gen.py          # 차트 PNG 생성 (8종)
├── notion_sync.py         # 노션 API 동기화·하위페이지 관리
├── update.py              # 메인 실행 (charts / notion)
├── requirements.txt       # 패키지 목록
├── charts/                # 생성된 차트 PNG (GitHub에 커밋됨)
└── .github/workflows/
    └── update.yml         # GitHub Actions 자동화
```

---

## 🚀 설정 방법

### 1단계: GitHub 저장소 생성
1. GitHub에서 새 저장소 생성
2. 이 폴더의 모든 파일을 push

### 2단계: 노션 준비
- 노션 Integration 토큰 (`ntn_...`)
- 상위 페이지 ID (SWING Portfolio를 만들 부모 페이지)
- Integration을 상위 페이지에 연결 (··· → Connections)

### 3단계: GitHub Secrets 등록
저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| 이름 | 값 |
|------|-----|
| `NOTION_TOKEN` | 노션 Integration 토큰 |
| `PARENT_PAGE_ID` | 상위 페이지 ID |
| `SWING_PAGE_ID` | (처음엔 비워둠 — 4단계에서 등록) |
| `TRADE_JOURNAL_PAGE_ID` | (처음엔 비워둠 — 4단계에서 등록) |
| `WATCHLIST_PAGE_ID` | (처음엔 비워둠 — 4단계에서 등록) |
| `PERFORMANCE_PAGE_ID` | (처음엔 비워둠 — 4단계에서 등록) |

### 4단계: 최초 실행 → 페이지 생성
1. **Actions** 탭 → "SWING Portfolio 자동 업데이트" → **Run workflow**
2. 실행 로그에 출력되는 **페이지 ID**를 각 Secret에 등록
   - `SWING_PAGE_ID` — 메인 페이지
   - `TRADE_JOURNAL_PAGE_ID` — 매매일지 전체보기
   - `WATCHLIST_PAGE_ID` — 관심종목 모니터링
   - `PERFORMANCE_PAGE_ID` — 포트폴리오 성과 분석
3. Secret 등록 후 **Run workflow**를 한 번 더 실행

### 5단계: 완료
이후 매일 오전 8시(KST) 자동 갱신됩니다. `config.py` push 시에도 즉시 반영됩니다.

---

## 📝 새 매매 등록하는 법

`config.py`의 `TRADE_LOGS`에 한 줄 추가하고 push합니다.

```python
TRADE_LOGS = [
    # (날짜, 종목명, 티커, 매수/매도, 수량, 단가, 분류, 사유)
    ("20260620", "삼성전자", "005930", "매수", 2, 75000, "국내종목", "추가 매수"),
    ("20260701", "삼성전자", "005930", "매도", 1, 82000, "국내종목", "일부 익절"),
]
```

push 즉시 GitHub Actions가 실행되어 보유주식·총자산·차트·노션 전체가 갱신됩니다.

### 관심종목 추가

`config.py`의 `WATCH_LIST`에 추가합니다.

```python
WATCH_LIST = [
    # (종목명, 티커, 기준지수)
    ("테슬라", "TSLA", "나스닥100"),
]
```

기준지수: `코스피200`, `S&P500`, `나스닥100`

---

## 🛠️ 로컬 테스트 (선택)

```bash
pip install -r requirements.txt

# Windows (PowerShell)
$env:NOTION_TOKEN="ntn_..."
$env:PARENT_PAGE_ID="..."
$env:SWING_PAGE_ID="..."
$env:GITHUB_REPOSITORY="username/repo-name"

python update.py charts   # 차트만 생성
python update.py notion   # 노션 업데이트
python update.py          # 둘 다
```

---

## 🏆 적용 기술

| 분류 | 기술 |
|------|------|
| 시세·수익률 | yfinance 실시간 현재가, 보유종목 수익률·총자산 계산 |
| 리스크 분석 | 연환산 변동성, 샤프지수, 최대낙폭(MDD) |
| 벤치마킹 | 코스피200/S&P500/나스닥100 대비 6개월 수익률·손절검토 |
| 포트폴리오 | 분류별 목표비중 리밸런싱, 상관관계 히트맵, 월별 성과 추적 |
| 인사이트 | 리밸런싱·손절·집중도·상관관계 규칙 기반 자동 알림 |
| 시각화 | matplotlib 8종 차트 (파이·히트맵·KPI카드·시계열 등) |
| 자동화 | GitHub Actions 스케줄(cron) + config.py push 트리거 |
| 노션 연동 | Notion API, GitHub raw URL 이미지, 비파괴 블록 업데이트 |

---

## 📦 제출 시 포함 권장

- 소스 코드 (`*.py`, `requirements.txt`, `.github/workflows/`)
- 생성된 차트 (`charts/*.png`)
- 노션 공유 페이지 **전체 화면 스크린샷** (메인 + 하위 페이지)
- `__pycache__/`, `.venv/`는 제외
