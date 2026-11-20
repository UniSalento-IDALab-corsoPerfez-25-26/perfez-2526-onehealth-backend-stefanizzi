from pathlib import Path

import requests


CKAN_BASE_URL = "https://dati.puglia.it/ckan/api/3/action"


class HealthCkanClient:
    """
    Client per i dataset sanitari pubblicati
    sul catalogo Open Data Regione Puglia.
    """

    def __init__(self, timeout: int = 60):
        self.timeout = timeout

    def _get(
        self,
        action: str,
        params=None,
    ) -> dict:
        url = f"{CKAN_BASE_URL}/{action}"

        response = requests.get(
            url,
            params=params,
            timeout=self.timeout,
        )

        response.raise_for_status()

        payload = response.json()

        if not payload.get("success"):
            raise RuntimeError(
                f"CKAN action {action} fallita."
            )

        return payload["result"]

    def search_datasets(
        self,
        query: str,
        rows: int = 20,
    ) -> list[dict]:
        result = self._get(
            "package_search",
            {
                "q": query,
                "rows": rows,
            },
        )

        return result["results"]

    def get_dataset(
        self,
        dataset_id: str,
    ) -> dict:
        return self._get(
            "package_show",
            {
                "id": dataset_id,
            },
        )

    def download_resource(
        self,
        url: str,
        destination: Path,
    ) -> Path:
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        response = requests.get(
            url,
            timeout=self.timeout,
        )

        response.raise_for_status()

        destination.write_bytes(
            response.content
        )

        return destination

    def download_dataset_resource(
        self,
        dataset_id: str,
        destination: Path,
        resource_format: str = "CSV",
    ) -> Path:
        """
        Scarica l'unica risorsa del formato richiesto
        associata a un dataset CKAN.
        """

        dataset = self.get_dataset(dataset_id)

        resources = dataset.get(
            "resources",
            [],
        )

        matching = [
            resource
            for resource in resources
            if (
                resource.get("format", "").upper()
                == resource_format.upper()
            )
        ]

        if not matching:
            raise ValueError(
                f"Nessuna risorsa {resource_format} "
                f"trovata per {dataset_id}."
            )

        if len(matching) > 1:
            raise ValueError(
                f"Trovate {len(matching)} risorse "
                f"{resource_format} per {dataset_id}. "
                "Specificare la risorsa esplicitamente."
            )

        resource = matching[0]

        return self.download_resource(
            resource["url"],
            destination,
        )

    def get_datastore_records(
        self,
        resource_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """
        Legge i record di una risorsa CKAN
        con DataStore attivo.
        """

        return self._get(
            "datastore_search",
            {
                "resource_id": resource_id,
                "limit": limit,
                "offset": offset,
            },
        )


    def get_datastore_schema(
        self,
        resource_id: str,
    ) -> list[dict]:
        """
        Restituisce lo schema delle colonne
        di una risorsa CKAN DataStore.
        """

        result = self.get_datastore_records(
            resource_id,
            limit=1,
        )

        return result.get(
            "fields",
            [],
        )
        def get_datastore_records(
            self,
            resource_id: str,
            *,
            limit: int = 100,
            offset: int = 0,
        ) -> dict:
            """
            Legge i record di una risorsa CKAN
            con DataStore attivo.
            """

        return self._get(
            "datastore_search",
            {
                "resource_id": resource_id,
                "limit": limit,
                "offset": offset,
            },
        )

    def get_datastore_schema(
        self,
        resource_id: str,
    ) -> list[dict]:
        """
        Restituisce lo schema delle colonne
        di una risorsa CKAN DataStore.
        """

        result = self.get_datastore_records(
            resource_id,
            limit=1,
        )

        return result.get(
            "fields",
            [],
        )