from __future__ import annotations

from typing import Any

from statsfolio import Client as _Client

from app.config import settings


class GhostfolioClient:
    """Thin wrapper around the Statsfolio Ghostfolio API client."""

    def __init__(
        self,
        token: str | None = None,
        host: str | None = None,
    ) -> None:
        self._client = _Client(
            access_token=token or settings.GHOSTFOLIO_TOKEN,
            host=host or settings.GHOSTFOLIO_HOST,
        )

    # -- pass-through (match existing call sites) --

    def orders(self, account_id: str | None = None) -> dict:
        return self._client.orders(account_id=account_id)

    def performance(self, date_range: str = "max") -> dict:
        return self._client.performance(date_range=date_range)

    def holdings(self, date_range: str = "max") -> dict:
        return self._client.holdings(date_range=date_range)

    def holding(self, data_source: str, symbol: str) -> dict:
        return self._client.portfolio_holding(data_source, symbol)

    def details(self) -> dict:
        return self._client.details()

    def investments(self, group_by: str = "month", date_range: str = "max") -> dict:
        return self._client.investments(group_by=group_by, date_range=date_range)

    def dividends(self, group_by: str = "month", date_range: str = "max") -> dict:
        return self._client.dividends(group_by=group_by, date_range=date_range)

    def accounts(self) -> dict:
        return self._client.accounts()

    def market_data(self, data_source: str, symbol: str) -> dict:
        return self._client.market_data(data_source, symbol)

    def market_data_admin(self) -> dict:
        return self._client.market_data_admin()

    def user_settings(self) -> dict:
        return self._client.user_settings()

    def import_transactions(self, data: dict[str, Any]) -> dict:
        return self._client.import_transactions(data)

    def test_connection(self) -> dict:
        return self._client.test_connection()
