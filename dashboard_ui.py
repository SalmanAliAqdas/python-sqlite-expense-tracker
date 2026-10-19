"""Presentation helpers for the Streamlit dashboard; no database access."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import escape

import altair as alt

from expense_tracker import format_pkr


INCOME = "#158567"
EXPENSE = "#db6c60"
TEAL = "#278b9a"


def savings_rate(income_paisa: int, expense_paisa: int) -> Decimal | None:
    """Return the share of income left after expenses, or None without income."""
    if income_paisa <= 0:
        return None
    return Decimal(income_paisa - expense_paisa) * 100 / Decimal(income_paisa)


def monthly_data(rows: list[dict]) -> list[dict]:
    """Aggregate integer paisa, including empty months between recorded months."""
    if not rows:
        return []
    totals: dict[str, dict[str, int]] = {}
    for row in rows:
        month = row["date"][:7]
        bucket = totals.setdefault(month, {"Income": 0, "Expense": 0})
        bucket[row["kind"]] += row["amount_paisa"]
    first, last = min(totals), max(totals)
    year, month = map(int, first.split("-"))
    result = []
    while f"{year:04d}-{month:02d}" <= last:
        key = f"{year:04d}-{month:02d}"
        bucket = totals.get(key, {"Income": 0, "Expense": 0})
        result.append({"Month": key + "-01", "Label": date(year, month, 1).strftime("%b %Y"),
                       "Income": bucket["Income"], "Expense": bucket["Expense"]})
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def summary_cards(totals: dict[str, int]) -> str:
    """Static, accessible KPI markup. Functional controls stay native Streamlit."""
    income, expenses, balance = (totals[key] for key in
                                 ("income_paisa", "expense_paisa", "balance_paisa"))
    rate = savings_rate(income, expenses)
    specs = [
        ("income", "↙", "Total income", income, "Money received"),
        ("expense", "↗", "Total expenses", expenses, "Money spent"),
        ("positive" if balance >= 0 else "negative", "⇄", "Net balance", balance, "Income minus expenses"),
    ]
    cards = []
    for tone, icon, label, amount, note in specs:
        number = format_pkr(amount).removeprefix("PKR ")
        cards.append(f'<article class="kpi-card {tone}"><div class="kpi-top">'
                     f'<span>{label}</span><span class="kpi-icon" aria-hidden="true">{icon}</span></div>'
                     f'<div class="kpi-value"><span class="kpi-currency">PKR</span> {number}</div>'
                     f'<div class="kpi-note">{note}</div></article>')
    rate_text = "—" if rate is None else f"{rate:,.1f}%"
    rate_note = "Add income to calculate" if rate is None else "Share of income retained"
    tone = "neutral" if rate is None else "positive" if rate >= 0 else "negative"
    cards.append(f'<article class="kpi-card {tone}"><div class="kpi-top">'
                 '<span>Savings rate</span><span class="kpi-icon" aria-hidden="true">%</span></div>'
                 f'<div class="kpi-value">{rate_text}</div><div class="kpi-note">{rate_note}</div></article>')
    return '<div class="kpi-grid" role="group" aria-label="Financial summary">' + "".join(cards) + "</div>"


def period_markup(rows: list[dict], label: str = "All time") -> str:
    if rows:
        dates = [date.fromisoformat(row["date"]) for row in rows]
        detail = f"{min(dates):%d %b %Y} – {max(dates):%d %b %Y}"
    else:
        detail = "No transactions yet"
    return ('<div class="reporting-period"><span class="period-label">REPORTING PERIOD</span>'
            f'<strong>{escape(label)}</strong><span>{escape(detail)}</span></div>')


def _polish(chart: alt.TopLevelMixin) -> alt.TopLevelMixin:
    return (chart.properties(background="#ffffff")
            .configure(font="sans-serif")
            .configure_view(stroke=None)
            .configure_axis(labelFontSize=11, labelColor="#738193", titleColor="#738193",
                            gridColor="#edf1f5", domain=False, ticks=False, labelPadding=10)
            .configure_legend(title=None, labelColor="#657386", labelFontSize=11,
                              orient="top", direction="horizontal", symbolType="circle", padding=10))


def spending_chart(months: list[dict]) -> alt.TopLevelMixin:
    values = [{"Month": row["Month"], "Spending": row["Expense"] / 100} for row in months]
    base = alt.Chart(alt.Data(values=values)).encode(
        x=alt.X("Month:T", title=None, axis=alt.Axis(format="%b %y", tickCount=5, grid=False)),
        y=alt.Y("Spending:Q", title=None, axis=alt.Axis(labelExpr="'PKR ' + format(datum.value, '~s')", tickCount=4)),
        tooltip=[alt.Tooltip("Month:T", title="Month", format="%B %Y"),
                 alt.Tooltip("Spending:Q", title="Expenses (PKR)", format=",.2f")],
    )
    area = base.mark_area(interpolate="monotone", color=TEAL, opacity=0.10)
    line = base.mark_line(interpolate="monotone", color=TEAL, strokeWidth=2.5,
                          point=alt.OverlayMarkDef(filled=True, fill="#ffffff", size=45,
                                                   stroke=TEAL, strokeWidth=2))
    return _polish((area + line).properties(height=255))


def category_chart(categories: list[dict]) -> alt.TopLevelMixin:
    values = [{"Category": row["category"], "Spending": row["total_paisa"] / 100}
              for row in categories]
    chart = alt.Chart(alt.Data(values=values)).mark_bar(
        color=TEAL, cornerRadiusEnd=4, height=16,
    ).encode(
        x=alt.X("Spending:Q", title=None,
                axis=alt.Axis(labelExpr="'PKR ' + format(datum.value, '~s')", tickCount=3)),
        y=alt.Y("Category:N", title=None, sort="-x", axis=alt.Axis(labelLimit=150)),
        tooltip=[alt.Tooltip("Category:N"), alt.Tooltip("Spending:Q", title="Expenses (PKR)", format=",.2f")],
    ).properties(height=max(255, len(categories) * 32))
    return _polish(chart)


def comparison_chart(months: list[dict]) -> alt.TopLevelMixin:
    values = [{"Month": row["Label"], "Type": kind, "Amount": row[kind] / 100}
              for row in months for kind in ("Income", "Expense")]
    chart = alt.Chart(alt.Data(values=values)).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X("Month:N", sort=[row["Label"] for row in months], title=None,
                axis=alt.Axis(labelAngle=0, labelOverlap="greedy", grid=False)),
        y=alt.Y("Amount:Q", title=None, axis=alt.Axis(labelExpr="'PKR ' + format(datum.value, '~s')", tickCount=4)),
        xOffset=alt.XOffset("Type:N", sort=["Income", "Expense"]),
        color=alt.Color("Type:N", scale=alt.Scale(domain=["Income", "Expense"], range=[INCOME, EXPENSE])),
        tooltip=[alt.Tooltip("Month:N"), alt.Tooltip("Type:N"),
                 alt.Tooltip("Amount:Q", title="Amount (PKR)", format=",.2f")],
    ).properties(height=280)
    return _polish(chart)
