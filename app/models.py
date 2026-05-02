from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PortfolioSummary(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    allTimeHighDate: datetime | None = None
    annualizedPerformancePercent: float | None = None
    annualizedPerformancePercentWithCurrencyEffect: float | None = None
    cash: float = 0.0
    committedFunds: float = 0.0
    currentValueInBaseCurrency: float | None = None
    dateOfFirstActivity: datetime | None = None
    dividendInBaseCurrency: float = 0.0
    excludedAccountsAndActivities: float = 0.0
    fees: float = 0.0
    filteredValueInBaseCurrency: float = 0.0
    grossPerformance: float = 0.0
    grossPerformanceWithCurrencyEffect: float = 0.0
    interestInBaseCurrency: float = 0.0
    liabilitiesInBaseCurrency: float = 0.0
    netPerformance: float | None = None
    netPerformancePercentage: float | None = None
    netPerformancePercentageWithCurrencyEffect: float | None = None
    netPerformanceWithCurrencyEffect: float | None = None
    totalBuy: float = 0.0
    totalSell: float = 0.0
    totalInvestment: float = 0.0
    totalValueInBaseCurrency: float = 0.0
    activityCount: int = 0

    @property
    def annualizedPerformancePercentage(self) -> float | None:
        return self.annualizedPerformancePercent

    @property
    def currentNetWorth(self) -> float | None:
        return self.currentValueInBaseCurrency

    @property
    def currentValues(self) -> float:
        return self.currentValueInBaseCurrency or 0.0

    @property
    def itemCount(self) -> int:
        return self.activityCount

    @property
    def firstOrderDate(self) -> datetime | None:
        return self.dateOfFirstActivity

    @property
    def investment(self) -> float:
        return self.totalInvestment


class AllocationItem(BaseModel):
    name: str
    percentage: float
    position: float
    summary: float


class AnalysisResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    currency: str
    summary: PortfolioSummary
    holdings_raw: list[dict[str, Any]]
    activities_raw: list[dict[str, Any]]
    moneyWeightedReturn: dict
    timeWeightedReturn: dict
    allocationByAssetClass: list[AllocationItem]
    allocationByHoldings: list[AllocationItem]
    monthlyReturns: list[dict]
    drawdownData: list[dict]
    investmentsData: list[dict]
    summaryText: str
