from __future__ import annotations

from pathlib import Path

import pandas as pd

from etl.clients.health_ckan import HealthCkanClient


class MeteorologyCkanClient(HealthCkanClient):
    """
    Client dedicato ai dataset meteorologici
    pubblicati da ARPA Puglia tramite CKAN.
    """

    def download_datastore_resource(
        self,
        resource_id: str,
        destination: Path,
        *,
        page_size: int = 5000,
    ) -> Path:
        """
        Scarica tutti i record di una risorsa CKAN DataStore
        e li salva in formato Parquet.
        """

        if page_size <= 0:
            raise ValueError(
                "page_size deve essere maggiore di zero."
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        offset = 0
        total: int | None = None
        records: list[dict] = []

        while total is None or offset < total:
            result = self.get_datastore_records(
                resource_id,
                limit=page_size,
                offset=offset,
            )

            batch = result.get(
                "records",
                [],
            )

            if total is None:
                total = int(
                    result.get(
                        "total",
                        len(batch),
                    )
                )

                print(
                    f"Record totali dichiarati: {total}"
                )

            if not batch:
                break

            records.extend(batch)

            offset += len(batch)

            print(
                f"Scaricati {len(records)} / {total}"
            )

        if total is not None and len(records) != total:
            raise RuntimeError(
                "Download CKAN incompleto: "
                f"attesi {total} record, ottenuti {len(records)}."
            )

        frame = pd.DataFrame(records)

        frame.to_parquet(
            destination,
            index=False,
        )

        print(
            f"File RAW creato: {destination}"
        )

        return destination