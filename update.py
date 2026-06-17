"""
SWING Portfolio 메인 실행 스크립트
- GitHub Actions가 이 파일을 실행합니다.
- 흐름: 데이터계산 → 차트생성 → (차트는 별도 스텝에서 git commit) → 노션 업데이트
- 2단계로 실행됩니다:
    python update.py charts   # 차트만 생성 (커밋 전)
    python update.py notion   # 노션 업데이트 (커밋 후, raw URL 유효)
- 인자 없이 실행하면 charts + notion 모두 수행 (로컬 테스트용)
"""

import sys
import os
from datetime import datetime

import config
from analysis import (
    calc_holdings, calc_totals, calc_index_analysis,
    calc_risk, calc_rebalance, fmt_won, fmt_pct
)
import charts_gen
import notion_sync as ns


def build_charts():
    """모든 차트를 charts/ 폴더에 생성"""
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📊 차트 생성 시작 (기준일 {today})")

    holdings = calc_holdings()
    totals   = calc_totals(holdings)
    print(f"   보유 {len(holdings)}종목 / 총평가 {fmt_won(totals[0])} ({fmt_pct(totals[2])})")

    # 파이차트
    charts_gen.make_pie_chart(holdings, today)
    print("   ✅ 분류별 파이차트")

    # 지수분석 차트
    rows, index_returns, stock_returns = calc_index_analysis()
    charts_gen.make_index_chart(index_returns, stock_returns, config.WATCH_LIST, today)
    print("   ✅ 지수분석 비교차트")

    # 리스크
    risk_rows = calc_risk(holdings)
    print("   ✅ 리스크 지표 계산")

    # 상관관계
    charts_gen.make_correlation_chart(holdings, today)
    print("   ✅ 상관관계 히트맵")

    # 종합카드
    charts_gen.make_summary_card(holdings, totals, risk_rows, today)
    print("   ✅ 종합 요약 카드")

    print("📊 차트 생성 완료\n")


def sync_notion():
    """노션 페이지 생성/업데이트"""
    today = datetime.now().strftime("%Y-%m-%d")
    cache_bust = os.environ.get("GITHUB_SHA", str(int(datetime.now().timestamp())))[:8]
    print(f"📝 노션 동기화 시작 (기준일 {today}, cache={cache_bust})")

    holdings = calc_holdings()
    total_eval, total_profit, total_pct = calc_totals(holdings)
    analysis_rows, index_returns, stock_returns = calc_index_analysis()
    risk_rows  = calc_risk(holdings)
    rebal_rows = calc_rebalance(holdings)

    # 차트 GitHub raw URL
    pie_url     = ns.github_raw_url("charts/pie_allocation.png", cache_bust)
    index_url   = ns.github_raw_url("charts/index_analysis.png", cache_bust)
    corr_url    = ns.github_raw_url("charts/correlation.png", cache_bust)
    summary_url = ns.github_raw_url("charts/summary_card.png", cache_bust)

    # 최근 매매일지
    sorted_logs = sorted(config.TRADE_LOGS, key=lambda x: x[0], reverse=True)
    latest_date = sorted_logs[0][0]
    latest_logs = [t for t in sorted_logs if t[0] == latest_date]

    page_id = config.SWING_PAGE_ID

    if not page_id:
        page_id = create_full_page(
            holdings, (total_eval, total_profit, total_pct),
            analysis_rows, risk_rows, rebal_rows,
            latest_logs, latest_date, today,
            pie_url, index_url, corr_url, summary_url
        )
        print(f"\n⚠️  새 페이지 생성됨. GitHub Secret 'SWING_PAGE_ID'에 등록하세요:")
        print(f"    {page_id}")
        return

    # 기존 페이지 업데이트
    update_existing_page(
        page_id, holdings, (total_eval, total_profit, total_pct),
        analysis_rows, risk_rows, rebal_rows,
        latest_logs, latest_date, today,
        pie_url, index_url, corr_url, summary_url
    )
    print("\n🎉 노션 동기화 완료!")


def create_full_page(holdings, totals, analysis_rows, risk_rows, rebal_rows,
                     latest_logs, latest_date, today,
                     pie_url, index_url, corr_url, summary_url):
    total_eval, total_profit, total_pct = totals

    children = [
        ns._callout(f"📅 작성일자: {today}   |   🔄 GitHub Actions가 매일 자동 업데이트합니다.",
                    "📊", "blue_background"),
        ns._divider(),
        # 총자산
        ns._heading("💰 총자산"),
        ns._table(4, ["작성일자", "총평가금액", "총수익", "총수익률"],
                  [[today, fmt_won(total_eval), fmt_won(total_profit), fmt_pct(total_pct)]]),
        ns._divider(),
        # 보유주식
        ns._heading("📈 보유주식"),
        ns._table(8, ["종목이름", "티커", "평가금액", "수익", "수익률", "보유수량", "매입가", "분류"],
                  [[h["name"], h["ticker"], fmt_won(h["eval"]), fmt_won(h["profit"]),
                    fmt_pct(h["pct"]), str(h["qty"]), fmt_won(h["avg"]), h["cat"]] for h in holdings]),
        # 분류별 비율
        ns._heading("📊 분류별 비율", 2),
        ns._image(pie_url),
        ns._divider(),
        # 최근 매매일지
        ns._heading(f"📋 최근 매매일지 ({latest_date})"),
        ns._table(8, ["날짜", "종목이름", "티커", "매수/매도", "수량", "단가", "분류", "사유"],
                  [[t[0], t[1], t[2], t[3], str(t[4]), fmt_won(t[5]), t[6], t[7]] for t in latest_logs]),
        ns._divider(),
        # 지수분석
        ns._heading("📈 지수기반 종목분석"),
        ns._callout("분석기간: 최근 6개월 월별 수익률 | 기준: 코스피200/S&P500/나스닥100 | 지수대비 -10%p 이하 → 🔴 손절검토"),
        ns._heading("📋 지수분석 대상 리스트", 2),
        ns._table(7, ["종목명", "티커", "기준지수", "6개월누적", "지수누적", "지수대비차이", "판정"], analysis_rows),
        ns._heading("📊 6개월 월별 수익률 비교 차트", 2),
        ns._image(index_url),
        ns._divider(),
        # 고급 분석
        ns._heading("🎯 고급 분석 대시보드"),
        ns._heading("📊 종합 요약", 2),
        ns._image(summary_url),
        ns._heading("⚠️ 리스크 지표 분석", 2),
        ns._callout("변동성=연환산 표준편차 | 샤프지수=위험대비수익(높을수록 우수) | MDD=최대낙폭 | 무위험수익률 3.5% 가정", "📐"),
        ns._table(7, ["종목명", "티커", "연변동성", "연수익률", "샤프지수", "최대낙폭", "등급"],
                  _risk_table_rows(risk_rows)),
        ns._heading("🔗 종목 간 상관관계 (분산투자 점검)", 2),
        ns._image(corr_url),
        ns._heading("⚖️ 리밸런싱 추천", 2),
        ns._callout("목표대비 ±5%p 이내 적정 / +5%p 초과 🔻비중축소 / -5%p 미만 🔺비중확대", "⚖️"),
        ns._table(5, ["분류", "현재비중", "목표비중", "갭", "추천"], rebal_rows),
    ]

    page = ns.notion.pages.create(
        parent={"page_id": config.PARENT_PAGE_ID},
        cover={"type": "external", "external": {
            "url": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1500&q=80"}},
        icon={"type": "emoji", "emoji": "📊"},
        properties={"title": {"title": [{"type": "text", "text": {"content": "SWING Portfolio"}}]}},
        children=children[:100]
    )
    return page["id"]


def _risk_table_rows(risk_rows):
    rows = []
    for r in risk_rows:
        if r["volatility"] is not None:
            rows.append([r["name"], r["ticker"], f"{r['volatility']:.1f}%",
                         f"{r['ann_return']:+.1f}%", f"{r['sharpe']:.2f}",
                         f"{r['mdd']:.1f}%", r["grade"]])
        else:
            rows.append([r["name"], r["ticker"], "N/A", "N/A", "N/A", "N/A", r["grade"]])
    return rows


def update_existing_page(page_id, holdings, totals, analysis_rows, risk_rows, rebal_rows,
                         latest_logs, latest_date, today,
                         pie_url, index_url, corr_url, summary_url):
    total_eval, total_profit, total_pct = totals
    blocks = ns.get_all_blocks(page_id)

    # 총자산
    tid = ns.find_table_after_heading(blocks, "총자산")
    if tid:
        ns.update_table_rows(tid, [[today, fmt_won(total_eval), fmt_won(total_profit), fmt_pct(total_pct)]])
        print("   ✅ 총자산")

    # 보유주식
    tid = ns.find_table_after_heading(blocks, "보유주식")
    if tid:
        ns.update_table_rows(tid, [[h["name"], h["ticker"], fmt_won(h["eval"]), fmt_won(h["profit"]),
                                    fmt_pct(h["pct"]), str(h["qty"]), fmt_won(h["avg"]), h["cat"]] for h in holdings])
        print("   ✅ 보유주식")

    # 분류별 비율 이미지
    iid = ns.find_image_after_heading(blocks, "분류별 비율")
    if iid:
        ns.update_image(iid, pie_url)
        print("   ✅ 분류별 파이차트")

    # 최근 매매일지
    tid = ns.find_table_after_heading(blocks, "매매일지")
    if tid:
        ns.update_table_rows(tid, [[t[0], t[1], t[2], t[3], str(t[4]), fmt_won(t[5]), t[6], t[7]] for t in latest_logs])
        print("   ✅ 매매일지")

    # 지수분석 테이블
    tid = ns.find_table_after_heading(blocks, "지수분석 대상")
    if tid:
        ns.update_table_rows(tid, analysis_rows)
        print("   ✅ 지수분석 테이블")

    # 지수분석 차트
    iid = ns.find_image_after_heading(blocks, "월별 수익률 비교")
    if iid:
        ns.update_image(iid, index_url)
        print("   ✅ 지수분석 차트")

    # 종합 요약 카드
    iid = ns.find_image_after_heading(blocks, "종합 요약")
    if iid:
        ns.update_image(iid, summary_url)
        print("   ✅ 종합 요약 카드")

    # 리스크 테이블
    tid = ns.find_table_after_heading(blocks, "리스크 지표")
    if tid:
        ns.update_table_rows(tid, _risk_table_rows(risk_rows))
        print("   ✅ 리스크 테이블")

    # 상관관계 이미지
    iid = ns.find_image_after_heading(blocks, "상관관계")
    if iid:
        ns.update_image(iid, corr_url)
        print("   ✅ 상관관계 히트맵")

    # 리밸런싱 테이블
    tid = ns.find_table_after_heading(blocks, "리밸런싱")
    if tid:
        ns.update_table_rows(tid, rebal_rows)
        print("   ✅ 리밸런싱 테이블")

    # 작성일자 callout
    for b in blocks:
        if b["type"] == "callout":
            txt = "".join(t["plain_text"] for t in b["callout"].get("rich_text", []))
            if "작성일자" in txt:
                ns.notion.blocks.update(block_id=b["id"], callout={
                    "rich_text": [{"type": "text", "text": {
                        "content": f"📅 작성일자: {today}   |   🔄 GitHub Actions가 매일 자동 업데이트합니다."}}],
                    "icon": {"type": "emoji", "emoji": "📊"}, "color": "blue_background"})
                break


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("charts", "all"):
        build_charts()
    if mode in ("notion", "all"):
        sync_notion()
