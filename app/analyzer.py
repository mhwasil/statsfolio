from datetime import datetime

from app.api_client import GhostfolioClient
from app.models import AllocationItem, AnalysisResult, PortfolioSummary


def _parse_date(value) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.replace(tzinfo=None)
    return datetime.now()


class PortfolioAnalyzer:
    """Computes advanced portfolio performance metrics from Ghostfolio data."""

    def __init__(self, client: GhostfolioClient):
        self.client = client

    def full_analysis(self) -> AnalysisResult:
        orders_data = self.client.orders()
        holdings_data = self.client.holdings()
        details = self.client.details()
        performance = self.client.performance()
        investments_data = self.client.investments()
        user = self.client.user_settings()

        activities_raw = orders_data.get("activities", [])
        holdings_raw = holdings_data.get("holdings", [])
        chart = performance.get("chart", [])
        investments = investments_data.get("result", [])

        summary_raw = details.get("summary", {})
        summary = PortfolioSummary(**summary_raw)

        user_settings = user.get("settings", {})
        currency = user_settings.get("baseCurrency", "USD")

        mwr = self.compute_money_weighted_return(activities_raw, holdings_raw, currency)
        twr = self.compute_time_weighted_return(activities_raw, performance)
        alloc_class = self._alloc_by_asset_class(holdings_raw)
        alloc_holdings = self._alloc_by_holdings(holdings_raw)
        monthly = self.compute_monthly_returns(chart)
        drawdown = self.compute_drawdown(chart)
        text = self.generate_summary(summary, mwr, twr, alloc_holdings, holdings_raw, currency)

        return AnalysisResult(
            currency=currency,
            summary=summary,
            holdings_raw=holdings_raw,
            activities_raw=activities_raw,
            moneyWeightedReturn=mwr,
            timeWeightedReturn=twr,
            allocationByAssetClass=alloc_class,
            allocationByHoldings=alloc_holdings,
            monthlyReturns=monthly,
            drawdownData=drawdown,
            investmentsData=investments,
            summaryText=text,
        )

    # ------------------------------------------------------------------ #
    #  Money-Weighted Rate of Return (XIRR / IRR)
    # ------------------------------------------------------------------ #
    def compute_money_weighted_return(
        self, activities: list[dict], holdings: list[dict], currency: str
    ) -> dict:
        if not activities:
            return {"annualized": 0.0, "total": 0.0, "cashflows": [], "currency": currency}

        base_date = min(_parse_date(a.get("date")) for a in activities)

        cashflows: list[dict] = []
        for a in activities:
            d = _parse_date(a.get("date"))
            days = (d - base_date).days
            atype = a.get("type", "")

            value_base = float(a.get("valueInBaseCurrency", 0))
            fee_base = float(a.get("feeInBaseCurrency", 0))

            if atype in ("BUY", "FEE", "LIABILITY"):
                flow = -(abs(value_base) + fee_base)
            elif atype == "SELL":
                flow = abs(value_base) - fee_base
            elif atype == "DIVIDEND":
                flow = abs(value_base)
            elif atype == "INTEREST":
                flow = abs(value_base)
            else:
                continue

            cashflows.append({
                "date": d,
                "days": days,
                "flow": flow,
                "symbol": a.get("symbol", ""),
                "type": atype,
            })

        terminal_value = sum(float(h.get("valueInBaseCurrency", 0)) for h in holdings)
        last_activity_date = max(_parse_date(a.get("date")) for a in activities)
        today = datetime.now()
        last_date = max(last_activity_date, today)
        terminal_days = (last_date - base_date).days

        cashflows.append({
            "date": last_date,
            "days": terminal_days,
            "flow": terminal_value,
            "symbol": "__terminal__",
            "type": "TERMINAL",
        })

        annualized, total = self._xirr(cashflows)
        serializable = []
        for cf in cashflows:
            entry = {**cf}
            if isinstance(entry["date"], datetime):
                entry["date"] = entry["date"].isoformat()
            serializable.append(entry)

        return {
            "annualized": round(annualized, 4),
            "total": round(total, 4),
            "cashflows": serializable,
            "terminalValue": round(terminal_value, 2),
            "currency": currency,
        }

    @staticmethod
    def _xirr(cashflows: list[dict]) -> tuple[float, float]:
        flows = [cf["flow"] for cf in cashflows]
        days = [float(cf["days"]) for cf in cashflows]

        rate = PortfolioAnalyzer._bisection_xirr(flows, days)

        # Derive total return from annualized rate for consistency
        span_days = max(days) - min(days) if days else 0
        years = span_days / 365.0 if span_days > 0 else 1
        total_return = (1 + rate) ** years - 1 if rate > -1 else -1.0
        return float(rate), float(total_return)

    @staticmethod
    def _bisection_xirr(flows: list[float], days: list[float], lo: float = -0.99, hi: float = 10.0, tol: float = 1e-10) -> float:
        def npv(r: float) -> float:
            return sum(f / (1 + r) ** (d / 365.0) for f, d in zip(flows, days))

        npv_lo = npv(lo)
        npv_hi = npv(hi)

        if npv_lo * npv_hi > 0:
            for test_rate in (0.05, 0.1, 0.2, 0.5, -0.5):
                if npv(test_rate) * npv_lo < 0:
                    hi = test_rate
                    npv_hi = npv(hi)
                    break
                if npv(test_rate) * npv_hi < 0:
                    lo = test_rate
                    npv_lo = npv(lo)
                    break

        for _ in range(300):
            mid = (lo + hi) / 2.0
            mid_val = npv(mid)
            if mid_val > 0:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        return (lo + hi) / 2.0

    # ------------------------------------------------------------------ #
    #  Time-Weighted Rate of Return
    # ------------------------------------------------------------------ #
    def compute_time_weighted_return(
        self, activities: list[dict], performance: dict
    ) -> dict:
        chart = performance.get("chart", [])

        # Use monthly chart data to build sub-periods for visualization only
        monthly_values = {}
        for c in chart:
            d = c.get("date", "")
            v = c.get("value", 0)
            if isinstance(d, str) and len(d) >= 7:
                key = d[:7]
            elif isinstance(d, datetime):
                key = d.strftime("%Y-%m")
            else:
                continue
            monthly_values[key] = v

        sorted_months = sorted(monthly_values.items())

        # Find date range for years calculation
        first_date = sorted_months[0][0] if sorted_months else None
        last_date = sorted_months[-1][0] if sorted_months else None

        try:
            fd = datetime.strptime(first_date, "%Y-%m")
            ld = datetime.strptime(last_date, "%Y-%m")
            total_days = (ld - fd).days
        except Exception:
            total_days = 0

        years = total_days / 365.0 if total_days > 0 else 1

        # Use Ghostfolio's own netPerformancePercentage for total TWRR
        # (chart-based TWRR is unreliable with frequent cash flows)
        perf_data = performance.get("performance", {})
        total_return = perf_data.get("netPerformancePercentage", 0) or 0
        annualized = (1 + total_return) ** (1.0 / years) - 1 if years > 0 and total_return > -1 else 0.0

        return {
            "annualized": round(annualized, 4),
            "total": round(total_return, 4),
            "subPeriods": [],
            "method": "TWRR",
            "years": round(years, 2),
        }

    

    # ------------------------------------------------------------------ #
    #  Monthly Returns
    # ------------------------------------------------------------------ #
    def compute_monthly_returns(self, chart: list[dict]) -> list[dict]:
        if not chart:
            return []

        monthly: dict[str, dict] = {}
        for entry in chart:
            d = entry.get("date", "")
            val = entry.get("value", 0)
            if isinstance(d, str) and len(d) >= 7:
                key = d[:7]
            elif isinstance(d, datetime):
                key = d.strftime("%Y-%m")
            else:
                continue
            if key not in monthly:
                monthly[key] = {"date": key, "value": val, "return": 0.0}
            monthly[key]["value"] = val

        sorted_months = sorted(monthly.values(), key=lambda m: m["date"])
        for i in range(1, len(sorted_months)):
            prev = sorted_months[i - 1]["value"]
            curr = sorted_months[i]["value"]
            if prev and prev > 0:
                sorted_months[i]["return"] = round(curr / prev - 1.0, 4)

        return sorted_months

    # ------------------------------------------------------------------ #
    #  Drawdown Analysis
    # ------------------------------------------------------------------ #
    def compute_drawdown(self, chart: list[dict]) -> list[dict]:
        if not chart:
            return []

        values = [c.get("value", 0) for c in chart]
        dates = [c.get("date", "") for c in chart]
        if not values:
            return []

        peak = values[0]
        drawdowns = []
        for d, v in zip(dates, values):
            if v > peak:
                peak = v
            dd = (v - peak) / peak if peak != 0 else 0.0
            drawdowns.append({
                "date": d,
                "value": round(v, 2),
                "peak": round(peak, 2),
                "drawdown": round(dd, 4),
            })

        return drawdowns

    # ------------------------------------------------------------------ #
    #  Allocation Helpers
    # ------------------------------------------------------------------ #
    def _alloc_by_asset_class(self, holdings: list[dict]) -> list[AllocationItem]:
        class_map: dict[str, dict] = {}
        for h in holdings:
            ac = h.get("assetClass", "UNKNOWN")
            allocation = (h.get("allocationInPercentage", 0) or 0) * 100
            value = h.get("valueInBaseCurrency", 0) or 0
            if ac not in class_map:
                class_map[ac] = {"name": ac, "percentage": 0, "position": 0, "summary": 0}
            class_map[ac]["percentage"] += allocation
            class_map[ac]["position"] += value
            class_map[ac]["summary"] += h.get("investment", 0) or 0

        items = []
        for item in class_map.values():
            items.append(AllocationItem(
                name=item["name"],
                percentage=round(item["percentage"], 2),
                position=round(item["position"], 2),
                summary=round(item["summary"], 2),
            ))
        return sorted(items, key=lambda x: x.percentage, reverse=True)

    def _alloc_by_holdings(self, holdings: list[dict]) -> list[AllocationItem]:
        items = []
        for h in holdings:
            allocation = (h.get("allocationInPercentage", 0) or 0) * 100
            value = h.get("valueInBaseCurrency", 0) or 0
            investment = h.get("investment", 0) or 0
            items.append(AllocationItem(
                name=f"{h.get('symbol', '')} - {h.get('name', '') or ''}".strip(),
                percentage=round(allocation, 2),
                position=round(value, 2),
                summary=round(investment, 2),
            ))
        return sorted(items, key=lambda x: x.percentage, reverse=True)

    # ------------------------------------------------------------------ #
    #  Natural-language Summary
    # ------------------------------------------------------------------ #
    def generate_summary(
        self,
        summary: PortfolioSummary,
        mwr: dict,
        twr: dict,
        alloc: list[AllocationItem],
        holdings: list[dict],
        currency: str,
    ) -> str:
        parts: list[str] = []
        curr = summary.currentNetWorth or summary.currentValues or 0
        invested = summary.investment or 0
        net_perf_pct = (summary.netPerformancePercentage or 0) * 100
        annualized = (summary.annualizedPerformancePercentage or 0) * 100

        parts.append(f"Portfolio Overview: Current net worth is {currency} {curr:,.2f} with {currency} {invested:,.2f} invested.")

        if net_perf_pct:
            direction = "gain" if net_perf_pct > 0 else "loss"
            parts.append(f"The portfolio has delivered a cumulative net {direction} of {abs(net_perf_pct):.2f}%.")
        if annualized:
            parts.append(f"Annualized performance stands at {annualized:.2f}% per year.")

        mwr_ann = mwr.get("annualized", 0)
        twr_ann = twr.get("annualized", 0)
        if mwr_ann:
            parts.append(f"Money-weighted return (XIRR) is {mwr_ann * 100:.2f}% annualized, reflecting the timing of your cash flows.")
        if twr_ann:
            parts.append(f"Time-weighted return is {twr_ann * 100:.2f}% annualized, independent of cash flow timing.")

        if alloc:
            top = alloc[:3]
            top_str = ", ".join(f"{a.name} ({a.percentage:.1f}%)" for a in top)
            parts.append(f"Top holdings by allocation: {top_str}.")

        sorted_holdings = sorted(
            holdings,
            key=lambda h: (h.get("netPerformancePercentWithCurrencyEffect", 0) or 0),
            reverse=True,
        )
        top_gainers = sorted_holdings[:3]
        if top_gainers:
            gainers_str = ", ".join(
                f"{h.get('symbol', 'N/A')} ({(h.get('netPerformancePercentWithCurrencyEffect', 0) or 0) * 100:.1f}%)"
                for h in top_gainers
            )
            parts.append(f"Best performers: {gainers_str}.")

        top_losers = sorted_holdings[-3:] if len(sorted_holdings) >= 3 else sorted_holdings
        if top_losers:
            losers_str = ", ".join(
                f"{h.get('symbol', 'N/A')} ({(h.get('netPerformancePercentWithCurrencyEffect', 0) or 0) * 100:.1f}%)"
                for h in top_losers
            )
            parts.append(f"Weakest performers: {losers_str}.")

        if summary.firstOrderDate:
            d = summary.firstOrderDate
            if isinstance(d, str):
                d = datetime.fromisoformat(d)
            if d.tzinfo:
                d = d.replace(tzinfo=None)
            age = (datetime.now() - d).days
            parts.append(f"Portfolio age: {age} days since first transaction.")

        return " ".join(parts)
