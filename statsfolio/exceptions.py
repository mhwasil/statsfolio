"""Custom exceptions for the Statsfolio Ghostfolio API client."""


class GhostfolioError(Exception):
    """Raised when a Ghostfolio API call fails.

    Attributes
    ----------
    status_code :
        HTTP status code from the response, or ``None`` for auth failures.
    response :
        Raw response body text.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response
