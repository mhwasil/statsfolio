import pytest
from datetime import datetime

from app.models import PortfolioSummary, AllocationItem, AnalysisResult


def test_portfolio_summary_model():
    s = PortfolioSummary(
        currentValueInBaseCurrency=150000.0,
        activityCount=12,
        totalInvestment=120000.0,
        netPerformance=30000.0,
        netPerformancePercentage=0.25,
        annualizedPerformancePercent=0.125,
        dateOfFirstActivity=datetime(2022, 1, 1),
    )
    assert s.currentNetWorth == 150000.0
    assert s.itemCount == 12
    assert s.investment == 120000.0
    assert s.annualizedPerformancePercentage == 0.125
    assert s.netPerformancePercentage == 0.25


def test_allocation_item():
    a = AllocationItem(name="AAPL", percentage=25.5, position=10000.0, summary=8000.0)
    assert a.name == "AAPL"
    assert a.percentage == 25.5


def test_xirr_positive_return():
    from app.analyzer import PortfolioAnalyzer

    cashflows = [
        {"flow": -10000, "days": 0},
        {"flow": -5000, "days": 180},
        {"flow": 18000, "days": 365},
    ]
    rate, total = PortfolioAnalyzer._xirr(cashflows)
    assert rate > 0.1
    assert rate < 1.0


def test_xirr_negative_return():
    from app.analyzer import PortfolioAnalyzer

    cashflows = [
        {"flow": -10000, "days": 0},
        {"flow": 5000, "days": 365},
    ]
    rate, total = PortfolioAnalyzer._xirr(cashflows)
    assert rate < 0


def test_bisection_xirr():
    from app.analyzer import PortfolioAnalyzer

    flows = [-1000, 200, 400, 600, 800]
    days = [0.0, 90.0, 180.0, 270.0, 365.0]
    rate = PortfolioAnalyzer._bisection_xirr(flows, days)
    assert -0.99 < rate < 10.0


def test_monthly_returns():
    from app.analyzer import PortfolioAnalyzer
    analyzer = PortfolioAnalyzer.__new__(PortfolioAnalyzer)

    chart = [
        {"date": "2024-01-15", "value": 10000},
        {"date": "2024-02-15", "value": 10500},
        {"date": "2024-03-15", "value": 10200},
        {"date": "2024-04-15", "value": 11000},
    ]
    monthly = analyzer.compute_monthly_returns(chart)
    assert len(monthly) == 4
    assert monthly[0]["return"] == 0.0
    assert abs(monthly[1]["return"] - 0.05) < 0.001
    assert monthly[2]["return"] < 0


def test_drawdown():
    from app.analyzer import PortfolioAnalyzer
    analyzer = PortfolioAnalyzer.__new__(PortfolioAnalyzer)

    chart = [
        {"date": "2024-01", "value": 10000},
        {"date": "2024-02", "value": 11000},
        {"date": "2024-03", "value": 9000},
        {"date": "2024-04", "value": 10500},
    ]
    dd = analyzer.compute_drawdown(chart)
    assert len(dd) == 4
    assert dd[0]["drawdown"] == 0.0
    assert dd[2]["drawdown"] < 0


def test_parse_date():
    from app.analyzer import _parse_date

    d1 = _parse_date("2024-01-15T10:30:00Z")
    assert d1.year == 2024
    assert d1.month == 1
    assert d1.day == 15

    d2 = _parse_date("2024-06-01T00:00:00+00:00")
    assert d2.year == 2024
    assert d2.month == 6

    dt = datetime(2024, 3, 15, 12, 0, 0)
    d3 = _parse_date(dt)
    assert d3 == dt


def test_money_weighted_return_with_dicts():
    from app.analyzer import PortfolioAnalyzer
    analyzer = PortfolioAnalyzer.__new__(PortfolioAnalyzer)

    activities = [
        {"date": "2024-01-01T00:00:00Z", "type": "BUY", "quantity": 10, "unitPrice": 100.0, "fee": 5, "symbol": "AAPL"},
        {"date": "2024-06-01T00:00:00Z", "type": "BUY", "quantity": 5, "unitPrice": 120.0, "fee": 5, "symbol": "AAPL"},
        {"date": "2024-09-01T00:00:00Z", "type": "DIVIDEND", "quantity": 15, "unitPrice": 0.5, "fee": 0, "symbol": "AAPL"},
    ]
    holdings = [
        {"valueInBaseCurrency": 1800.0, "currency": "USD", "dateOfFirstActivity": "2024-01-01T00:00:00Z"},
    ]

    mwr = analyzer.compute_money_weighted_return(activities, holdings, "USD")
    assert "annualized" in mwr
    assert "cashflows" in mwr
    assert len(mwr["cashflows"]) > 0


def test_alloc_by_holdings_with_dicts():
    from app.analyzer import PortfolioAnalyzer
    analyzer = PortfolioAnalyzer.__new__(PortfolioAnalyzer)

    holdings = [
        {"symbol": "AAPL", "name": "Apple Inc.", "allocationInPercentage": 0.40, "valueInBaseCurrency": 10000.0, "investment": 8000.0},
        {"symbol": "MSFT", "name": "Microsoft Corp.", "allocationInPercentage": 0.30, "valueInBaseCurrency": 7500.0, "investment": 6000.0},
    ]

    alloc = analyzer._alloc_by_holdings(holdings)
    assert len(alloc) == 2
    assert alloc[0].percentage == 40.0
    assert alloc[1].percentage == 30.0
