"""
SWING Portfolio 분석 모듈
- 보유주식/총자산/리스크/지수분석/리밸런싱 계산 로직을 모아둔 파일
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
from dateutil.relativedelta import relativedelta

from config import (
    TRADE_LOGS, WATCH_LIST, TARGET_ALLOCATION, RISK_FREE_RATE
)

INDEX_TICKERS = {
    "코스피200": "^KS200",
    "S&P500":    "^GSPC",
    "나스닥100":  "^NDX",
}


# ────────────────────────────── 공통 유틸 ──────────────────────────────
def fmt_won(v):
    return f"₩{v:,.0f}"


def fmt_pct(r):
    return f"{'+' if r >= 0 else ''}{r:.2f}%"


def get_yf_ticker(ticker, index_or_cat):
    """국내 종목(숫자 티커)은 .KS suffix 추가"""
    if ticker.isdigit():
        return ticker + ".KS"
    return ticker


def get_close_series(df):
    """yfinance 결과에서 Close를 항상 1차원 Series로 추출"""
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close


def safe_download(ticker_str, start, end=None):
    try:
        df = yf.download(ticker_str, start=start, end=end,
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        return df
    except Exception as e:
        print(f"  ⚠️  {ticker_str} 다운로드 실패: {e}")
        return None


def get_current_price(ticker, cat, fallback):
    """현재가 조회 — 실패 시 fallback(매입가) 반환"""
    yft = get_yf_ticker(ticker, cat)
    try:
        t = yf.Ticker(yft)
        p = t.fast_info.last_price
        if p and p > 0:
            return float(p)
    except Exception:
        pass
    return fallback


# ────────────────────────────── 보유주식 / 총자산 ──────────────────────────────
def calc_holdings():
    """매매일지 → 보유주식 + 현재가 반영 수익률"""
    hmap = {}
    for date, name, ticker, action, qty, price, cat, reason in TRADE_LOGS:
        if ticker not in hmap:
            hmap[ticker] = {"name": name, "ticker": ticker, "cat": cat,
                            "qty": 0, "cost": 0}
        if action == "매수":
            hmap[ticker]["qty"]  += qty
            hmap[ticker]["cost"] += qty * price
        else:
            hmap[ticker]["qty"]  -= qty

    holdings = []
    for ticker, h in hmap.items():
        if h["qty"] <= 0:
            continue
        avg = h["cost"] / h["qty"]
        cur = get_current_price(ticker, h["cat"], avg)
        ev  = cur * h["qty"]
        prf = ev - h["cost"]
        pct = prf / h["cost"] * 100 if h["cost"] else 0
        holdings.append({
            "name": h["name"], "ticker": ticker, "cat": h["cat"],
            "qty": h["qty"], "avg": avg, "current": cur,
            "eval": ev, "profit": prf, "pct": pct
        })
    return holdings


def calc_totals(holdings):
    total_eval   = sum(h["eval"] for h in holdings)
    total_cost   = sum(h["avg"] * h["qty"] for h in holdings)
    total_profit = total_eval - total_cost
    total_pct    = total_profit / total_cost * 100 if total_cost else 0
    return total_eval, total_profit, total_pct


# ────────────────────────────── 지수기반 분석 ──────────────────────────────
def _monthly_returns(ticker_str, start, end):
    df = safe_download(ticker_str, start, end)
    if df is None or len(df) < 5:
        return None
    close = get_close_series(df)
    returns = close.resample("ME").last().pct_change().dropna() * 100
    return returns if not returns.empty else None


def _cumret(ret):
    return float((1 + ret / 100).prod() - 1) * 100


def calc_index_analysis():
    """관심종목 6개월 월별수익률 vs 기준지수 + 손절검토 판정"""
    today_dt = datetime.now()
    start_dt = (today_dt - relativedelta(months=6)).replace(day=1)

    index_returns = {}
    for idx_name, idx_ticker in INDEX_TICKERS.items():
        r = _monthly_returns(idx_ticker, start_dt, today_dt)
        if r is not None:
            index_returns[idx_name] = r

    stock_returns = {}
    for name, ticker, idx in WATCH_LIST:
        yft = get_yf_ticker(ticker, idx)
        stock_returns[(name, ticker, idx)] = _monthly_returns(yft, start_dt, today_dt)

    rows = []
    for name, ticker, idx in WATCH_LIST:
        ret     = stock_returns.get((name, ticker, idx))
        idx_ret = index_returns.get(idx)
        if ret is not None and idx_ret is not None:
            common = ret.index.intersection(idx_ret.index)
            s_cum = _cumret(ret.loc[common])
            i_cum = _cumret(idx_ret.loc[common])
            diff  = s_cum - i_cum
            verdict = "🔴 손절검토" if diff <= -10 else ("🟡 관찰" if diff <= -5 else "🟢 유지")
            row = [name, ticker, idx, fmt_pct(s_cum), fmt_pct(i_cum),
                   f"{'+' if diff >= 0 else ''}{diff:.1f}%p", verdict]
        else:
            row = [name, ticker, idx, "N/A", "N/A", "N/A", "⚪ 데이터없음"]
        rows.append(row)

    return rows, index_returns, stock_returns


# ────────────────────────────── 리스크 지표 ──────────────────────────────
def calc_risk(holdings):
    """보유종목 1년 일간수익률 → 변동성·샤프·MDD"""
    start_1y = datetime.now() - relativedelta(years=1)
    rows = []
    for h in holdings:
        yft = get_yf_ticker(h["ticker"], h["cat"])
        df = safe_download(yft, start_1y)
        if df is None or len(df) < 20:
            rows.append({"name": h["name"], "ticker": h["ticker"],
                         "volatility": None, "ann_return": None,
                         "sharpe": None, "mdd": None, "grade": "⚪ N/A"})
            continue
        daily = get_close_series(df).pct_change().dropna()
        volatility = float(daily.std() * np.sqrt(252) * 100)
        ann_return = float(daily.mean() * 252 * 100)
        sharpe = (ann_return / 100 - RISK_FREE_RATE) / (volatility / 100) if volatility > 0 else 0
        cum  = (1 + daily).cumprod()
        peak = cum.cummax()
        mdd  = float(((cum - peak) / peak).min() * 100)
        grade = "🟢 안정" if volatility < 25 else ("🟡 보통" if volatility < 45 else "🔴 고위험")
        rows.append({"name": h["name"], "ticker": h["ticker"],
                     "volatility": volatility, "ann_return": ann_return,
                     "sharpe": sharpe, "mdd": mdd, "grade": grade})
    return rows


# ────────────────────────────── 리밸런싱 ──────────────────────────────
def calc_rebalance(holdings):
    cat_eval = {}
    for h in holdings:
        cat_eval[h["cat"]] = cat_eval.get(h["cat"], 0) + h["eval"]
    total_ev = sum(cat_eval.values())

    rows = []
    all_cats = set(list(cat_eval.keys()) + list(TARGET_ALLOCATION.keys()))
    for cat in sorted(all_cats):
        cur = cat_eval.get(cat, 0) / total_ev * 100 if total_ev else 0
        tgt = TARGET_ALLOCATION.get(cat, 0)
        gap = cur - tgt
        rec = "🔻 비중축소" if gap > 5 else ("🔺 비중확대" if gap < -5 else "✅ 적정")
        rows.append([cat, f"{cur:.1f}%", f"{tgt:.1f}%",
                     f"{'+' if gap >= 0 else ''}{gap:.1f}%p", rec])
    return rows


# ────────────────────────────── 상관관계 ──────────────────────────────
def calc_avg_correlation(holdings):
    """보유종목 평균 상관계수 (대각선 제외)"""
    start_1y = datetime.now() - relativedelta(years=1)
    price_data = {}
    for h in holdings:
        yft = get_yf_ticker(h["ticker"], h["cat"])
        df = safe_download(yft, start_1y)
        if df is not None and len(df) >= 20:
            price_data[h["name"]] = get_close_series(df).pct_change().dropna()
    if len(price_data) < 2:
        return None
    ret_df = pd.DataFrame(price_data).dropna()
    corr = ret_df.corr()
    mask = ~np.eye(len(corr), dtype=bool)
    return float(corr.values[mask].mean())


# ────────────────────────────── 시장 현황 ──────────────────────────────
def calc_market_snapshot():
    """주요 지수 전일대비·5일 변동"""
    rows = []
    for idx_name, idx_ticker in INDEX_TICKERS.items():
        df = safe_download(idx_ticker, datetime.now() - relativedelta(days=15))
        if df is None or len(df) < 2:
            rows.append([idx_name, "N/A", "N/A", "N/A", "⚪ 데이터없음"])
            continue
        close = get_close_series(df)
        today_close = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])
        change_pct = (today_close - prev_close) / prev_close * 100
        week_pct = 0.0
        if len(close) >= 6:
            week_pct = (today_close - float(close.iloc[-6])) / float(close.iloc[-6]) * 100
        trend = "🟢 상승" if change_pct > 0.3 else ("🔴 하락" if change_pct < -0.3 else "➡️ 보합")
        rows.append([
            idx_name, f"{today_close:,.2f}",
            fmt_pct(change_pct), fmt_pct(week_pct), trend
        ])
    return rows


# ────────────────────────────── 실현손익 / 매매 통계 ──────────────────────────────
def calc_realized_pnl():
    """매도 거래 실현손익 (평균단가 기준)"""
    hmap = {}
    realized = []
    for date, name, ticker, action, qty, price, cat, reason in TRADE_LOGS:
        if ticker not in hmap:
            hmap[ticker] = {"name": name, "cat": cat, "qty": 0, "cost": 0}
        if action == "매수":
            hmap[ticker]["qty"] += qty
            hmap[ticker]["cost"] += qty * price
        else:
            avg = hmap[ticker]["cost"] / hmap[ticker]["qty"] if hmap[ticker]["qty"] else price
            pnl = (price - avg) * qty
            pnl_pct = (price - avg) / avg * 100 if avg else 0
            realized.append({
                "date": date, "name": name, "ticker": ticker,
                "qty": qty, "sell_price": price, "avg_cost": avg,
                "pnl": pnl, "pnl_pct": pnl_pct, "cat": cat, "reason": reason
            })
            hmap[ticker]["qty"] -= qty
            hmap[ticker]["cost"] -= avg * qty
    total_realized = sum(r["pnl"] for r in realized)
    return realized, total_realized


def calc_trade_stats():
    """매매일지 통계 요약"""
    buys = [t for t in TRADE_LOGS if t[3] == "매수"]
    sells = [t for t in TRADE_LOGS if t[3] == "매도"]
    buy_amount = sum(t[4] * t[5] for t in buys)
    sell_amount = sum(t[4] * t[5] for t in sells)
    dates = sorted(set(t[0] for t in TRADE_LOGS))
    return {
        "total_trades": len(TRADE_LOGS),
        "buy_count": len(buys), "sell_count": len(sells),
        "buy_amount": buy_amount, "sell_amount": sell_amount,
        "first_date": dates[0] if dates else "-",
        "last_date": dates[-1] if dates else "-",
        "active_days": len(dates),
    }


# ────────────────────────────── 포트폴리오 vs 벤치마크 ──────────────────────────────
CAT_BENCHMARK = {
    "국내종목": "코스피200", "국내ETF": "코스피200",
    "국내ETF-해외": "S&P500", "해외종목": "나스닥100", "해외ETF": "S&P500",
}


def _holding_return_6m(ticker, cat):
    yft = get_yf_ticker(ticker, cat)
    start = datetime.now() - relativedelta(months=6)
    df = safe_download(yft, start)
    if df is None or len(df) < 5:
        return None
    close = get_close_series(df)
    return float((close.iloc[-1] / close.iloc[0] - 1) * 100)


def calc_benchmark_comparison(holdings):
    """보유 포트폴리오 가중수익률 vs 분류별 벤치마크"""
    total_ev = sum(h["eval"] for h in holdings)
    if not total_ev:
        return [], 0.0, 0.0

    port_ret = 0.0
    bench_ret = 0.0
    rows = []
    for h in holdings:
        weight = h["eval"] / total_ev
        h_ret = _holding_return_6m(h["ticker"], h["cat"])
        bench_name = CAT_BENCHMARK.get(h["cat"], "S&P500")
        bench_ticker = INDEX_TICKERS[bench_name]
        b_ret = _holding_return_6m(bench_ticker, bench_name)
        if h_ret is not None and b_ret is not None:
            port_ret += weight * h_ret
            bench_ret += weight * b_ret
            diff = h_ret - b_ret
            verdict = "🟢 아웃퍼폼" if diff > 3 else ("🔴 언더퍼폼" if diff < -3 else "🟡 동행")
            rows.append([
                h["name"], h["ticker"], bench_name,
                fmt_pct(h_ret), fmt_pct(b_ret),
                f"{'+' if diff >= 0 else ''}{diff:.1f}%p", verdict
            ])
        else:
            rows.append([h["name"], h["ticker"], bench_name, "N/A", "N/A", "N/A", "⚪ N/A"])
    return rows, port_ret, bench_ret


# ────────────────────────────── 포트폴리오 성과 이력 ──────────────────────────────
def calc_portfolio_history():
    """매매일지 기반 월말 포트폴리오 평가액 시뮬레이션 (최근 6개월)"""
    today_dt = datetime.now()
    months = []
    for i in range(5, -1, -1):
        m = (today_dt - relativedelta(months=i)).replace(day=1)
        months.append(m)

    history = []
    for month_end in months:
        me = (month_end + relativedelta(months=1)) - relativedelta(days=1)
        me_str = me.strftime("%Y%m%d")

        hmap = {}
        for date, name, ticker, action, qty, price, cat, reason in TRADE_LOGS:
            if date > me_str:
                continue
            if ticker not in hmap:
                hmap[ticker] = {"qty": 0, "cost": 0, "cat": cat}
            if action == "매수":
                hmap[ticker]["qty"] += qty
                hmap[ticker]["cost"] += qty * price
            else:
                hmap[ticker]["qty"] -= qty

        total_val = 0
        for ticker, h in hmap.items():
            if h["qty"] <= 0:
                continue
            yft = get_yf_ticker(ticker, h["cat"])
            df = safe_download(yft, month_end, me + relativedelta(days=1))
            if df is not None and len(df) > 0:
                price = float(get_close_series(df).iloc[-1])
            else:
                price = h["cost"] / h["qty"] if h["qty"] else 0
            total_val += price * h["qty"]

        if total_val > 0:
            history.append({"month": month_end.strftime("%Y-%m"), "value": total_val})

    monthly_returns = []
    for i in range(1, len(history)):
        prev_v = history[i - 1]["value"]
        cur_v = history[i]["value"]
        ret = (cur_v - prev_v) / prev_v * 100 if prev_v else 0
        monthly_returns.append({
            "month": history[i]["month"], "return": ret, "value": cur_v
        })
    return history, monthly_returns


# ────────────────────────────── 관심종목 모니터링 ──────────────────────────────
def calc_watchlist_monitor():
    """관심종목 현재가·일간변동·52주 고저 대비"""
    rows = []
    for name, ticker, idx in WATCH_LIST:
        yft = get_yf_ticker(ticker, idx)
        df = safe_download(yft, datetime.now() - relativedelta(years=1))
        if df is None or len(df) < 5:
            rows.append([name, ticker, idx, "N/A", "N/A", "N/A", "N/A", "⚪ N/A"])
            continue
        close = get_close_series(df)
        cur = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) >= 2 else cur
        day_pct = (cur - prev) / prev * 100
        high_52 = float(close.max())
        low_52 = float(close.min())
        from_high = (cur - high_52) / high_52 * 100
        from_low = (cur - low_52) / low_52 * 100 if low_52 else 0

        if from_high >= -5:
            status = "🔥 52주 고점 근접"
        elif from_low <= 5:
            status = "💎 52주 저점 근접"
        elif day_pct >= 3:
            status = "🚀 급등"
        elif day_pct <= -3:
            status = "📉 급락"
        else:
            status = "🟢 관찰"

        rows.append([
            name, ticker, idx, fmt_won(cur), fmt_pct(day_pct),
            fmt_pct(from_high), fmt_pct(from_low), status
        ])
    return rows


# ────────────────────────────── 투자 인사이트 ──────────────────────────────
def calc_insights(holdings, totals, risk_rows, rebal_rows, analysis_rows, avg_corr=None):
    """규칙 기반 투자 인사이트·알림"""
    insights = []
    total_pct = totals[2]

    if total_pct >= 10:
        insights.append(("🎉", "수익 달성", f"총수익률 {fmt_pct(total_pct)} — 목표 수익 구간 도달"))
    elif total_pct <= -5:
        insights.append(("⚠️", "손실 주의", f"총수익률 {fmt_pct(total_pct)} — 포트폴리오 전략 재점검 권장"))

    for row in rebal_rows:
        if "비중확대" in row[4]:
            insights.append(("⚖️", "리밸런싱", f"{row[0]}: {row[1]} → 목표 {row[2]} ({row[4]})"))
        elif "비중축소" in row[4]:
            insights.append(("⚖️", "리밸런싱", f"{row[0]}: {row[1]} → 목표 {row[2]} ({row[4]})"))

    stop_loss = [row for row in analysis_rows if "손절검토" in row[6]]
    for row in stop_loss[:3]:
        insights.append(("🔴", "손절검토", f"{row[0]}({row[1]}): 지수대비 {row[5]} — 성과 점검 필요"))

    if avg_corr is not None:
        if avg_corr > 0.7:
            insights.append(("🔗", "분산투자", f"평균 상관계수 {avg_corr:.2f} — 분산효과 낮음, 종목 다양화 검토"))
        elif avg_corr < 0.3:
            insights.append(("✅", "분산투자", f"평균 상관계수 {avg_corr:.2f} — 양호한 분산 구조"))

    high_risk = [r for r in risk_rows if r.get("grade") == "🔴 고위험"]
    if high_risk:
        names = ", ".join(r["name"] for r in high_risk)
        insights.append(("⚠️", "고위험 종목", f"{names} — 연변동성 45% 초과"))

    if holdings:
        total_ev = sum(h["eval"] for h in holdings)
        max_h = max(holdings, key=lambda h: h["eval"])
        conc = max_h["eval"] / total_ev * 100 if total_ev else 0
        if conc > 40:
            insights.append(("📌", "집중도 경고", f"{max_h['name']} 비중 {conc:.1f}% — 과도한 집중 주의"))

    if not insights:
        insights.append(("✅", "양호", "현재 특별한 경고 신호 없음 — 목표 비중 유지 권장"))
    return insights
