from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from etl.config import settings
from etl.models.arpa import ArpaMeasurementQuery, IngestionMode


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    url: str
    sha256: str
    size_bytes: int
    content_type: str | None


class ArpaApiError(RuntimeError):
    pass


class ArpaAirQualityClient:
    def __init__(self) -> None:
        self.base_url = settings.arpa_base_url.rstrip("/")
        self.timeout = settings.arpa_timeout_seconds
        self.max_retries = settings.arpa_max_retries

    def _get(self, url: str, params: dict[str, object] | None = None) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                    response = client.get(url, params=params)
                    response.raise_for_status()
                    return response
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(2 ** (attempt - 1))
        raise ArpaApiError(f"Richiesta ARPA fallita dopo {self.max_retries} tentativi") from last_error

    @staticmethod
    def _save_response(response: httpx.Response, destination: Path) -> DownloadResult:
        destination.parent.mkdir(parents=True, exist_ok=True)
        content = response.content
        destination.write_bytes(content)
        return DownloadResult(
            path=destination,
            url=str(response.url),
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            content_type=response.headers.get("content-type"),
        )

    def download_stations(self, destination: Path) -> DownloadResult:
        response = self._get(f"{self.base_url}/Stations")
        return self._save_response(response, destination)

    def download_pollutants(self, destination: Path) -> DownloadResult:
        response = self._get(f"{self.base_url}/Pollutants")
        return self._save_response(response, destination)

    def download_measurements(self, query: ArpaMeasurementQuery) -> DownloadResult:
        suffix = "geojson" if query.output_format.value == "GeoJSON" else "csv"
        if query.mode == IngestionMode.DAILY:
            filename = f"measurements_{query.network.lower()}_daily.{suffix}"
            folder = settings.arpa_raw_dir / "daily"
        else:
            period = f"{query.year:04d}" + (f"_{query.month:02d}" if query.month else "")
            pollutant = f"_{query.pollutant_label.lower()}" if query.pollutant_label else ""
            filename = f"measurements_{query.network.lower()}_{period}{pollutant}.{suffix}"
            folder = settings.arpa_raw_dir / "historical"

        response = self._get(self.base_url, params=query.to_params())
        return self._save_response(response, folder / filename)
