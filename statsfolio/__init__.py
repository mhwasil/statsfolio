"""Statsfolio Ghostfolio API client.

A lightweight Python client for the Ghostfolio REST API. Built from scratch
based on the Ghostfolio NestJS controller definitions.

Ghostfolio is licensed under Apache 2.0. This client is an independent
implementation that interacts with the Ghostfolio REST API.
"""

from statsfolio.exceptions import GhostfolioError
from statsfolio.ghostfolio_client import Client

__all__ = ["Client", "GhostfolioError"]
