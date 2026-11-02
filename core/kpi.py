"""Deterministic KPI reports.

Performance / comparison questions ("Show Q4 2004 performance",
"Compare Q1 2005 vs Q1 2004") are answered here with plain pandas so the
numbers are always exact. The LLM is only used to write the short narrative
around those numbers (and a built-in template is used if the LLM fails).

Anything that is not a recognisable performance question returns None and is
handled by the normal pandas agent.
"""
import re
from dataclasses import dataclass

import pandas as pd

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_NAMES = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)

_PERIOD_RE = re.compile(
    r"(?P<q>\bq(?P<qn>[1-4])\s*(?:of\s*)?(?P<qy>20\d{2})\b)"
    r"|(?P<q2>\b(?P<qy2>20\d{2})\s*q(?P<qn2>[1-4])\b)"
    rf"|(?P<m>\b(?P<mn>{_MONTH_NAMES})\b\.?,?\s*(?P<my>20\d{{2}})\b)"
    r"|(?P<y>\b(?P<yy>20\d{2})\b)",
    re.IGNORECASE,
)

# The question must look like a performance/comparison request ...
_PERF_WORDS = (
    "performance", "compare", "comparison", " vs ", " vs. ", "versus",
    "how are we doing", "how are we performing",
)
# ... and must NOT be about a specific entity (those go to the agent).
_ENTITY_WORDS = (
    "customer", "product", "country", "category", "productline", "city",
    "territory", "dealsize", "deal size", "top ", "bottom ", "best ", "worst ",
)


@dataclass(frozen=True)
class Period:
    kind: str   # "month" | "quarter" | "year"
    year: int
    n: int = 0  # month number or quarter number

    @property
    def start(self) -> pd.Timestamp:
        if self.kind == "year":
            return pd.Timestamp(self.year, 1, 1)
        if self.kind == "quarter":
            return pd.Timestamp(self.year, 3 * (self.n - 1) + 1, 1)
        return pd.Timestamp(self.year, self.n, 1)

    @property
    def end(self) -> pd.Timestamp:
        """Last day of the period (inclusive)."""
        if self.kind == "year":
            return pd.Timestamp(self.year, 12, 31)
        if self.kind == "quarter":
            return self.start + pd.DateOffset(months=3) - pd.Timedelta(days=1)
        return self.start + pd.offsets.MonthEnd(0)

    @property
    def label(self) -> str:
        if self.kind == "year":
            return str(self.year)
        if self.kind == "quarter":
            return f"Q{self.n} {self.year}"
        return self.start.strftime("%b %Y")

    def previous_year(self) -> "Period":
        return Period(self.kind, self.year - 1, self.n)


def parse_periods(text: str):
    periods = []
    for m in _PERIOD_RE.finditer(text):
        if m.group("q"):
            periods.append(Period("quarter", int(m.group("qy")), int(m.group("qn"))))
        elif m.group("q2"):
            periods.append(Period("quarter", int(m.group("qy2")), int(m.group("qn2"))))
        elif m.group("m"):
            periods.append(Period("month", int(m.group("my")), MONTHS[m.group("mn").lower()[:3]]))
        else:
            periods.append(Period("year", int(m.group("yy"))))
    return periods


def _slice(df: pd.DataFrame, p: Period) -> pd.DataFrame:
    return df[(df["orderdate"] >= p.start) & (df["orderdate"] < p.end + pd.Timedelta(days=1))]


def compute_kpis(df: pd.DataFrame, p: Period):
    s = _slice(df, p)
    if s.empty:
        return None
    sales = float(s["sales"].sum())
    orders = int(s["ordernumber"].nunique())
    return {
        "sales": sales,
        "qty": int(s["quantityordered"].sum()),
        "orders": orders,
        "aov": sales / orders,  # Total Sales / unique order numbers (as in the prompt)
    }


def _growth(cur, prev):
    if prev is None or prev == 0:
        return None
    return (cur - prev) / prev * 100


def _money(v):
    return "N/A" if v is None else f"${v:,.2f}"


def _pct(v):
    return "N/A" if v is None else f"{v:.2f}%"


def _template_narrative(cur_label, prev_label, cur, prev, g):
    if prev is None:
        return (
            f"{cur_label} recorded {_money(cur['sales'])} in sales from {cur['qty']:,} units across "
            f"{cur['orders']:,} orders. No baseline data exists for {prev_label}, so growth cannot be calculated.",
            f"Average order value was {_money(cur['aov'])}.",
            "Add earlier-period data to enable year-over-year comparison.",
        )
    word = "grew" if g["sales"] >= 0 else "declined"
    aov_word = "rose" if g["aov"] >= 0 else "fell"
    summary = (
        f"Sales {word} {abs(g['sales']):.2f}% to {_money(cur['sales'])} in {cur_label} versus {prev_label}, "
        f"with quantity ordered {'up' if g['qty'] >= 0 else 'down'} {abs(g['qty']):.2f}%. "
        f"Average order value {aov_word} {abs(g['aov']):.2f}%."
    )
    trend = (
        "Growth is being driven by order volume rather than order size."
        if g["sales"] >= 0 and g["aov"] < 0 else
        "Both volume and order size moved in the same direction as sales."
        if (g["sales"] >= 0) == (g["aov"] >= 0) else
        "Order size moved against the overall sales direction."
    )
    action = (
        "Protect the gains: review which products and customers drove the increase."
        if g["sales"] >= 0 else
        "Investigate the main customers and product lines behind the decline."
    )
    return summary, trend, action


def _llm_narrative(llm, cur_label, prev_label, cur, prev, g):
    if llm is None or prev is None:
        return None
    prompt = (
        "You are a business performance analyst. Using ONLY the numbers below "
        "(do not invent or recompute any figures), write a short commentary.\n\n"
        f"{cur_label}: sales {_money(cur['sales'])}, quantity {cur['qty']:,}, "
        f"orders {cur['orders']:,}, average order value {_money(cur['aov'])}\n"
        f"{prev_label}: sales {_money(prev['sales'])}, quantity {prev['qty']:,}, "
        f"orders {prev['orders']:,}, average order value {_money(prev['aov'])}\n"
        f"Growth: sales {_pct(g['sales'])}, quantity {_pct(g['qty'])}, average order value {_pct(g['aov'])}\n\n"
        "Reply in EXACTLY this format, plain text, no markdown:\n"
        "SUMMARY: <2-3 sentences>\n"
        "TREND: <1 sentence>\n"
        "ACTION: <1 data-driven recommendation>"
    )
    try:
        content = llm.invoke(prompt).content
        if isinstance(content, list):  # some models return a list of parts
            content = "".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
        m = re.search(r"SUMMARY:\s*(.*?)\s*TREND:\s*(.*?)\s*ACTION:\s*(.*)", content, re.S)
        if m:
            return tuple(x.strip() for x in m.groups())
    except Exception:
        pass
    return None


def build_report(df: pd.DataFrame, query: str, llm=None):
    """Return (markdown, cacheable) for a performance question, or None if the
    question should be handled by the pandas agent instead."""
    q = f" {query.lower().strip()} "
    if not any(w in q for w in _PERF_WORDS) or any(w in q for w in _ENTITY_WORDS):
        return None
    periods = parse_periods(q)
    if not periods:
        return None

    cur_p = periods[0]
    prev_p = periods[1] if len(periods) > 1 else cur_p.previous_year()

    min_d, max_d = df["orderdate"].min().date(), df["orderdate"].max().date()
    cur = compute_kpis(df, cur_p)
    if cur is None:
        return (
            f"Invalid Date Range: The requested period does not exist. "
            f"Available data: {min_d} to {max_d}.",
            False,
        )
    prev = compute_kpis(df, prev_p)

    g = None
    if prev is not None:
        g = {k: _growth(cur[k], prev[k]) for k in ("sales", "qty", "aov")}

    narrative = _llm_narrative(llm, cur_p.label, prev_p.label, cur, prev, g)
    used_llm = narrative is not None
    if narrative is None:
        narrative = _template_narrative(cur_p.label, prev_p.label, cur, prev, g)
    summary, trend, action = narrative

    pv = prev or {}
    prev_col = prev_p.label if prev else f"{prev_p.label} (N/A - baseline missing)"
    rows = [
        ("Sales", _money(cur["sales"]), _money(pv.get("sales")), _pct(g and g["sales"])),
        ("Quantity", f"{cur['qty']:,}", f"{pv['qty']:,}" if prev else "N/A", _pct(g and g["qty"])),
        ("Avg Order Value", _money(cur["aov"]), _money(pv.get("aov")), _pct(g and g["aov"])),
    ]
    table = (
        f"| KPI | {cur_p.label} | {prev_col} | Growth (%) |\n"
        "|:---|:---:|:---:|:---:|\n"
        + "\n".join(f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows)
    )

    note = ""
    if cur_p.end.date() > max_d:
        note = (
            f"\n\n*Note: data ends {max_d}, so {cur_p.label} is only partially covered "
            f"and growth compares against a full {prev_p.label}.*"
        )

    text = (
        f"### Executive Summary\n{summary}\n\n"
        f"### KPI Table\n{table}\n\n"
        f"### Business Insights\n- **Trend**: {trend}\n- **Action**: {action}"
        f"{note}"
    )
    # Don't permanently cache a templated fallback when the LLM was expected.
    cacheable = used_llm or llm is None or prev is None
    return text, cacheable