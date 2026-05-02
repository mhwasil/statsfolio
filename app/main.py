"""Statsfolio -- Dash + AG Grid application."""

import json
from datetime import datetime
from pathlib import Path

import dash
from dash import html, dcc, callback, Input, Output, State, no_update
import dash_ag_grid as dag
import plotly.express as px
import plotly.graph_objects as go

from app.analyzer import PortfolioAnalyzer
from app.api_client import GhostfolioClient
from app.config import settings

APP_DIR = Path(__file__).resolve().parent

app = dash.Dash(
    __name__,
    assets_folder=str(APP_DIR / "assets"),
    suppress_callback_exceptions=True,
    requests_pathname_prefix=settings.BASE_URL + "/",
)
server = app.server

client = GhostfolioClient()
analyzer = PortfolioAnalyzer(client)

# --------------------------------------------------------------------------- #
#  Theme palettes
# --------------------------------------------------------------------------- #
THEMES = {
    "dark": {
        "bg": "#0f1117",
        "bg_card": "#1a1d2e",
        "text": "#e4e6f0",
        "text_muted": "#9ca3b4",
        "border": "#2a2e45",
        "accent": "#6366f1",
        "grid_color": "rgba(100, 116, 139, 0.5)",
        "ag_theme": "ag-theme-alpine-dark",
    },
    "light": {
        "bg": "#f5f5f5",
        "bg_card": "#ffffff",
        "text": "#1a1d2e",
        "text_muted": "#6b7280",
        "border": "#e0e0e0",
        "accent": "#6366f1",
        "grid_color": "rgba(0, 0, 0, 0.15)",
        "ag_theme": "ag-theme-alpine",
    },
}

GREEN = "#10b981"
RED = "#ef4444"

# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #


def fmt(value, currency="USD"):
    if value is None:
        return "N/A"
    return f"{currency} {value:,.2f}"


def pct(value):
    if value is None:
        return "N/A"
    return f"{value:.2f}%"


def chart_style(theme):
    """Return a layout dict themed for the current palette."""
    t = THEMES[theme]
    bg = t["bg_card"]
    return dict(
        paper_bgcolor=bg,
        plot_bgcolor=bg,
        font_color=t["text"],
        xaxis=dict(
            gridcolor=t["grid_color"],
            gridwidth=1,
            tickfont_color=t["text"],
            title_font_color=t["text"],
        ),
        yaxis=dict(
            gridcolor=t["grid_color"],
            gridwidth=1,
            tickfont_color=t["text"],
            title_font_color=t["text"],
        ),
    )


def _activity_symbol(act: dict) -> str:
    """Extract symbol from a Ghostfolio activity (SymbolProfile.symbol falls back to top-level)."""
    return (act.get("SymbolProfile") or {}).get("symbol", "") or act.get("symbol", "")


def compute_avg_prices(activities, holdings):
    """Weighted average buy price per (symbol, currency)."""
    holding_currency = {}
    for h in holdings:
        sym = h.get("symbol", "")
        curr = h.get("currency", "USD")
        if sym:
            holding_currency[sym] = curr

    aggregates: dict[tuple[str, str], dict[str, float]] = {}
    for act in activities:
        if act.get("type") != "BUY":
            continue
        sym = _activity_symbol(act)
        qty = act.get("quantity", 0) or 0
        unit_price = act.get("unitPrice", 0) or 0
        fee = act.get("fee", 0) or 0
        act_currency = act.get("currency", holding_currency.get(sym, "USD"))
        if not sym or not qty:
            continue
        key = (sym, act_currency)
        if key not in aggregates:
            aggregates[key] = {"total_value": 0, "total_qty": 0}
        aggregates[key]["total_value"] += qty * unit_price + fee
        aggregates[key]["total_qty"] += qty

    result: dict[tuple[str, str], float] = {}
    for key, data in aggregates.items():
        if data["total_qty"]:
            result[key] = data["total_value"] / data["total_qty"]
    return result


def _fetch_analysis_safe():
    """Run full_analysis and return (result, error)."""
    try:
        return analyzer.full_analysis(), None
    except Exception as exc:
        return None, str(exc)


def _fetch_orders_safe():
    try:
        return client.orders(), None
    except Exception as exc:
        return None, str(exc)


# --------------------------------------------------------------------------- #
#  AG Grid column definitions
# --------------------------------------------------------------------------- #

NUM_FMT = 'params.value != null ? params.value.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}) : "N/A"'

DASHBOARD_COL_DEFS = [
     {"headerName": "Symbol", "field": "symbol", "pinned": True, "minWidth": 100},
     {"headerName": "Name", "field": "name", "minWidth": 150},
     {"headerName": "Allocation %", "field": "allocationNum", "minWidth": 110},
     {"headerName": "Avg Price", "field": "avgPriceStr", "minWidth": 120, "valueGetter": "data.avgPriceNum"},
     {"headerName": "Market Value", "field": "marketValueStr", "minWidth": 130, "valueGetter": "data.marketValueNum"},
     {"headerName": "Invested", "field": "investmentStr", "minWidth": 120, "valueGetter": "data.investmentNum"},
     {"headerName": "Performance %", "field": "performanceNum", "minWidth": 120},
 ]

HOLDINGS_COL_DEFS = [
    {"headerName": "Symbol", "field": "symbol", "pinned": True, "minWidth": 100},
    {"headerName": "Name", "field": "name", "minWidth": 160},
    {"headerName": "Quantity", "field": "quantityNum", "minWidth": 100},
    {"headerName": "Avg Price", "field": "avgPriceStr", "minWidth": 120, "valueGetter": "data.avgPriceNum"},
    {"headerName": "Market Price", "field": "marketPriceStr", "minWidth": 130, "valueGetter": "data.marketPriceNum"},
    {"headerName": "Market Value", "field": "marketValueStr", "minWidth": 140, "valueGetter": "data.marketValueNum"},
    {"headerName": "Invested", "field": "investmentStr", "minWidth": 130, "valueGetter": "data.investmentNum"},
    {"headerName": "Change", "field": "changeStr", "minWidth": 120, "valueGetter": "data.changeNum", "cellClassRules": {"cell-positive": "params.data.changeNum > 0", "cell-negative": "params.data.changeNum < 0"}},
    {"headerName": "Change %", "field": "changePercentStr", "minWidth": 110, "valueGetter": "data.changePercentNum", "cellClassRules": {"cell-positive": "params.data.changePercentNum > 0", "cell-negative": "params.data.changePercentNum < 0"}},
    {"headerName": "Performance (no FX) %", "field": "performanceNoFxNum", "minWidth": 160, "cellClassRules": {"cell-positive": "params.value > 0", "cell-negative": "params.value < 0"}},
    {"headerName": "Performance %", "field": "performanceNum", "minWidth": 130, "cellClassRules": {"cell-positive": "params.value > 0", "cell-negative": "params.value < 0"}},
    {"headerName": "Allocation %", "field": "allocationNum", "minWidth": 120},
]

ACTIVITIES_COL_DEFS = [
    {"headerName": "Date", "field": "date", "minWidth": 110},
    {"headerName": "Symbol", "field": "symbol", "pinned": True, "minWidth": 100},
    {"headerName": "Name", "field": "name", "minWidth": 160},
    {"headerName": "Type", "field": "type", "minWidth": 100, "cellClassRules": {
        "badge-buy": "params.data.type === 'BUY'",
        "badge-sell": "params.data.type === 'SELL'",
        "badge-dividend": "params.data.type === 'DIVIDEND'",
        "badge-fee": "params.data.type === 'FEE'",
        "badge-interest": "params.data.type === 'INTEREST'",
        "badge-liability": "params.data.type === 'LIABILITY'",
    }},
    {"headerName": "Quantity", "field": "quantityNum", "minWidth": 100},
    {"headerName": "Unit Price", "field": "unitPriceNum", "minWidth": 120, "valueFormatter": "params.data.currency + ' ' + params.value.toFixed(2)"},
    {"headerName": "Fee", "field": "feeNum", "minWidth": 100, "valueFormatter": "params.data.currency + ' ' + params.value.toFixed(2)"},
    {"headerName": "Total", "field": "totalNum", "minWidth": 120, "valueFormatter": "params.data.currency + ' ' + params.value.toFixed(2)"},
    {"headerName": "Currency", "field": "currency", "minWidth": 90},
]

GRID_DEFAULT_OPTS = {
    "pagination": True,
    "paginationPageSize": 20,
    "pageSizes": [10, 20, 50, 100],
    "animateRows": True,
    "rowSelection": "single",
}

# --------------------------------------------------------------------------- #
#  KPI card helper
# --------------------------------------------------------------------------- #


def kpi_card(label, value, color=None):
    style = {"color": color} if color else {}
    return html.Div(
        [
            html.Div(label, className="kpi-label"),
            html.Div(value, className="kpi-value", style=style),
        ],
        className="kpi-card",
    )


# --------------------------------------------------------------------------- #
#  Page renderers
# --------------------------------------------------------------------------- #


def render_dashboard(theme="dark"):
    result, err = _fetch_analysis_safe()
    if err:
        return _error_block("Dashboard", err, theme)

    t = THEMES[theme]
    currency = result.currency
    holdings = result.holdings_raw
    activities = result.activities_raw
    avg_prices = compute_avg_prices(activities, holdings)

    # KPIs
    kpis = [
        kpi_card("Net Worth", fmt(result.summary.currentNetWorth or result.summary.currentValues, currency)),
        kpi_card("Invested", fmt(result.summary.investment or result.summary.committedFunds, currency)),
        kpi_card(
            "Net Performance",
            f"{fmt(result.summary.netPerformance, currency)} ({pct((result.summary.netPerformancePercentage or 0) * 100)})",
        ),
        kpi_card(
            "Net Perf (w/ FX)",
            f"{fmt(result.summary.netPerformanceWithCurrencyEffect, currency)} ({pct((result.summary.netPerformancePercentageWithCurrencyEffect or 0) * 100)})",
        ),
        kpi_card("Annualized", pct((result.summary.annualizedPerformancePercentage or 0) * 100)),
        kpi_card(
            "Annualized (w/ FX)",
            pct((result.summary.annualizedPerformancePercentWithCurrencyEffect or 0) * 100),
        ),
        kpi_card("MWRR (XIRR)", f"{(result.moneyWeightedReturn.get('annualized') or 0) * 100:.2f}%"),
        kpi_card("TWRR", f"{(result.timeWeightedReturn.get('annualized') or 0) * 100:.2f}%"),
    ]

    # Summary
    summary = html.Div(
        [html.H2("Portfolio Summary"), html.P(result.summaryText)],
        className="summary-box",
    )

    # Stats row
    stats = html.Div(
        [
            html.Div([html.Span("Total Holdings", className="stat-label"), html.Span(str(len(holdings)), className="stat-value")], className="stat-item"),
            html.Div([html.Span("Total Activities", className="stat-label"), html.Span(str(len(activities)), className="stat-value")], className="stat-item"),
            html.Div([html.Span("Base Currency", className="stat-label"), html.Span(currency, className="stat-value")], className="stat-item"),
        ],
        className="stats-row",
    )

    # Pie chart (allocation)
    pie_fig = _build_pie_chart(holdings, theme)

    # Performance bar chart
    perf_fig = _build_perf_bar_chart(holdings, theme)

    # Holdings AG Grid
    grid_rows = []
    for h in holdings[:20]:
        sym = h.get("symbol", "")
        h_currency = h.get("currency", "USD")
        net_perf = (h.get("netPerformancePercentWithCurrencyEffect", 0) or 0) * 100
        alloc = (h.get("allocationInPercentage", 0) or 0) * 100
        qty_h = float(h.get("quantity", 0))
        inv_h = float(h.get("investment", 0))
        mp_h = float(h.get("marketPrice", 0))
        mv_base_h = float(h.get("valueInBaseCurrency", 0))
        ap_base = inv_h / qty_h if qty_h > 0 else 0
        rate = (mp_h * qty_h / mv_base_h) if (mp_h and qty_h and mv_base_h) else 1
        ap = round(ap_base * rate, 2)
        mv_base = round(mv_base_h, 2)
        grid_rows.append({
            "symbol": sym,
            "name": h.get("name", "") or "",
            "allocationNum": round(alloc, 1),
            "avgPriceNum": ap,
            "avgPriceStr": f"{h_currency} {ap:.2f}",
            "marketValueNum": mv_base,
            "marketValueStr": f"{currency} {mv_base:.2f}",
            "investmentNum": round(inv_h, 2),
            "investmentStr": f"{currency} {inv_h:.2f}",
            "performanceNum": round(net_perf, 2),
        })

    holdings_grid = dag.AgGrid(
        columnDefs=DASHBOARD_COL_DEFS,
        rowData=grid_rows,
        className=f"{t['ag_theme']} ag-theme-gf",
        defaultColDef={"resizable": True, "sortable": True, "filter": True},
        dashGridOptions={"pagination": False},
        style={"height": "350px"},
    )

    return [
        html.H1("Portfolio Dashboard", className="page-title"),
        html.Div(kpis, className="kpi-grid"),
        summary,
        stats,
        html.Div(dcc.Graph(figure=_build_evolution_chart(result, theme), config={"displayModeBar": False}), key=f"evolution-{theme}", className="chart-card full-width"),
        html.Div(dcc.Graph(figure=pie_fig, config={"displayModeBar": False}), key=f"pie-{theme}", className="chart-card full-width"),
        html.Div(dcc.Graph(figure=perf_fig, config={"displayModeBar": False}), key=f"perf-{theme}", className="chart-card full-width"),
        html.Div([html.H2("Top Holdings"), holdings_grid], className="table-card"),
    ]


def render_analysis(theme="dark"):
    result, err = _fetch_analysis_safe()
    if err:
        return _error_block("Analysis", err, theme)

    t = THEMES[theme]
    currency = result.currency

    # Summary
    summary = html.Div(
        [html.H2("Analysis Summary"), html.P(result.summaryText)],
        className="summary-box",
    )

    # Ghostfolio performance breakdown KPIs
    gf_absolute = result.summary.netPerformance or 0
    gf_absolute_pct = (result.summary.netPerformancePercentage or 0) * 100
    gf_currency_effect = (result.summary.netPerformanceWithCurrencyEffect or 0) - (result.summary.netPerformance or 0)
    gf_currency_effect_pct = ((result.summary.netPerformancePercentageWithCurrencyEffect or 0) - (result.summary.netPerformancePercentage or 0)) * 100
    gf_net_perf = result.summary.netPerformanceWithCurrencyEffect or 0
    gf_net_perf_pct = (result.summary.netPerformancePercentageWithCurrencyEffect or 0) * 100
    gf_annualized = (result.summary.annualizedPerformancePercent or 0) * 100
    gf_annualized_fx = (result.summary.annualizedPerformancePercentWithCurrencyEffect or 0) * 100

    gf_kpis = [
        kpi_card("Absolute Performance", f"{currency} {gf_absolute:.2f} ({gf_absolute_pct:.2f}%)", GREEN if gf_absolute >= 0 else RED),
        kpi_card("Currency Effect", f"{currency} {gf_currency_effect:.2f} ({gf_currency_effect_pct:.2f}%)", GREEN if gf_currency_effect >= 0 else RED),
        kpi_card("Net Performance (w/ FX)", f"{currency} {gf_net_perf:.2f} ({gf_net_perf_pct:.2f}%)", GREEN if gf_net_perf >= 0 else RED),
        kpi_card("Annualized (no FX)", f"{gf_annualized:.2f}%"),
        kpi_card("Annualized (w/ FX)", f"{gf_annualized_fx:.2f}%"),
    ]

    # Computed return metrics
    mwr = result.moneyWeightedReturn
    twr = result.timeWeightedReturn
    current_investment = sum(float(h.get("investment", 0)) for h in result.holdings_raw)
    current_value = sum(float(h.get("valueInBaseCurrency", 0)) for h in result.holdings_raw)
    current_return = current_value - current_investment
    current_return_pct = (current_return / current_investment * 100) if current_investment > 0 else 0

    comp_kpis = [
        kpi_card("MWRR Annualized (XIRR)", f"{mwr.get('annualized', 0) * 100:.2f}%"),
        kpi_card("MWRR Total Return", f"{mwr.get('total', 0) * 100:.2f}%"),
        kpi_card("TWRR Annualized", f"{twr.get('annualized', 0) * 100:.2f}%"),
        kpi_card("TWRR Total Return", f"{twr.get('total', 0) * 100:.2f}%"),
    ]
    if mwr.get("terminalValue"):
        comp_kpis.append(kpi_card("Terminal Value", f"{currency} {mwr['terminalValue']:.2f}"))
    if twr.get("years"):
        comp_kpis.append(kpi_card("Period (Years)", str(twr["years"])))
    comp_kpis.append(kpi_card("Total Return (Value)", f"{currency} {gf_absolute:.2f}", GREEN if gf_absolute >= 0 else RED))
    comp_kpis.append(kpi_card("Current Investment", f"{currency} {current_investment:.2f}"))
    comp_kpis.append(kpi_card("Current Value", f"{currency} {current_value:.2f}"))
    comp_kpis.append(kpi_card("Current Return", f"{currency} {current_return:.2f} ({current_return_pct:.2f}%)", GREEN if current_return >= 0 else RED))

    # Holdings AG Grid
    avg_prices = compute_avg_prices(result.activities_raw, result.holdings_raw)
    holdings_rows = []
    for h in sorted(result.holdings_raw, key=lambda x: x.get("valueInBaseCurrency", 0), reverse=True):
        sym = h.get("symbol", "")
        h_currency = h.get("currency", "USD")
        net_perf = (h.get("netPerformancePercentWithCurrencyEffect", 0) or 0) * 100
        net_perf_no_fx = (h.get("netPerformancePercent", 0) or 0) * 100
        alloc = (h.get("allocationInPercentage", 0) or 0) * 100
        qty = float(h.get("quantity", 0))
        inv_base = float(h.get("investment", 0))
        mp_h = float(h.get("marketPrice", 0))
        mv_base_h = float(h.get("valueInBaseCurrency", 0))
        ap_base = inv_base / qty if qty > 0 else 0
        rate = (mp_h * qty / mv_base_h) if (mp_h and qty and mv_base_h) else 1
        ap = round(ap_base * rate, 2)
        mp = round(mp_h, 2)
        mv_base = round(mv_base_h, 2)
        holdings_rows.append({
            "symbol": sym,
            "name": h.get("name", "") or "",
            "quantityNum": round(qty, 2),
            "avgPriceNum": ap,
            "avgPriceStr": f"{h_currency} {ap:.2f}",
            "marketPriceNum": mp,
            "marketPriceStr": f"{h_currency} {mp:.2f}",
            "marketValueNum": mv_base,
            "marketValueStr": f"{currency} {mv_base:.2f}",
            "investmentNum": inv_base,
            "investmentStr": f"{currency} {inv_base:.2f}",
            "currency": h_currency,
            "changeNum": round((mp - ap) * qty, 2),
            "changeStr": f"{h_currency} {(mp - ap) * qty:.2f}",
            "changePercentNum": round((mp / ap - 1) * 100, 2) if ap > 0 else 0,
            "changePercentStr": f"{((mp / ap - 1) * 100 if ap > 0 else 0):.2f}",
            "performanceNum": round(net_perf, 2),
            "performanceNoFxNum": round(net_perf_no_fx, 2),
            "allocationNum": round(alloc, 1),
        })

    holdings_grid = dag.AgGrid(
        columnDefs=HOLDINGS_COL_DEFS,
        rowData=holdings_rows,
        className=f"{t['ag_theme']} ag-theme-gf",
        defaultColDef={"resizable": True, "sortable": True, "filter": True},
        dashGridOptions=GRID_DEFAULT_OPTS,
        style={"height": "600px"},
    )

    # Charts
    monthly_fig = _build_monthly_chart(result, theme)
    drawdown_fig = _build_drawdown_chart(result, theme)
    cashflow_fig = _build_cashflow_chart(result, theme)

    # Recent activities AG Grid
    activity_rows = []
    for a in sorted(result.activities_raw, key=lambda x: x.get("date", ""), reverse=True)[:50]:
        d = a.get("date", "")[:10]
        quantity = float(a.get("quantity", 0))
        unit_price = float(a.get("unitPrice", 0))
        fee = float(a.get("fee", 0))
        atype = a.get("type", "")
        total = quantity * unit_price + (fee if atype in ("BUY", "FEE") else -fee)
        activity_rows.append({
            "date": d,
            "symbol": _activity_symbol(a),
            "name": (a.get("SymbolProfile") or {}).get("name", "") or a.get("name", "") or "",
            "type": atype,
            "quantity": f"{quantity:.4f}",
            "unitPrice": f"{unit_price:,.2f}",
            "fee": f"{fee:,.2f}",
            "total": f"{total:,.2f}",
            "currency": a.get("currency", ""),
        })

    activities_grid = dag.AgGrid(
        columnDefs=ACTIVITIES_COL_DEFS,
        rowData=activity_rows,
        className=f"{THEMES[theme]['ag_theme']} ag-theme-gf",
        defaultColDef={"resizable": True, "sortable": True, "filter": True},
        dashGridOptions={"pagination": False},
        style={"height": "450px"},
    )

    return [
        html.H1("Performance Analysis", className="page-title"),
        summary,
        html.H2("Ghostfolio Performance Breakdown", className="section-title"),
        html.Div(gf_kpis, className="kpi-grid"),
        html.H2("Computed Return Metrics", className="section-title"),
        html.Div(comp_kpis, className="kpi-grid"),
        html.Div([html.H2("Holdings"), holdings_grid], className="table-card"),
        html.Div(dcc.Graph(figure=monthly_fig, config={"displayModeBar": False}), key=f"monthly-{theme}", className="chart-card full-width"),
        html.Div(dcc.Graph(figure=drawdown_fig, config={"displayModeBar": False}), key=f"drawdown-{theme}", className="chart-card full-width"),
        html.Div(dcc.Graph(figure=cashflow_fig, config={"displayModeBar": False}), key=f"cashflow-{theme}", className="chart-card full-width"),
        html.Div([html.H2("Recent Activities (Last 50)"), activities_grid], className="table-card"),
    ]



def render_activities(theme="dark"):
    orders_data, err = _fetch_orders_safe()
    if err:
        return _error_block("Activities", err, theme)

    t = THEMES[theme]
    activities = orders_data.get("activities", []) if orders_data else []

    rows = []
    for a in sorted(activities, key=lambda x: x.get("date", ""), reverse=True):
        d = a.get("date", "")[:10]
        quantity = float(a.get("quantity", 0))
        unit_price = float(a.get("unitPrice", 0))
        fee = float(a.get("fee", 0))
        atype = a.get("type", "")
        total = quantity * unit_price + (fee if atype in ("BUY", "FEE") else -fee)
        rows.append({
            "date": d,
            "symbol": _activity_symbol(a),
            "name": (a.get("SymbolProfile") or {}).get("name", "") or a.get("name", "") or "",
            "type": atype,
            "quantityNum": round(quantity, 2),
            "unitPriceNum": round(unit_price, 2),
            "feeNum": round(fee, 2),
            "totalNum": round(total, 2),
            "currency": a.get("currency", ""),
        })

    grid = dag.AgGrid(
        columnDefs=ACTIVITIES_COL_DEFS,
        rowData=rows,
        className=f"{t['ag_theme']} ag-theme-gf",
        defaultColDef={"resizable": True, "sortable": True, "filter": True},
        dashGridOptions=GRID_DEFAULT_OPTS,
        style={"height": "600px"},
    )

    return [
        html.H1(["Activities", html.Span(f"({len(rows)} transactions)", className="subtitle")], className="page-title"),
        html.Div([grid], className="table-card"),
    ]


def render_setup(theme="dark"):
    t = THEMES[theme]
    try:
        conn = client.test_connection()
    except Exception as exc:
        conn = {"status": "error", "detail": str(exc)}

    reachable = conn.get("status") == "ok"
    authenticated = conn.get("authenticated", False)

    status_rows = [
        {"Label": "API URL", "Value": settings.GHOSTFOLIO_HOST},
        {"Label": "API Key Set", "Value": "Yes" if settings.has_token else "No"},
        {"Label": "Ghostfolio Reachable", "Value": ("Yes" if reachable else f"No - {conn.get('detail', 'Unknown')}")},
        {"Label": "Authenticated", "Value": ("Yes" if authenticated else "No")},
    ]

    conn_grid = dag.AgGrid(
        columnDefs=[
            {"headerName": "Label", "field": "Label", "minWidth": 180},
            {"headerName": "Value", "field": "Value", "minWidth": 300},
        ],
        rowData=status_rows,
        className=f"{t['ag_theme']} ag-theme-gf",
        defaultColDef={"resizable": True},
        dashGridOptions={"pagination": False, "rowSelection": False},
        style={"height": "160px"},
    )

    # Fix instructions
    if not settings.has_token:
        steps = html.Ol(
            [
                html.Li(f"Open your Ghostfolio instance at {settings.GHOSTFOLIO_HOST}"),
                html.Li("Log in and go to Settings → API Keys"),
                html.Li("Create a new API key"),
                html.Li("Copy .env.example to .env in the python/ directory"),
                html.Li("Set GHOSTFOLIO_TOKEN to your API key"),
                html.Li("Restart the application"),
            ],
            className="steps",
        )
    elif not authenticated:
        steps = html.Ol(
            [
                html.Li("Verify your API key in .env is correct"),
                html.Li("Make sure the API key was created in your Ghostfolio instance"),
                html.Li("Restart the application after updating .env"),
                html.Li("If you see a 404 error, your instance may be behind a reverse proxy that masks auth errors"),
            ],
            className="steps",
        )
    else:
        steps = html.P("Everything looks good! Navigate to the Dashboard.")

    return [
        html.H1("Connection Setup", className="page-title"),
        html.Div([html.H2("Configuration"), conn_grid], className="summary-box"),
        html.Div([html.H2("How to Fix"), steps], className="summary-box"),
    ]


# --------------------------------------------------------------------------- #
#  Error helper
# --------------------------------------------------------------------------- #


def _error_block(title, message, theme):
    return [
        html.H1(title, className="page-title"),
        html.Div(
            [
                html.P(message, style={"fontSize": "1.1rem", "marginBottom": "1rem"}),
                html.A("Go to Setup Page", href="/setup", className="btn"),
            ],
            className="summary-box error-box",
        ),
    ]


# --------------------------------------------------------------------------- #
#  Chart builders
# --------------------------------------------------------------------------- #


def _build_pie_chart(holdings, theme="dark"):
    if not holdings:
        return _empty_chart("No holdings data", theme)

    sorted_h = sorted(holdings, key=lambda h: h.get("valueInBaseCurrency", 0), reverse=True)
    top = sorted_h[:10]
    labels = [h.get("symbol", "") for h in top]
    values = [float((h.get("allocationInPercentage", 0) or 0) * 100) for h in top]
    total_top = sum(values)
    if total_top < 100:
        labels.append("Other")
        values.append(round(100 - total_top, 2))

    colors = list(px.colors.qualitative.Set2) + ["#b0b0b0"]

    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        textposition="inside",
        textinfo="percent+label",
        marker_colors=colors[:len(labels)],
    ))
    fig.update_layout(
        title="Portfolio Allocation by Holding",
        showlegend=False,
        margin=dict(l=0, r=0, t=30, b=0),
        **chart_style(theme),
    )
    return fig


def _build_perf_bar_chart(holdings, theme="dark"):
    if not holdings:
        return _empty_chart("No holdings data", theme)

    top = sorted(holdings, key=lambda h: (h.get("netPerformancePercentWithCurrencyEffect", 0) or 0), reverse=True)[:15]
    returns = [(h.get("netPerformancePercentWithCurrencyEffect", 0) or 0) * 100 for h in top]
    colors = [GREEN if r >= 0 else RED for r in returns]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[h.get("symbol", "") for h in top],
        y=returns,
        marker_color=colors,
    ))
    fig.update_layout(
        title="Holdings Performance (%)",
        yaxis_title="Return (%)",
        xaxis_title="",
        **chart_style(theme),
    )
    return fig


def _build_monthly_chart(result, theme="dark"):
    if not result.monthlyReturns:
        return _empty_chart("No monthly returns data", theme)

    returns = [m.get("return", 0) * 100 for m in result.monthlyReturns]
    dates = [m["date"] for m in result.monthlyReturns]
    colors = [GREEN if r >= 0 else RED for r in returns]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=dates, y=returns, marker_color=colors))
    fig.update_layout(
        title="Monthly Returns (%)",
        xaxis_title="Month",
        yaxis_title="Return (%)",
        xaxis_tickangle=45,
        **chart_style(theme),
    )
    return fig


def _build_drawdown_chart(result, theme="dark"):
    if not result.drawdownData:
        return _empty_chart("No drawdown data", theme)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[d["date"] for d in result.drawdownData],
        y=[d["drawdown"] * 100 for d in result.drawdownData],
        fill="tozeroy",
        fillcolor="rgba(239, 68, 68, 0.3)",
        line=dict(color=RED),
        name="Drawdown",
    ))
    fig.update_layout(
        title="Portfolio Drawdown (%)",
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        **chart_style(theme),
    )
    return fig


def _build_cashflow_chart(result, theme="dark"):
    cfs = result.moneyWeightedReturn.get("cashflows")
    if not cfs:
        return _empty_chart("No cash flow data", theme)

    fig = go.Figure()
    for cf_type in ("BUY", "SELL", "DIVIDEND", "FEE"):
        type_cfs = [c for c in cfs if c.get("type") == cf_type]
        if not type_cfs:
            continue
        fig.add_trace(go.Scatter(
            x=[c["date"][:10] for c in type_cfs],
            y=[c["flow"] for c in type_cfs],
            mode="markers",
            name=cf_type,
            marker=dict(size=[max(8, min(30, abs(c["flow"]) / 100)) for c in type_cfs], opacity=0.7),
            text=[f"{c.get('symbol', '')}<br>Flow: {c['flow']:,.2f}" for c in type_cfs],
            hoverinfo="text",
        ))
    fig.update_layout(
        title="Cash Flow Timeline (Money-Weighted Analysis)",
        yaxis_title="Cash Flow",
        xaxis_title="Date",
        **chart_style(theme),
    )
    return fig


def _build_evolution_chart(result, theme="dark"):
    chart_data = []
    for c in result.monthlyReturns:
        d = c.get("date", "")
        if isinstance(d, str) and len(d) >= 7:
            d = d[:7]
        elif isinstance(d, datetime):
            d = d.strftime("%Y-%m")
        else:
            continue
        chart_data.append({"date": d, "value": c.get("value", 0)})

    cumulative_investment = {}
    for act in sorted(result.activities_raw, key=lambda x: x.get("date", "")):
        d = act.get("date", "")
        if isinstance(d, str) and len(d) >= 7:
            month = d[:7]
        elif isinstance(d, datetime):
            month = d.strftime("%Y-%m")
        else:
            continue
        atype = act.get("type", "")
        value = abs(float(act.get("valueInBaseCurrency", 0)))
        if atype in ("BUY", "FEE", "LIABILITY"):
            flow = value
        elif atype in ("SELL",):
            flow = -value
        else:
            flow = 0
        cumulative_investment[month] = cumulative_investment.get(month, 0) + flow

    all_dates = sorted(set(c["date"] for c in chart_data) | set(cumulative_investment.keys()))
    inv_map = dict(sorted(cumulative_investment.items()))
    chart_map = {c["date"]: c["value"] for c in chart_data}
    last_inv = 0
    last_val = 0
    inv_dates, inv_values, val_dates, val_values = [], [], [], []
    for d in all_dates:
        if d in inv_map:
            last_inv += inv_map[d]
        if d in chart_map:
            last_val = chart_map[d]
        inv_dates.append(d)
        inv_values.append(last_inv)
        val_dates.append(d)
        val_values.append(last_val)

    if not inv_dates:
        return _empty_chart("No evolution data", theme)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=inv_dates, y=inv_values, name="Invested", line=dict(color="#6366f1", width=2)))
    fig.add_trace(go.Scatter(x=val_dates, y=val_values, name="Current Value", line=dict(color=GREEN, width=2)))
    fig.update_layout(
        title="Portfolio Evolution",
        xaxis_title="Date",
        yaxis_title=result.currency,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis_tickangle=45,
        **chart_style(theme),
    )
    return fig


def _empty_chart(msg, theme="dark"):
    fig = go.Figure()
    t = THEMES[theme]
    fig.add_annotation(text=msg, showarrow=False, font_size=14, font_color=t["text"], xref="paper", yref="paper", x=0.5, y=0.5)
    fig.update_layout(**chart_style(theme))
    return fig


# --------------------------------------------------------------------------- #
#  Layout
# --------------------------------------------------------------------------- #


app.layout = html.Div(
    [
        dcc.Store(id="theme-store", data="dark", storage_type="local"),
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="exchange-rates-store", data="{}"),

        # Navbar
        html.Nav(
            [
                html.Div([html.A("Statsfolio", href="/", className="nav-brand-link")], className="nav-brand"),
                html.Div(
                    [
                        html.A("Dashboard", href="/", id="nav-dashboard"),
                        html.A("Analysis", href="/analysis", id="nav-analysis"),
                         html.A("Activities", href="/activities", id="nav-activities"),
                        html.A("Setup", href="/setup", id="nav-setup"),
                        html.Button("\u263e", id="theme-toggle", className="theme-toggle-btn", title="Toggle theme"),
                        dcc.Dropdown(id="currency-dropdown", className="currency-dropdown", placeholder="Currency"),
                    ],
                    className="nav-links",
                ),
            ],
            className="navbar",
        ),

        # Main content
        html.Main(
            dcc.Loading(
                html.Div(id="page-content"),
                type="circle",
                color=THEMES["dark"]["accent"],
            ),
            className="container",
        ),

        # Footer
        html.Footer(
            "Statsfolio \u2014 Powered by Dash, AG Grid &amp; Plotly",
            className="footer",
        ),

        # Currency conversion script (injected by callback)
        html.Div(id="currency-script"),
    ],
    id="app-root",
)


# --------------------------------------------------------------------------- #
#  Callbacks
# --------------------------------------------------------------------------- #


@callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    Input("theme-store", "data"),
)
def render_page(pathname, theme):
    if not theme:
        theme = "dark"
    if pathname == "/analysis":
        return render_analysis(theme)
    if pathname == "/activities":
        return render_activities(theme)
    if pathname == "/setup":
        return render_setup(theme)
    return render_dashboard(theme)


@callback(
    Output("theme-store", "data"),
    Input("theme-toggle", "n_clicks"),
    State("theme-store", "data"),
    prevent_initial_call=True,
)
def toggle_theme(n_clicks, current):
    if not current:
        current = "dark"
    return "light" if current == "dark" else "dark"


@callback(
    Output("nav-dashboard", "className"),
    Output("nav-analysis", "className"),
    Output("nav-activities", "className"),
    Output("nav-setup", "className"),
    Input("url", "pathname"),
)
def update_nav_active(pathname):
    base = ""
    active = "active"
    return (
        active if pathname in (None, "/") else base,
        active if pathname == "/analysis" else base,
        active if pathname == "/activities" else base,
        active if pathname == "/setup" else base,
    )


@callback(
    Output("currency-dropdown", "options"),
    Output("currency-dropdown", "value"),
    Output("exchange-rates-store", "data"),
    Input("url", "pathname"),
)
def load_exchange_rates(pathname):
    try:
        result = analyzer.full_analysis()
        base = result.currency
        rates = {base: 1.0}
        for h in result.holdings_raw:
            cur = h.get("currency")
            if cur and cur not in rates:
                qty = float(h.get("quantity", 0))
                price = float(h.get("marketPrice", 0))
                native_value = qty * price
                base_value = float(h.get("valueInBaseCurrency", 0))
                if native_value > 0:
                    rates[cur] = base_value / native_value
        options = [{"label": f"{cur}{' (base)' if cur == base else ''}", "value": cur} for cur in rates]
        return options, base, json.dumps({"base": base, "rates": rates})
    except Exception:
        return [{"label": "USD", "value": "USD"}], "USD", json.dumps({"base": "USD", "rates": {"USD": 1.0}})


@callback(
    Output("app-root", "className"),
    Input("theme-store", "data"),
)
def update_theme_class(theme):
    if not theme:
        theme = "dark"
    return f"theme-{theme}"


@callback(
    Output("theme-toggle", "children"),
    Input("theme-store", "data"),
)
def update_theme_icon(theme):
    if not theme:
        theme = "dark"
    return "\u263e" if theme == "dark" else "\u2600"


@callback(
    Output("currency-script", "children"),
    Input("exchange-rates-store", "data"),
)
def inject_currency_script(rates_json):
    return html.Script(
        f"""
        (function() {{
            const ratesData = {rates_json};
            const select = document.getElementById('currency-dropdown');
            if (!select) return;
            select.addEventListener('change', function() {{
                const target = this.value;
                const base = ratesData.base;
                const rates = ratesData.rates;
                if (!rates[target]) return;
                const factor = rates[base] / rates[target];
                document.querySelectorAll('[data-base-value]').forEach(function(el) {{
                    const val = parseFloat(el.dataset.baseValue);
                    if (!isNaN(val)) {{
                        const converted = val * factor;
                        const suffix = el.dataset.suffix || '';
                        el.textContent = el.textContent.replace(/[A-Z]{{3}}\\s*[-]?\\d[\\d,.]]*/, target + ' ' + converted.toLocaleString('en-US', {{minimumFractionDigits: 2, maximumFractionDigits: 2}}) + suffix);
                    }}
                }});
                document.querySelectorAll('.currency-label').forEach(function(el) {{
                    el.textContent = target;
                }});
            }});
        }})();
        """
    )


# --------------------------------------------------------------------------- #
#  Entry point
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    app.run(debug=True, port=8050)
