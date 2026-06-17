# 📊 SWING Portfolio — GitHub 자동화 대시보드

매일 자동으로 주가를 반영해 노션 대시보드를 갱신하는 무인 자동화 프로젝트입니다.
Colab/Imgur 없이 **GitHub Actions + GitHub 이미지 저장**으로 동작합니다.

## ✨ 특징

- **매일 자동 실행**: GitHub Actions 스케줄러가 매일 오전 8시(KST) 자동 갱신
- **매매일지 등록 시 자동 갱신**: `config.py` 수정 후 push하면 전체 재계산
- **이미지 직접 호스팅**: 차트는 GitHub 저장소에 png로 저장, 노션은 raw 링크 참조
- **블록 비파괴**: 노션 블록을 삭제하지 않고 내용만 업데이트

## 📁 파일 구조

```
swing-portfolio/
├── config.py              # 매매일지·관심종목·설정 (여기만 수정)
├── analysis.py            # 계산 로직 (보유주식·리스크·지수분석·리밸런싱)
├── charts_gen.py          # 차트 png 생성
├── notion_sync.py         # 노션 API 동기화
├── update.py              # 메인 실행 (charts / notion)
├── requirements.txt       # 패키지 목록
├── charts/                # 생성된 차트 png 저장 폴더
└── .github/workflows/
    └── update.yml         # GitHub Actions 자동화 설정
```

---

## 🚀 설정 방법

### 1단계: GitHub 저장소 생성
1. GitHub에서 새 저장소 생성 (예: `swing-portfolio`)
2. 이 폴더의 모든 파일을 업로드 (push)

### 2단계: 노션 토큰/페이지 준비
- 노션 Integration 토큰 (`ntn_...`)
- 상위 페이지 ID (SWING Portfolio를 만들 부모 페이지)

### 3단계: GitHub Secrets 등록
저장소 → **Settings → Secrets and variables → Actions → New repository secret**

| 이름 | 값 |
|------|-----|
| `NOTION_TOKEN` | 노션 Integration 토큰 |
| `PARENT_PAGE_ID` | 상위 페이지 ID |
| `SWING_PAGE_ID` | (처음엔 비워둠 — 4단계에서 등록) |

### 4단계: 최초 실행 → 페이지 생성
1. 저장소 → **Actions** 탭 → "SWING Portfolio 자동 업데이트" → **Run workflow**
2. 실행 로그에 출력되는 **새 페이지 ID**를 복사
3. `SWING_PAGE_ID` Secret에 그 ID를 등록
4. 노션에서 생성된 페이지에 Integration 연결 (··· → Connections)

### 5단계: 끝!
이제 매일 자동 실행됩니다. 손댈 필요 없습니다.

---

## 📝 새 매매 등록하는 법

`config.py`의 `TRADE_LOGS`에 한 줄 추가하고 push 하면 끝입니다.

```python
TRADE_LOGS = [
    # ... 기존 ...
    ("20260620", "삼성전자", "005930", "매수", 2, 75000, "국내종목", "추가 매수"),
]
```

push 즉시 GitHub Actions가 돌면서 보유주식·총자산·차트가 전부 자동 갱신됩니다.

---

## 🛠️ 로컬 테스트 (선택)

```bash
pip install -r requirements.txt
export NOTION_TOKEN="ntn_..."
export PARENT_PAGE_ID="..."
export SWING_PAGE_ID="..."
export GITHUB_REPOSITORY="username/swing-portfolio"

python update.py charts   # 차트만 생성
python update.py notion   # 노션 업데이트
python update.py          # 둘 다
```

---

## 🏆 적용 기술

- 실시간 현재가 반영 수익률 분석 (yfinance)
- 리스크 분석: 연환산 변동성, 샤프지수, 최대낙폭(MDD)
- 지수 벤치마킹: 코스피200/S&P500/나스닥100 대비 + 손절검토 판정
- 상관관계 히트맵 (분산투자 점검)
- 리밸런싱 엔진 (목표비중 대비 갭 분석)
- CI/CD 자동화: GitHub Actions 스케줄 + 이벤트 트리거
