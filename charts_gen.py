"""
SWING Portfolio 차트 생성 모듈
- 모든 차트를 charts/ 폴더에 png로 저장 (GitHub에 커밋됨)
- Imgur 불필요: 노션은 GitHub raw 링크로 이미지를 참조
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch
from datetime import datetime

from config import CHART_DIR
from analysis import get_yf_ticker, get_close_series, safe_download
from dateutil.relativedelta import relativedelta

WATCH_GROUPS = ["코스피200", "S&P500", "나스닥100"]


def _setup_korean_font():
    """나눔고딕 폰트 설정 (GitHub Actions에서 apt 설치됨)"""
    candidates = [f for f in fm.findSystemFonts()
                  if "NanumGothic" in f or "nanumgothic" in f.lower()]
    if candidates:
        fm.fontManager.addfont(candidates[0])
        plt.rcParams["font.family"] = fm.FontProperties(fname=candidates[0]).get_name()
    plt.rcParams["axes.unicode_minus"] = False


def _ensure_dir():
    os.makedirs(CHART_DIR, exist_ok=True)


def make_pie_chart(holdings, today):
    """분류별 비중 파이차트"""
    _setup_korean_font()
    _ensure_dir()

    cat_map = {}
    for h in holdings:
        cat_map[h["cat"]] = cat_map.get(h["cat"], 0) + h["eval"]
    labels = list(cat_map.keys())
    values = list(cat_map.values())
    total  = sum(values)

    COLORS = ["#4F6CF7", "#34C38F", "#F4A84A", "#E24B4A", "#8B5CF6", "#14B8A6"]
    colors = COLORS[:len(labels)]

    fig, ax = plt.subplots(figsize=(8, 6), facecolor="#FFFFFF")
    wedges, _, autotexts = ax.pie(
        values, labels=None,
        autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
        colors=colors, startangle=90, pctdistance=0.78,
        wedgeprops=dict(linewidth=2, edgecolor="white"),
    )
    for at in autotexts:
        at.set_fontsize(12); at.set_fontweight("bold"); at.set_color("white")

    legend_labels = [f"{l}  ₩{v:,.0f}  ({v/total*100:.1f}%)"
                     for l, v in zip(labels, values)]
    ax.legend(wedges, legend_labels, loc="lower center",
              bbox_to_anchor=(0.5, -0.18), ncol=2, fontsize=10, frameon=False)
    ax.set_title(f"SWING Portfolio — 분류별 비율\n기준일: {today}  |  총평가금액: ₩{total:,.0f}",
                 fontsize=13, fontweight="bold", pad=20, color="#1a1a2e")

    plt.tight_layout()
    path = os.path.join(CHART_DIR, "pie_allocation.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return path


def make_index_chart(index_returns, stock_returns, watch_list, today):
    """기준지수별 6개월 월별수익률 비교 (3단)"""
    _setup_korean_font()
    _ensure_dir()

    INDEX_COLORS = {"코스피200": "#2563EB", "S&P500": "#16A34A", "나스닥100": "#9333EA"}
    STOCK_COLORS = ["#F59E0B", "#EF4444", "#06B6D4", "#F97316",
                    "#84CC16", "#EC4899", "#14B8A6", "#6366F1", "#A78BFA"]

    fig, axes = plt.subplots(3, 1, figsize=(14, 18), facecolor="#F8F9FA")
    fig.suptitle(f"지수기반 종목분석 — 6개월 월별 수익률 비교\n기준일: {today}",
                 fontsize=15, fontweight="bold", y=0.98, color="#1a1a2e")

    for ax_idx, idx_name in enumerate(WATCH_GROUPS):
        ax = axes[ax_idx]
        ax.set_facecolor("#FFFFFF")
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color("#E5E7EB")
        ax.tick_params(colors="#6B7280", labelsize=9)
        ax.set_title(f"▶ {idx_name} 기준", fontsize=12, fontweight="bold",
                     color=INDEX_COLORS[idx_name], pad=10, loc="left")
        ax.axhline(0, color="#9CA3AF", linewidth=0.8)
        ax.set_ylabel("월별 수익률 (%)", fontsize=9, color="#6B7280")
        ax.grid(axis="y", color="#F3F4F6", linewidth=0.7, linestyle="--")

        if idx_name in index_returns:
            idx_ret = index_returns[idx_name]
            months  = [m.strftime("%y.%m") for m in idx_ret.index]
            ax.plot(months, idx_ret.values, color=INDEX_COLORS[idx_name],
                    linewidth=2.5, marker="o", markersize=5,
                    label=f"{idx_name} (지수)", zorder=5, linestyle="--")

        group = [(n, t, i) for n, t, i in watch_list if i == idx_name]
        ci = 0
        for name, ticker, idx in group:
            ret = stock_returns.get((name, ticker, idx))
            if ret is None:
                continue
            if idx_name in index_returns:
                common = ret.index.intersection(index_returns[idx_name].index)
                ret = ret.loc[common]
            months = [m.strftime("%y.%m") for m in ret.index]
            ax.plot(months, ret.values, color=STOCK_COLORS[ci % len(STOCK_COLORS)],
                    linewidth=1.6, marker="s", markersize=4, label=name, alpha=0.85)
            ci += 1

        ax.legend(loc="upper left", fontsize=8, framealpha=0.9,
                  ncol=min(len(group) + 1, 5))

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    path = os.path.join(CHART_DIR, "index_analysis.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#F8F9FA")
    plt.close()
    return path


def make_correlation_chart(holdings, today):
    """보유종목 상관관계 히트맵"""
    _setup_korean_font()
    _ensure_dir()

    start_1y = datetime.now() - relativedelta(years=1)
    price_data = {}
    for h in holdings:
        yft = get_yf_ticker(h["ticker"], h["cat"])
        df = safe_download(yft, start_1y)
        if df is not None and len(df) >= 20:
            price_data[h["name"]] = get_close_series(df).pct_change().dropna()

    if len(price_data) < 2:
        return None, None

    ret_df = pd.DataFrame(price_data).dropna()
    corr = ret_df.corr()

    fig, ax = plt.subplots(figsize=(10, 8), facecolor="white")
    im = ax.imshow(corr.values, cmap="RdYlBu_r", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.index)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(corr.index, fontsize=9)
    for i in range(len(corr.index)):
        for j in range(len(corr.columns)):
            val = corr.values[i, j]
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    color="white" if abs(val) > 0.6 else "black",
                    fontsize=8, fontweight="bold")
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("상관계수", fontsize=10)
    ax.set_title(f"보유종목 상관관계 히트맵 (1년 일간수익률)\n낮을수록 분산투자 효과 ↑  |  기준일: {today}",
                 fontsize=13, fontweight="bold", pad=15, color="#1a1a2e")

    plt.tight_layout()
    path = os.path.join(CHART_DIR, "correlation.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()

    mask = ~np.eye(len(corr), dtype=bool)
    avg_corr = float(corr.values[mask].mean())
    return path, avg_corr


def make_summary_card(holdings, totals, risk_rows, today):
    """종합 요약 KPI 카드 (다크테마)"""
    _setup_korean_font()
    _ensure_dir()

    total_eval, total_profit, total_pct = totals
    valid = [r for r in risk_rows if r["volatility"] is not None]
    avg_vol    = np.mean([r["volatility"] for r in valid]) if valid else 0
    avg_sharpe = np.mean([r["sharpe"] for r in valid]) if valid else 0

    fig = plt.figure(figsize=(14, 8), facecolor="#0F172A")
    fig.suptitle("SWING Portfolio — 종합 대시보드", fontsize=22, fontweight="bold",
                 color="white", y=0.96)
    fig.text(0.5, 0.90, f"기준일 {today}", fontsize=12, color="#94A3B8", ha="center")

    cards = [
        ("총평가금액", f"₩{total_eval:,.0f}", "#3B82F6"),
        ("총수익", f"₩{total_profit:,.0f}", "#22C55E" if total_profit >= 0 else "#EF4444"),
        ("총수익률", f"{'+' if total_pct>=0 else ''}{total_pct:.2f}%", "#22C55E" if total_pct >= 0 else "#EF4444"),
        ("보유종목수", f"{len(holdings)}종목", "#A855F7"),
        ("평균변동성", f"{avg_vol:.1f}%", "#F59E0B"),
        ("평균샤프지수", f"{avg_sharpe:.2f}", "#06B6D4"),
    ]
    positions = [(0.05, 0.48), (0.37, 0.48), (0.69, 0.48),
                 (0.05, 0.12), (0.37, 0.12), (0.69, 0.12)]
    for (label, value, color), (x, y) in zip(cards, positions):
        ax = fig.add_axes([x, y, 0.26, 0.32]); ax.axis("off")
        box = FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                             boxstyle="round,pad=0.02,rounding_size=0.08",
                             facecolor="#1E293B", edgecolor=color, linewidth=2.5,
                             transform=ax.transAxes)
        ax.add_patch(box)
        ax.text(0.5, 0.68, label, fontsize=13, color="#94A3B8",
                ha="center", va="center", transform=ax.transAxes)
        ax.text(0.5, 0.33, value, fontsize=22, fontweight="bold", color=color,
                ha="center", va="center", transform=ax.transAxes)

    path = os.path.join(CHART_DIR, "summary_card.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#0F172A")
    plt.close()
    return path


def make_market_snapshot_chart(market_rows, today):
    """주요 지수 전일대비 막대 차트"""
    _setup_korean_font()
    _ensure_dir()

    names, pcts = [], []
    for row in market_rows:
        if row[2] == "N/A":
            continue
        names.append(row[0])
        pcts.append(float(row[2].replace("%", "").replace("+", "")))

    if not names:
        return None

    colors = ["#22C55E" if p >= 0 else "#EF4444" for p in pcts]
    fig, ax = plt.subplots(figsize=(10, 5), facecolor="white")
    bars = ax.bar(names, pcts, color=colors, edgecolor="white", linewidth=1.5, width=0.55)
    for bar, p, c in zip(bars, pcts, colors):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + (0.15 if p >= 0 else -0.35),
                f"{'+' if p >= 0 else ''}{p:.2f}%", ha="center", fontsize=11, fontweight="bold", color=c)
    ax.axhline(0, color="#9CA3AF", linewidth=0.8)
    ax.set_ylabel("전일대비 (%)", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(f"오늘의 시장 현황 — 주요 지수 전일대비\n기준일: {today}",
                 fontsize=13, fontweight="bold", pad=15, color="#1a1a2e")
    plt.tight_layout()
    path = os.path.join(CHART_DIR, "market_snapshot.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return path


def make_benchmark_chart(port_ret, bench_ret, today):
    """포트폴리오 vs 벤치마크 6개월 수익률 비교"""
    _setup_korean_font()
    _ensure_dir()

    labels = ["내 포트폴리오", "가중 벤치마크"]
    values = [port_ret, bench_ret]
    colors = ["#3B82F6", "#94A3B8"]

    fig, ax = plt.subplots(figsize=(8, 5), facecolor="white")
    bars = ax.bar(labels, values, color=colors, edgecolor="white", linewidth=2, width=0.45)
    for bar, v, c in zip(bars, values, colors):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + (0.3 if v >= 0 else -0.8),
                f"{'+' if v >= 0 else ''}{v:.2f}%", ha="center", fontsize=14, fontweight="bold", color=c)
    ax.axhline(0, color="#9CA3AF", linewidth=0.8)
    diff = port_ret - bench_ret
    diff_text = f"{'+' if diff >= 0 else ''}{diff:.2f}%p"
    verdict = "🟢 아웃퍼폼" if diff > 0 else ("🔴 언더퍼폼" if diff < 0 else "🟡 동행")
    ax.set_title(f"포트폴리오 vs 벤치마크 (6개월)\n{verdict}  |  초과수익 {diff_text}  |  기준일: {today}",
                 fontsize=13, fontweight="bold", pad=15, color="#1a1a2e")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    path = os.path.join(CHART_DIR, "benchmark_comparison.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return path


def make_portfolio_history_chart(history, monthly_returns, today):
    """월말 포트폴리오 평가액 + 월별 수익률"""
    _setup_korean_font()
    _ensure_dir()

    if len(history) < 2:
        return None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), facecolor="#F8F9FA",
                                    gridspec_kw={"height_ratios": [2, 1]})
    fig.suptitle(f"포트폴리오 성과 추적\n기준일: {today}",
                 fontsize=15, fontweight="bold", y=0.98, color="#1a1a2e")

    months = [h["month"] for h in history]
    values = [h["value"] for h in history]
    ax1.set_facecolor("#FFFFFF")
    ax1.fill_between(range(len(months)), values, alpha=0.15, color="#3B82F6")
    ax1.plot(range(len(months)), values, color="#3B82F6", linewidth=2.5, marker="o", markersize=7)
    for i, (m, v) in enumerate(zip(months, values)):
        ax1.annotate(f"₩{v:,.0f}", (i, v), textcoords="offset points",
                     xytext=(0, 12), ha="center", fontsize=8, color="#3B82F6")
    ax1.set_xticks(range(len(months)))
    ax1.set_xticklabels(months, fontsize=9)
    ax1.set_ylabel("평가금액 (원)", fontsize=10)
    ax1.set_title("월말 포트폴리오 평가액", fontsize=12, fontweight="bold", loc="left")
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.grid(axis="y", color="#F3F4F6", linestyle="--")

    if monthly_returns:
        ret_months = [r["month"] for r in monthly_returns]
        rets = [r["return"] for r in monthly_returns]
        bar_colors = ["#22C55E" if r >= 0 else "#EF4444" for r in rets]
        ax2.set_facecolor("#FFFFFF")
        ax2.bar(ret_months, rets, color=bar_colors, edgecolor="white", width=0.5)
        for i, r in enumerate(rets):
            ax2.text(i, r + (0.2 if r >= 0 else -0.5), f"{'+' if r >= 0 else ''}{r:.1f}%",
                     ha="center", fontsize=9, fontweight="bold")
        ax2.axhline(0, color="#9CA3AF", linewidth=0.8)
        ax2.set_ylabel("월별 수익률 (%)", fontsize=10)
        ax2.set_title("월별 수익률", fontsize=12, fontweight="bold", loc="left")
        ax2.spines[["top", "right"]].set_visible(False)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    path = os.path.join(CHART_DIR, "portfolio_history.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="#F8F9FA")
    plt.close()
    return path


def make_watchlist_heatmap(watch_rows, today):
    """관심종목 일간변동률 히트맵 스타일 바차트"""
    _setup_korean_font()
    _ensure_dir()

    names, pcts, statuses = [], [], []
    for row in watch_rows:
        if row[4] == "N/A":
            continue
        names.append(row[0])
        pcts.append(float(row[4].replace("%", "").replace("+", "")))
        statuses.append(row[7])

    if not names:
        return None

    colors = []
    for p, s in zip(pcts, statuses):
        if "급등" in s or "고점" in s:
            colors.append("#22C55E")
        elif "급락" in s:
            colors.append("#EF4444")
        elif "저점" in s:
            colors.append("#3B82F6")
        else:
            colors.append("#22C55E" if p >= 0 else "#EF4444")

    fig, ax = plt.subplots(figsize=(12, max(5, len(names) * 0.5)), facecolor="white")
    y_pos = range(len(names))
    bars = ax.barh(y_pos, pcts, color=colors, edgecolor="white", height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=10)
    for bar, p in zip(bars, pcts):
        ax.text(bar.get_width() + (0.1 if p >= 0 else -0.1), bar.get_y() + bar.get_height() / 2,
                f"{'+' if p >= 0 else ''}{p:.2f}%", va="center",
                ha="left" if p >= 0 else "right", fontsize=9, fontweight="bold")
    ax.axvline(0, color="#9CA3AF", linewidth=0.8)
    ax.set_xlabel("일간 변동률 (%)", fontsize=10)
    ax.set_title(f"관심종목 모니터링 — 일간 변동률\n기준일: {today}",
                 fontsize=13, fontweight="bold", pad=15, color="#1a1a2e")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    path = os.path.join(CHART_DIR, "watchlist_monitor.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    return path
