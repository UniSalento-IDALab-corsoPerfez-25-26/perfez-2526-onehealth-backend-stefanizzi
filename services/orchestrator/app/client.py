from typing import Any

import httpx


class ServiceCallError(RuntimeError):
    """
    Raised when a downstream service cannot complete
    an orchestrated operation successfully.
    """

    def __init__(
        self,
        *,
        service: str,
        method: str,
        url: str,
        status_code: int | None,
        detail: str,
    ):
        self.service = service
        self.method = method
        self.url = url
        self.status_code = status_code
        self.detail = detail

        super().__init__(
            f"{service} call failed: "
            f"{method} {url} - {detail}"
        )


class OrchestratorClient:
    """
    HTTP client used by the application orchestrator.

    The orchestrator communicates only through public
    service APIs and does not directly invoke ETL code.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 300.0,
    ):
        self.timeout_seconds = timeout_seconds

    async def request(
        self,
        *,
        service: str,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds
            ) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                )

        except httpx.RequestError as exc:
            raise ServiceCallError(
                service=service,
                method=method,
                url=url,
                status_code=None,
                detail=str(exc),
            ) from exc

        if response.status_code >= 400:
            raise ServiceCallError(
                service=service,
                method=method,
                url=url,
                status_code=response.status_code,
                detail=response.text,
            )

        try:
            payload = response.json()

        except ValueError as exc:
            raise ServiceCallError(
                service=service,
                method=method,
                url=url,
                status_code=response.status_code,
                detail=(
                    "Downstream service returned "
                    "invalid JSON."
                ),
            ) from exc

        if not isinstance(payload, dict):
            raise ServiceCallError(
                service=service,
                method=method,
                url=url,
                status_code=response.status_code,
                detail=(
                    "Downstream service response "
                    "is not a JSON object."
                ),
            )

        return payload