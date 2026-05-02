"""Statsfolio Ghostfolio API client.

A lightweight Python client for the Ghostfolio REST API. Built from scratch
based on the Ghostfolio NestJS controller definitions.

Ghostfolio is licensed under Apache 2.0. This client is an independent
implementation that interacts with the Ghostfolio REST API.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from statsfolio.exceptions import GhostfolioError

logger = logging.getLogger(__name__)


class Client:
    """HTTP client for the Ghostfolio REST API.

    All portfolio endpoints use JWT authentication. The client exchanges an
    access token for a JWT on first use and refreshes it periodically.

    Parameters
    ----------
    access_token :
        The Ghostfolio user access token (created in Ghostfolio settings).
    host :
        Base URL of the Ghostfolio instance, e.g. ``https://ghostfol.io``.
    verify_ssl :
        Whether to verify TLS certificates (disable for local dev with
        self-signed certs).
    timeout :
        Request timeout in seconds.
    """

    # JWT is valid for 30 d; refresh proactively at 28 d.
    _JWT_REFRESH_DELTA = timedelta(days=28)

    def __init__(
        self,
        access_token: str,
        host: str = "https://ghostfol.io",
        *,
        verify_ssl: bool = True,
        timeout: float = 30,
    ) -> None:
        self.host = host.rstrip("/")
        self._access_token = access_token
        self._verify_ssl = verify_ssl
        self._timeout = timeout

        self._session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503])
        self._session.mount("https://", HTTPAdapter(max_retries=retries))

        self._jwt: str | None = None
        self._jwt_expires: datetime | None = None

    # ------------------------------------------------------------------ #
    #  Internals
    # ------------------------------------------------------------------ #

    def _endpoint(self, path: str, *, version: str = "v1") -> str:
        """Build a fully-qualified API URL."""
        return f"{self.host}/api/{version}/{path}"

    def _ensure_jwt(self) -> None:
        """Fetch a fresh JWT if the current one is expired or missing."""
        if self._jwt and self._jwt_expires and datetime.now(timezone.utc) < self._jwt_expires:
            return

        url = self._endpoint("auth/anonymous")
        resp = self._session.post(
            url,
            json={"accessToken": self._access_token},
            timeout=self._timeout,
            verify=self._verify_ssl,
        )
        if resp.status_code != 201 and resp.status_code != 200:
            raise GhostfolioError(
                f"Authentication failed (HTTP {resp.status_code})",
                status_code=resp.status_code,
                response=resp.text,
            )
        self._jwt = resp.json().get("authToken")
        self._jwt_expires = datetime.now(timezone.utc) + self._JWT_REFRESH_DELTA

    def _headers(self) -> dict[str, str]:
        self._ensure_jwt()
        return {"Authorization": f"Bearer {self._jwt}"}

    def _get(self, path: str, *, params: dict | None = None, version: str = "v1") -> dict:
        url = self._endpoint(path, version=version)
        resp = self._session.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=self._timeout,
            verify=self._verify_ssl,
        )
        self._raise(resp)
        return resp.json()

    def _post(
        self,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        version: str = "v1",
    ) -> dict:
        url = self._endpoint(path, version=version)
        resp = self._session.post(
            url,
            headers=self._headers(),
            json=json,
            params=params,
            timeout=self._timeout,
            verify=self._verify_ssl,
        )
        self._raise(resp)
        return resp.json()

    @staticmethod
    def _raise(resp: requests.Response) -> None:
        if resp.status_code >= 400:
            raise GhostfolioError(
                f"Request failed (HTTP {resp.status_code}): {resp.text[:200]}",
                status_code=resp.status_code,
                response=resp.text,
            )

    # ------------------------------------------------------------------ #
    #  Public API – portfolio read endpoints
    # ------------------------------------------------------------------ #

    def test_connection(self) -> dict[str, Any]:
        """Return a quick connectivity / auth check.

        Calls ``GET /portfolio/details`` and reports whether the token is
        valid and data is available.
        """
        result: dict[str, Any] = {"status": "ok", "host": self.host}
        try:
            data = self.portfolio_details()
            result["authenticated"] = True
            result["has_data"] = bool(data)
        except GhostfolioError as exc:
            result["status"] = "error"
            result["authenticated"] = False
            result["detail"] = str(exc)
        return result

    def portfolio_details(
        self,
        *,
        range: str = "max",
        accounts: str | None = None,
        asset_classes: str | None = None,
        data_source: str | None = None,
        symbol: str | None = None,
        tags: str | None = None,
        with_markets: bool = False,
    ) -> dict:
        """GET /api/v1/portfolio/details

        Full portfolio snapshot: accounts, holdings, markets, and summary
        metrics (net worth, invested, performance, etc.).
        """
        params: dict[str, Any] = {"range": range, "withMarkets": str(with_markets).lower()}
        if accounts:
            params["accounts"] = accounts
        if asset_classes:
            params["assetClasses"] = asset_classes
        if data_source:
            params["dataSource"] = data_source
        if symbol:
            params["symbol"] = symbol
        if tags:
            params["tags"] = tags
        return self._get("portfolio/details", params=params)

    def portfolio_holdings(
        self,
        *,
        range: str = "max",
        accounts: str | None = None,
        asset_classes: str | None = None,
        data_source: str | None = None,
        symbol: str | None = None,
        query: str | None = None,
        tags: str | None = None,
    ) -> dict:
        """GET /api/v1/portfolio/holdings

        Returns ``{ holdings: PortfolioPosition[] }`` with current positions,
        allocations, market prices, and performance figures.
        """
        params: dict[str, Any] = {"range": range}
        if accounts:
            params["accounts"] = accounts
        if asset_classes:
            params["assetClasses"] = asset_classes
        if data_source:
            params["dataSource"] = data_source
        if symbol:
            params["symbol"] = symbol
        if query:
            params["query"] = query
        if tags:
            params["tags"] = tags
        return self._get("portfolio/holdings", params=params)

    def portfolio_holding(self, data_source: str, symbol: str) -> dict:
        """GET /api/v1/portfolio/holding/:dataSource/:symbol

        Detailed info for a single holding.
        """
        return self._get(f"portfolio/holding/{data_source}/{symbol}")

    def portfolio_performance(
        self,
        *,
        range: str = "max",
        accounts: str | None = None,
        asset_classes: str | None = None,
        data_source: str | None = None,
        symbol: str | None = None,
        tags: str | None = None,
    ) -> dict:
        """GET /api/v2/portfolio/performance

        Chart data and performance summary (netPerformance,
        netPerformancePercentage, annualizedPerformancePercent, etc.).
        """
        params: dict[str, Any] = {"range": range}
        if accounts:
            params["accounts"] = accounts
        if asset_classes:
            params["assetClasses"] = asset_classes
        if data_source:
            params["dataSource"] = data_source
        if symbol:
            params["symbol"] = symbol
        if tags:
            params["tags"] = tags
        return self._get("portfolio/performance", params=params, version="v2")

    def portfolio_investments(
        self,
        *,
        range: str = "max",
        group_by: str = "month",
        accounts: str | None = None,
        asset_classes: str | None = None,
        data_source: str | None = None,
        symbol: str | None = None,
        tags: str | None = None,
    ) -> dict:
        """GET /api/v1/portfolio/investments

        Investment cash flows grouped by period.
        """
        params: dict[str, Any] = {"range": range, "groupBy": group_by}
        if accounts:
            params["accounts"] = accounts
        if asset_classes:
            params["assetClasses"] = asset_classes
        if data_source:
            params["dataSource"] = data_source
        if symbol:
            params["symbol"] = symbol
        if tags:
            params["tags"] = tags
        return self._get("portfolio/investments", params=params)

    def portfolio_dividends(
        self,
        *,
        range: str = "max",
        group_by: str = "month",
        accounts: str | None = None,
        asset_classes: str | None = None,
        data_source: str | None = None,
        symbol: str | None = None,
        tags: str | None = None,
    ) -> dict:
        """GET /api/v1/portfolio/dividends

        Dividend income grouped by period.
        """
        params: dict[str, Any] = {"range": range, "groupBy": group_by}
        if accounts:
            params["accounts"] = accounts
        if asset_classes:
            params["assetClasses"] = asset_classes
        if data_source:
            params["dataSource"] = data_source
        if symbol:
            params["symbol"] = symbol
        if tags:
            params["tags"] = tags
        return self._get("portfolio/dividends", params=params)

    # ------------------------------------------------------------------ #
    #  Activities (orders)
    # ------------------------------------------------------------------ #

    def activities(
        self,
        *,
        account_id: str | None = None,
        activity_types: str | None = None,
        asset_classes: str | None = None,
        data_source: str | None = None,
        range: str = "max",
        symbol: str | None = None,
        tags: str | None = None,
        skip: int = 0,
        take: int = 1000,
        sort_column: str | None = None,
        sort_direction: str | None = None,
    ) -> dict:
        """GET /api/v1/activities

        Returns ``{ activities: Activity[], count: int }``.
        Falls back to the legacy ``/order`` endpoint if the instance does
        not support ``/activities``.
        """
        params: dict[str, Any] = {"range": range, "skip": skip, "take": take}
        if account_id:
            params["accounts"] = account_id
        if activity_types:
            params["activityTypes"] = activity_types
        if asset_classes:
            params["assetClasses"] = asset_classes
        if data_source:
            params["dataSource"] = data_source
        if symbol:
            params["symbol"] = symbol
        if tags:
            params["tags"] = tags
        if sort_column:
            params["sortColumn"] = sort_column
        if sort_direction:
            params["sortDirection"] = sort_direction

        try:
            return self._get("activities", params=params)
        except GhostfolioError as exc:
            if exc.status_code == 404:
                logger.debug("activities endpoint not found, falling back to legacy /order")
                legacy_params: dict[str, Any] = {}
                if account_id:
                    legacy_params["accounts"] = account_id
                return self._get("order", params=legacy_params)
            raise

    # ------------------------------------------------------------------ #
    #  User
    # ------------------------------------------------------------------ #

    def user(self) -> dict:
        """GET /api/v1/user

        Returns the authenticated user profile including settings
        (baseCurrency, etc.).
        """
        return self._get("user")

    # ------------------------------------------------------------------ #
    #  Accounts
    # ------------------------------------------------------------------ #

    def accounts(self) -> dict:
        """GET /api/v1/account

        Returns ``{ accounts: AccountWithAggregations[] }``.
        """
        return self._get("account")

    # ------------------------------------------------------------------ #
    #  Symbol lookup
    # ------------------------------------------------------------------ #

    def symbol_lookup(
        self, query: str, *, include_indices: bool = False
    ) -> dict:
        """GET /api/v1/symbol/lookup

        Search for tradable symbols.
        """
        return self._get(
            "symbol/lookup",
            params={"query": query, "includeIndices": str(include_indices).lower()},
        )

    def symbol_info(
        self, data_source: str, symbol: str, *, include_historical: bool = False
    ) -> dict:
        """GET /api/v1/symbol/:dataSource/:symbol

        Asset profile and optional historical data.
        """
        return self._get(
            f"symbol/{data_source}/{symbol}",
            params={"includeHistoricalData": str(int(include_historical))},
        )

    # ------------------------------------------------------------------ #
    #  Import / export
    # ------------------------------------------------------------------ #

    def import_activities(
        self,
        activities: list[dict],
        *,
        accounts: list[dict] | None = None,
        asset_profiles: list[dict] | None = None,
        tags: list[dict] | None = None,
        dry_run: bool = False,
    ) -> dict:
        """POST /api/v1/import

        Bulk-import activities (orders).
        """
        payload: dict[str, Any] = {"activities": activities}
        if accounts:
            payload["accounts"] = accounts
        if asset_profiles:
            payload["assetProfiles"] = asset_profiles
        if tags:
            payload["tags"] = tags
        return self._post("import", json=payload, params={"dryRun": str(dry_run).lower()})

    def export(
        self,
        *,
        accounts: str | None = None,
        activity_ids: str | None = None,
        activity_types: str | None = None,
        asset_classes: str | None = None,
        data_source: str | None = None,
        symbol: str | None = None,
        tags: str | None = None,
    ) -> dict:
        """GET /api/v1/export

        Export portfolio data (activities, accounts, asset profiles, tags).
        """
        params: dict[str, Any] = {}
        if accounts:
            params["accounts"] = accounts
        if activity_ids:
            params["activityIds"] = activity_ids
        if activity_types:
            params["activityTypes"] = activity_types
        if asset_classes:
            params["assetClasses"] = asset_classes
        if data_source:
            params["dataSource"] = data_source
        if symbol:
            params["symbol"] = symbol
        if tags:
            params["tags"] = tags
        return self._get("export", params=params)

    # ------------------------------------------------------------------ #
    #  Admin market data
    # ------------------------------------------------------------------ #

    def admin_market_data(
        self,
        *,
        data_source: str | None = None,
        query: str | None = None,
        skip: int = 0,
        take: int = 100,
    ) -> dict:
        """GET /api/v1/admin/market-data

        Overview of loaded market data (admin-only).
        """
        params: dict[str, Any] = {"skip": skip, "take": take}
        if data_source:
            params["dataSource"] = data_source
        if query:
            params["query"] = query
        return self._get("admin/market-data", params=params)

    def admin_market_data_symbol(self, data_source: str, symbol: str) -> dict:
        """GET /api/v1/admin/market-data/:dataSource/:symbol

        Market data for a specific symbol (admin-only).
        """
        return self._get(f"admin/market-data/{data_source}/{symbol}")

    # ------------------------------------------------------------------ #
    #  Health & info
    # ------------------------------------------------------------------ #

    def health(self) -> dict:
        """GET /api/v1/health

        Service health check (no auth required).
        """
        url = self._endpoint("health")
        resp = self._session.get(url, timeout=self._timeout, verify=self._verify_ssl)
        return resp.json()

    def info(self) -> dict:
        """GET /api/v1/info

        System information: available data providers, benchmarks, etc.
        """
        url = self._endpoint("info")
        resp = self._session.get(url, timeout=self._timeout, verify=self._verify_ssl)
        return resp.json()

    # ------------------------------------------------------------------ #
    #  Convenience (backward compat)
    # ------------------------------------------------------------------ #

    def orders(self, account_id: str | None = None) -> dict:
        """Alias for :meth:`activities` (legacy name)."""
        return self.activities(account_id=account_id)

    def performance(self, date_range: str = "max") -> dict:
        """Alias for :meth:`portfolio_performance`."""
        return self.portfolio_performance(range=date_range)

    def holdings(self, date_range: str = "max") -> dict:
        """Alias for :meth:`portfolio_holdings`."""
        return self.portfolio_holdings(range=date_range)

    def details(self) -> dict:
        """Alias for :meth:`portfolio_details`."""
        return self.portfolio_details()

    def investments(self, group_by: str = "month", date_range: str = "max") -> dict:
        """Alias for :meth:`portfolio_investments`."""
        return self.portfolio_investments(range=date_range, group_by=group_by)

    def dividends(self, group_by: str = "month", date_range: str = "max") -> dict:
        """Alias for :meth:`portfolio_dividends`."""
        return self.portfolio_dividends(range=date_range, group_by=group_by)

    def market_data(self, data_source: str, symbol: str) -> dict:
        """Alias for :meth:`admin_market_data_symbol`."""
        return self.admin_market_data_symbol(data_source, symbol)

    def market_data_admin(self) -> dict:
        """Alias for :meth:`admin_market_data`."""
        return self.admin_market_data()

    def user_settings(self) -> dict:
        """Alias for :meth:`user`."""
        return self.user()

    def import_transactions(self, data: dict) -> dict:
        """Alias for :meth:`import_activities`."""
        return self.import_activities(**data)

    def __repr__(self) -> str:
        return f"Client(host={self.host!r})"
