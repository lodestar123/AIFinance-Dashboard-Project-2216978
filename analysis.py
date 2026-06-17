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
