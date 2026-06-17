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
    calc_risk, calc_rebalance, calc_market_snapshot,
    calc_realized_pnl, calc_trade_stats, calc_benchmark_comparison,
    calc_portfolio_history, calc_watchlist_monitor, calc_insights,
    calc_avg_correlation,
    fmt_won, fmt_pct
)
import charts_gen
import notion_sync as ns


# ────────────────────────────── 차트 생성 ──────────────────────────────
def build_charts():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"📊 차트 생성 시작 (기준일 {today})")

    holdings = calc_holdings()
    totals = calc_totals(holdings)
    print(f"   보유 {len(holdings)}종목 / 총평가 {fmt_won(totals[0])} ({fmt_pct(totals[2])})")

    charts_gen.make_pie_chart(holdings, today)
    print("   ✅ 분류별 파이차트")

    rows, index_returns, stock_returns = calc_index_analysis()
    charts_gen.make_index_chart(index_returns, stock_returns, config.WATCH_LIST, today)
    print("   ✅ 지수분석 비교차트")

    risk_rows = calc_risk(holdings)
    _, avg_corr = charts_gen.make_correlation_chart(holdings, today)
    print(f"   ✅ 상관관계 히트맵 (평균 {avg_corr:.2f})" if avg_corr else "   ✅ 상관관계 히트맵")

    charts_gen.make_summary_card(holdings, totals, risk_rows, today)
    print("   ✅ 종합 요약 카드")

    market_rows = calc_market_snapshot()
    charts_gen.make_market_snapshot_chart(market_rows, today)
    print("   ✅ 시장 현황 차트")

    _, port_ret, bench_ret = calc_benchmark_comparison(holdings)
    charts_gen.make_benchmark_chart(port_ret, bench_ret, today)
    print("   ✅ 벤치마크 비교 차트")

    history, monthly_returns = calc_portfolio_history()
    charts_gen.make_portfolio_history_chart(history, monthly_returns, today)
    print("   ✅ 포트폴리오 성과 차트")

    watch_rows = calc_watchlist_monitor()
    charts_gen.make_watchlist_heatmap(watch_rows, today)
    print("   ✅ 관심종목 모니터링 차트")

    print("📊 차트 생성 완료\n")


# ────────────────────────────── 데이터 수집 ──────────────────────────────
def _gather_data():
    today = datetime.now().strftime("%Y-%m-%d")
    cache_bust = os.environ.get("GITHUB_SHA", str(int(datetime.now().timestamp())))[:8]

    holdings = calc_holdings()
    totals = calc_totals(holdings)
    analysis_rows, index_returns, stock_returns = calc_index_analysis()
    risk_rows = calc_risk(holdings)
    rebal_rows = calc_rebalance(holdings)
    market_rows = calc_market_snapshot()
    bench_rows, port_ret, bench_ret = calc_benchmark_comparison(holdings)
    history, monthly_returns = calc_portfolio_history()
    watch_rows = calc_watchlist_monitor()
    realized, total_realized = calc_realized_pnl()
    trade_stats = calc_trade_stats()
    avg_corr = calc_avg_correlation(holdings)
    insights = calc_insights(holdings, totals, risk_rows, rebal_rows, analysis_rows, avg_corr)

    sorted_logs = sorted(config.TRADE_LOGS, key=lambda x: x[0], reverse=True)
    latest_date = sorted_logs[0][0] if sorted_logs else today.replace("-", "")
    latest_logs = [t for t in sorted_logs if t[0] == latest_date]

    urls = {
        "pie":     ns.github_raw_url("charts/pie_allocation.png", cache_bust),
        "index":   ns.github_raw_url("charts/index_analysis.png", cache_bust),
        "corr":    ns.github_raw_url("charts/correlation.png", cache_bust),
        "summary": ns.github_raw_url("charts/summary_card.png", cache_bust),
        "market":  ns.github_raw_url("charts/market_snapshot.png", cache_bust),
        "bench":   ns.github_raw_url("charts/benchmark_comparison.png", cache_bust),
        "history": ns.github_raw_url("charts/portfolio_history.png", cache_bust),
        "watch":   ns.github_raw_url("charts/watchlist_monitor.png", cache_bust),
    }
    return {
        "today": today, "holdings": holdings, "totals": totals,
        "analysis_rows": analysis_rows, "risk_rows": risk_rows,
        "rebal_rows": rebal_rows, "market_rows": market_rows,
        "bench_rows": bench_rows, "port_ret": port_ret, "bench_ret": bench_ret,
        "history": history, "monthly_returns": monthly_returns,
        "watch_rows": watch_rows, "realized": realized,
        "total_realized": total_realized, "trade_stats": trade_stats,
        "insights": insights, "latest_logs": latest_logs,
        "latest_date": latest_date, "urls": urls,
    }


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


# ────────────────────────────── 메인 페이지 ──────────────────────────────
def _main_page_children(d):
    total_eval, total_profit, total_pct = d["totals"]
    diff = d["port_ret"] - d["bench_ret"]
    insight_rows = [[i[0], i[1], i[2]] for i in d["insights"]]

    return [
        ns._callout(ns.project_header_text(), "🎓", "purple_background"),
        ns._callout(f"📅 기준일: {d['today']}   |   🔄 GitHub Actions가 매일 자동 업데이트합니다.",
                    "📊", "blue_background"),
        ns._divider(),
        ns._heading("🌐 오늘의 시장 현황"),
        ns._callout("코스피200 / S&P500 / 나스닥100 전일대비·5일 변동", "🌍"),
        ns._table(5, ["지수", "현재가", "전일대비", "5일변동", "추세"], d["market_rows"]),
        ns._heading("시장 현황 차트", 2),
        ns._image(d["urls"]["market"]),
        ns._divider(),
        ns._heading("💰 총자산"),
        ns._table(4, ["작성일자", "총평가금액", "총수익", "총수익률"],
                  [[d["today"], fmt_won(total_eval), fmt_won(total_profit), fmt_pct(total_pct)]]),
        ns._divider(),
        ns._heading("💡 투자 인사이트"),
        ns._callout("매매일지·리스크·리밸런싱·지수분석 데이터를 종합한 자동 알림", "🤖", "yellow_background"),
        ns._table(3, ["아이콘", "유형", "내용"], insight_rows),
        ns._divider(),
        ns._heading("📈 보유주식"),
        ns._table(8, ["종목이름", "티커", "평가금액", "수익", "수익률", "보유수량", "매입가", "분류"],
                  [[h["name"], h["ticker"], fmt_won(h["eval"]), fmt_won(h["profit"]),
                    fmt_pct(h["pct"]), str(h["qty"]), fmt_won(h["avg"]), h["cat"]] for h in d["holdings"]]),
        ns._heading("📊 분류별 비율", 2),
        ns._image(d["urls"]["pie"]),
        ns._divider(),
        ns._heading("📊 포트폴리오 vs 벤치마크"),
        ns._callout(f"6개월 가중수익률: 포트폴리오 {fmt_pct(d['port_ret'])} vs 벤치마크 {fmt_pct(d['bench_ret'])} "
                    f"(초과 {'+' if diff >= 0 else ''}{diff:.1f}%p)", "📐"),
        ns._image(d["urls"]["bench"]),
        ns._heading("종목별 벤치마크 비교", 2),
        ns._table(7, ["종목명", "티커", "벤치마크", "6M수익", "벤치수익", "초과수익", "판정"], d["bench_rows"]),
        ns._divider(),
        ns._heading(f"📋 최근 매매일지 ({d['latest_date']})"),
        ns._table(8, ["날짜", "종목이름", "티커", "매수/매도", "수량", "단가", "분류", "사유"],
                  [[t[0], t[1], t[2], t[3], str(t[4]), fmt_won(t[5]), t[6], t[7]] for t in d["latest_logs"]]),
        ns._callout("📋 전체 매매 이력은 하위 페이지 '매매일지 전체보기'에서 확인하세요.", "📋"),
        ns._divider(),
        ns._heading("📈 지수기반 종목분석"),
        ns._callout("분석기간: 최근 6개월 월별 수익률 | 기준: 코스피200/S&P500/나스닥100 | 지수대비 -10%p 이하 → 🔴 손절검토"),
        ns._heading("📋 지수분석 대상 리스트", 2),
        ns._table(7, ["종목명", "티커", "기준지수", "6개월누적", "지수누적", "지수대비차이", "판정"], d["analysis_rows"]),
        ns._heading("📊 6개월 월별 수익률 비교 차트", 2),
        ns._image(d["urls"]["index"]),
        ns._divider(),
        ns._heading("🎯 고급 분석 대시보드"),
        ns._heading("📊 종합 요약", 2),
        ns._image(d["urls"]["summary"]),
        ns._heading("⚠️ 리스크 지표 분석", 2),
        ns._callout("변동성=연환산 표준편차 | 샤프지수=위험대비수익(높을수록 우수) | MDD=최대낙폭 | 무위험수익률 3.5% 가정", "📐"),
        ns._table(7, ["종목명", "티커", "연변동성", "연수익률", "샤프지수", "최대낙폭", "등급"],
                  _risk_table_rows(d["risk_rows"])),
        ns._heading("🔗 종목 간 상관관계 (분산투자 점검)", 2),
        ns._image(d["urls"]["corr"]),
        ns._heading("⚖️ 리밸런싱 추천", 2),
        ns._callout("목표대비 ±5%p 이내 적정 / +5%p 초과 🔻비중축소 / -5%p 미만 🔺비중확대", "⚖️"),
        ns._table(5, ["분류", "현재비중", "목표비중", "갭", "추천"], d["rebal_rows"]),
        ns._divider(),
        ns._heading("📂 하위 페이지"),
        ns._callout("아래 하위 페이지가 자동 생성·갱신됩니다:  📋 매매일지 전체보기  |  🔍 관심종목 모니터링  |  📈 포트폴리오 성과 분석", "📂"),
    ]


def _update_main_page(page_id, d):
    blocks = ns.get_all_blocks(page_id)
    if ns.ensure_project_header(page_id, blocks):
        print("   ✅ 과제 헤더 추가")
        blocks = ns.get_all_blocks(page_id)
    total_eval, total_profit, total_pct = d["totals"]

    updates = [
        ("총자산", [[d["today"], fmt_won(total_eval), fmt_won(total_profit), fmt_pct(total_pct)]]),
        ("보유주식", [[h["name"], h["ticker"], fmt_won(h["eval"]), fmt_won(h["profit"]),
                       fmt_pct(h["pct"]), str(h["qty"]), fmt_won(h["avg"]), h["cat"]] for h in d["holdings"]]),
        ("매매일지", [[t[0], t[1], t[2], t[3], str(t[4]), fmt_won(t[5]), t[6], t[7]] for t in d["latest_logs"]]),
        ("지수분석 대상", d["analysis_rows"]),
        ("리스크 지표", _risk_table_rows(d["risk_rows"])),
        ("리밸런싱", d["rebal_rows"]),
    ]
    for keyword, rows in updates:
        tid = ns.find_table_after_heading(blocks, keyword)
        if tid:
            ns.update_table_rows(tid, rows)
            print(f"   ✅ {keyword}")

    image_updates = [
        ("분류별 비율", d["urls"]["pie"]),
        ("월별 수익률 비교", d["urls"]["index"]),
        ("종합 요약", d["urls"]["summary"]),
        ("상관관계", d["urls"]["corr"]),
    ]
    for keyword, url in image_updates:
        iid = ns.find_image_after_heading(blocks, keyword)
        if iid:
            ns.update_image(iid, url)
            print(f"   ✅ {keyword} 차트")

    new_sections = [
        ("시장 현황", 5, ["지수", "현재가", "전일대비", "5일변동", "추세"], d["market_rows"], "market", "시장 현황 차트"),
        ("투자 인사이트", 3, ["아이콘", "유형", "내용"],
         [[i[0], i[1], i[2]] for i in d["insights"]], None, None),
        ("포트폴리오 vs 벤치마크", 0, [], [], "bench", None),
        ("종목별 벤치마크", 7, ["종목명", "티커", "벤치마크", "6M수익", "벤치수익", "초과수익", "판정"],
         d["bench_rows"], None, None),
    ]
    for keyword, width, headers, rows, img_key, img_heading in new_sections:
        if not ns.has_section(blocks, keyword):
            section = [ns._divider(), ns._heading(
                f"{'🌐 ' if '시장' in keyword else '💡 ' if '인사이트' in keyword else '📊 '}{keyword}")]
            if width > 0:
                section.append(ns._table(width, headers, rows))
            if img_key:
                section.append(ns._image(d["urls"][img_key]))
            if img_heading:
                pass  # image already appended
            ns.append_blocks(page_id, section)
            print(f"   ➕ {keyword} 섹션 추가")
        else:
            if width > 0:
                tid = ns.find_table_after_heading(blocks, keyword)
                if tid:
                    ns.update_table_rows(tid, rows)
                    print(f"   ✅ {keyword}")
            if img_key:
                iid = ns.find_image_after_heading(blocks, keyword.split("vs")[0].strip() if "벤치마크" in keyword else "시장")
                if iid:
                    ns.update_image(iid, d["urls"][img_key])
                    print(f"   ✅ {keyword} 차트")

    ns.update_callout_date(blocks, d["today"])


# ────────────────────────────── 하위 페이지: 매매일지 ──────────────────────────────
def _trade_journal_children(d):
    ts = d["trade_stats"]
    all_logs = sorted(config.TRADE_LOGS, key=lambda x: x[0], reverse=True)
    log_rows = [[t[0], t[1], t[2], t[3], str(t[4]), fmt_won(t[5]), t[6], t[7]] for t in all_logs]

    realized_rows = []
    for r in d["realized"]:
        realized_rows.append([
            r["date"], r["name"], r["ticker"], str(r["qty"]),
            fmt_won(r["sell_price"]), fmt_won(r["avg_cost"]),
            fmt_won(r["pnl"]), fmt_pct(r["pnl_pct"])
        ])

    children = [
        ns._callout(f"📅 기준일: {d['today']}   |   🔄 GitHub Actions가 매일 자동 업데이트합니다.",
                    "📋", "blue_background"),
        ns._heading("📊 매매 통계 요약"),
        ns._table(4, ["항목", "매수", "매도", "합계"], [
            ["건수", str(ts["buy_count"]), str(ts["sell_count"]), str(ts["total_trades"])],
            ["금액", fmt_won(ts["buy_amount"]), fmt_won(ts["sell_amount"]), "-"],
            ["기간", ts["first_date"], ts["last_date"], f"{ts['active_days']}일"],
            ["실현손익", "-", "-", fmt_won(d["total_realized"])],
        ]),
        ns._divider(),
        ns._heading("📋 전체 매매 이력"),
        ns._table(8, ["날짜", "종목이름", "티커", "매수/매도", "수량", "단가", "분류", "사유"], log_rows),
    ]
    if realized_rows:
        children += [
            ns._divider(),
            ns._heading("💰 실현손익 내역"),
            ns._callout("매도 거래 기준 평균단가 대비 실현손익", "💰"),
            ns._table(8, ["날짜", "종목", "티커", "수량", "매도가", "평균단가", "실현손익", "수익률"],
                      realized_rows),
        ]
    return children


def _update_trade_journal(page_id, d):
    blocks = ns.get_all_blocks(page_id)
    ts = d["trade_stats"]
    all_logs = sorted(config.TRADE_LOGS, key=lambda x: x[0], reverse=True)
    log_rows = [[t[0], t[1], t[2], t[3], str(t[4]), fmt_won(t[5]), t[6], t[7]] for t in all_logs]

    tid = ns.find_table_after_heading(blocks, "매매 통계")
    if tid:
        ns.update_table_rows(tid, [
            ["건수", str(ts["buy_count"]), str(ts["sell_count"]), str(ts["total_trades"])],
            ["금액", fmt_won(ts["buy_amount"]), fmt_won(ts["sell_amount"]), "-"],
            ["기간", ts["first_date"], ts["last_date"], f"{ts['active_days']}일"],
            ["실현손익", "-", "-", fmt_won(d["total_realized"])],
        ])
        print("   ✅ 매매 통계")

    tid = ns.find_table_after_heading(blocks, "전체 매매")
    if tid:
        ns.update_table_rows(tid, log_rows)
        print("   ✅ 전체 매매 이력")

    if d["realized"]:
        realized_rows = [[r["date"], r["name"], r["ticker"], str(r["qty"]),
                          fmt_won(r["sell_price"]), fmt_won(r["avg_cost"]),
                          fmt_won(r["pnl"]), fmt_pct(r["pnl_pct"])] for r in d["realized"]]
        tid = ns.find_table_after_heading(blocks, "실현손익")
        if tid:
            ns.update_table_rows(tid, realized_rows)
            print("   ✅ 실현손익")

    ns.update_callout_date(blocks, d["today"])


# ────────────────────────────── 하위 페이지: 관심종목 ──────────────────────────────
def _watchlist_children(d):
    return [
        ns._callout(f"📅 기준일: {d['today']}   |   🔄 GitHub Actions가 매일 자동 업데이트합니다.",
                    "🔍", "purple_background"),
        ns._heading("🔍 관심종목 실시간 모니터링"),
        ns._callout("52주 고저 대비·일간 변동률·상태 판정 | config.py WATCH_LIST 관리", "📡"),
        ns._image(d["urls"]["watch"]),
        ns._heading("📋 관심종목 상세", 2),
        ns._table(8, ["종목명", "티커", "기준지수", "현재가", "일간변동", "고점대비", "저점대비", "상태"],
                  d["watch_rows"]),
        ns._divider(),
        ns._heading("📈 지수기반 종목분석 (6개월)"),
        ns._table(7, ["종목명", "티커", "기준지수", "6개월누적", "지수누적", "지수대비차이", "판정"],
                  d["analysis_rows"]),
        ns._heading("📊 6개월 월별 수익률 비교", 2),
        ns._image(d["urls"]["index"]),
    ]


def _update_watchlist(page_id, d):
    blocks = ns.get_all_blocks(page_id)

    iid = ns.find_image_after_heading(blocks, "관심종목")
    if not iid:
        iid = ns.find_image_after_heading(blocks, "모니터링")
    if iid:
        ns.update_image(iid, d["urls"]["watch"])
        print("   ✅ 관심종목 차트")

    for keyword, rows in [("관심종목 상세", d["watch_rows"]), ("지수기반", d["analysis_rows"])]:
        tid = ns.find_table_after_heading(blocks, keyword)
        if tid:
            ns.update_table_rows(tid, rows)
            print(f"   ✅ {keyword}")

    iid = ns.find_image_after_heading(blocks, "월별 수익률")
    if iid:
        ns.update_image(iid, d["urls"]["index"])
        print("   ✅ 지수분석 차트")

    ns.update_callout_date(blocks, d["today"])


# ────────────────────────────── 하위 페이지: 성과 분석 ──────────────────────────────
def _performance_children(d):
    total_eval, total_profit, total_pct = d["totals"]
    diff = d["port_ret"] - d["bench_ret"]
    ret_rows = [[r["month"], fmt_pct(r["return"]), fmt_won(r["value"])] for r in d["monthly_returns"]]

    return [
        ns._callout(f"📅 기준일: {d['today']}   |   🔄 GitHub Actions가 매일 자동 업데이트합니다.",
                    "📈", "green_background"),
        ns._heading("📈 포트폴리오 성과 분석"),
        ns._callout(f"총평가 {fmt_won(total_eval)} | 수익률 {fmt_pct(total_pct)} | "
                    f"벤치마크 대비 {'+' if diff >= 0 else ''}{diff:.1f}%p", "📊"),
        ns._image(d["urls"]["history"]),
        ns._heading("📋 월별 수익률", 2),
        ns._table(3, ["월", "수익률", "평가금액"], ret_rows if ret_rows else [["-", "-", "-"]]),
        ns._divider(),
        ns._heading("📊 포트폴리오 vs 벤치마크"),
        ns._image(d["urls"]["bench"]),
        ns._table(7, ["종목명", "티커", "벤치마크", "6M수익", "벤치수익", "초과수익", "판정"], d["bench_rows"]),
        ns._divider(),
        ns._heading("⚠️ 리스크 지표"),
        ns._table(7, ["종목명", "티커", "연변동성", "연수익률", "샤프지수", "최대낙폭", "등급"],
                  _risk_table_rows(d["risk_rows"])),
        ns._heading("🔗 상관관계", 2),
        ns._image(d["urls"]["corr"]),
    ]


def _update_performance(page_id, d):
    blocks = ns.get_all_blocks(page_id)

    for keyword, url_key in [("포트폴리오 성과", "history"), ("벤치마크", "bench"), ("상관관계", "corr")]:
        iid = ns.find_image_after_heading(blocks, keyword)
        if iid:
            ns.update_image(iid, d["urls"][url_key])
            print(f"   ✅ {keyword} 차트")

    ret_rows = [[r["month"], fmt_pct(r["return"]), fmt_won(r["value"])] for r in d["monthly_returns"]]
    tid = ns.find_table_after_heading(blocks, "월별 수익률")
    if tid and ret_rows:
        ns.update_table_rows(tid, ret_rows)
        print("   ✅ 월별 수익률")

    for keyword, rows in [("벤치마크", d["bench_rows"]), ("리스크", _risk_table_rows(d["risk_rows"]))]:
        tid = ns.find_table_after_heading(blocks, keyword, exclude="벤치마크" if keyword == "리스크" else None)
        if tid:
            ns.update_table_rows(tid, rows)
            print(f"   ✅ {keyword} 테이블")

    ns.update_callout_date(blocks, d["today"])


# ────────────────────────────── 노션 동기화 오케스트레이션 ──────────────────────────────
def sync_notion():
    d = _gather_data()
    print(f"📝 노션 동기화 시작 (기준일 {d['today']})")

    # 메인 페이지
    page_id = config.SWING_PAGE_ID
    if not page_id:
        page_id = ns.create_child_page(
            config.PARENT_PAGE_ID, "SWING Portfolio", "📊",
            _main_page_children(d)[:100]
        )
        print(f"\n⚠️  메인 페이지 생성됨. GitHub Secret 'SWING_PAGE_ID'에 등록:")
        print(f"    {page_id}")
    else:
        print("📝 메인 페이지 업데이트")
        _update_main_page(page_id, d)

    # 하위 페이지들
    sub_pages = [
        ("TRADE_JOURNAL_PAGE_ID", "📋 매매일지 전체보기", "📋",
         _trade_journal_children, _update_trade_journal),
        ("WATCHLIST_PAGE_ID", "🔍 관심종목 모니터링", "🔍",
         _watchlist_children, _update_watchlist),
        ("PERFORMANCE_PAGE_ID", "📈 포트폴리오 성과 분석", "📈",
         _performance_children, _update_performance),
    ]

    parent = page_id or config.PARENT_PAGE_ID
    for env_key, title, icon, create_fn, update_fn in sub_pages:
        sub_id = getattr(config, env_key, "")
        print(f"\n📝 {title}")
        if not sub_id:
            sub_id = ns.create_child_page(parent, title, icon, create_fn(d)[:100])
            secret_name = env_key
            print(f"   ⚠️  하위 페이지 생성됨. GitHub Secret '{secret_name}'에 등록:")
            print(f"       {sub_id}")
        else:
            update_fn(sub_id, d)

    print("\n🎉 노션 동기화 완료!")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("charts", "all"):
        build_charts()
    if mode in ("notion", "all"):
        sync_notion()
