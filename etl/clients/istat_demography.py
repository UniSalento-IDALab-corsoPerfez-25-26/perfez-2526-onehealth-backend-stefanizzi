from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile

import requests


class IstatDemographyClient:
    """
    Client per il download dei dati POSAS ISTAT:

    Popolazione residente per età, sesso e stato civile
    al 1° gennaio.

    I file vengono scaricati per provincia e annualità.
    """

    BASE_URL = "https://demo.istat.it/data/posas"

    PUGLIA_PROVINCES = {
        "071": "Foggia",
        "072": "Bari",
        "073": "Taranto",
        "074": "Brindisi",
        "075": "Lecce",
        "110": "Barletta-Andria-Trani",
    }

    def __init__(
        self,
        *,
        timeout: int = 60,
    ) -> None:
        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "one-health-puglia/1.0 "
                    "(academic research project)"
                )
            }
        )

    def build_filename(
        self,
        *,
        year: int,
        province_code: str,
        province_name: str,
    ) -> str:
        """
        Costruisce il nome ufficiale dello ZIP ISTAT.
        """

        return (
            f"POSAS_{year}_it_"
            f"{province_code}_{province_name}.zip"
        )

    def build_url(
        self,
        *,
        year: int,
        province_code: str,
        province_name: str,
    ) -> str:
        """
        Costruisce l'URL ufficiale dello ZIP.
        """

        filename = self.build_filename(
            year=year,
            province_code=province_code,
            province_name=province_name,
        )

        return f"{self.BASE_URL}/{filename}"

    def download_file(
        self,
        *,
        url: str,
        destination: Path,
        overwrite: bool = False,
    ) -> Path:
        """
        Scarica un singolo file ZIP.

        Se il file esiste già e overwrite=False,
        non viene riscaricato.
        """

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if destination.exists() and not overwrite:
            if destination.stat().st_size > 0:
                print(
                    f"Già presente: {destination.name}"
                )
                return destination

        print(f"Download: {url}")

        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                stream=True,
            )

            response.raise_for_status()

        except requests.RequestException as exc:
            raise RuntimeError(
                f"Errore durante il download di {url}: {exc}"
            ) from exc

        content_type = (
            response.headers
            .get("Content-Type", "")
            .lower()
        )

        # Alcuni server possono restituire una pagina HTML
        # con status 200 quando il file non esiste.
        if "text/html" in content_type:
            raise RuntimeError(
                "ISTAT ha restituito una pagina HTML "
                f"invece dello ZIP richiesto: {url}"
            )

        temporary_path = destination.with_suffix(
            destination.suffix + ".part"
        )

        try:
            with temporary_path.open("wb") as output_file:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        output_file.write(chunk)

            if temporary_path.stat().st_size == 0:
                raise RuntimeError(
                    f"File scaricato vuoto: {url}"
                )

            temporary_path.replace(destination)

        except Exception:
            temporary_path.unlink(
                missing_ok=True
            )
            raise

        self.validate_zip(destination)

        print(
            f"Salvato: {destination} "
            f"({destination.stat().st_size:,} byte)"
        )

        return destination

    @staticmethod
    def validate_zip(
        zip_path: Path,
    ) -> None:
        """
        Verifica che il file sia realmente uno ZIP valido.
        """

        if not zip_path.exists():
            raise FileNotFoundError(
                f"ZIP non trovato: {zip_path}"
            )

        try:
            with ZipFile(zip_path) as archive:
                corrupted_file = archive.testzip()

                if corrupted_file is not None:
                    raise RuntimeError(
                        "File corrotto nello ZIP "
                        f"{zip_path.name}: {corrupted_file}"
                    )

        except BadZipFile as exc:
            zip_path.unlink(
                missing_ok=True
            )

            raise RuntimeError(
                f"Il file non è uno ZIP valido: {zip_path}"
            ) from exc

    def download_puglia(
        self,
        *,
        year: int,
        output_dir: Path,
        overwrite: bool = False,
    ) -> list[Path]:
        """
        Scarica i sei ZIP provinciali della Puglia
        per una determinata annualità.
        """

        zip_paths: list[Path] = []
        errors: list[str] = []

        for province_code, province_name in (
            self.PUGLIA_PROVINCES.items()
        ):
            filename = self.build_filename(
                year=year,
                province_code=province_code,
                province_name=province_name,
            )

            url = self.build_url(
                year=year,
                province_code=province_code,
                province_name=province_name,
            )

            destination = output_dir / filename

            try:
                downloaded_path = self.download_file(
                    url=url,
                    destination=destination,
                    overwrite=overwrite,
                )

                zip_paths.append(
                    downloaded_path
                )

            except Exception as exc:
                errors.append(
                    f"{province_code} {province_name}: {exc}"
                )

        if errors:
            formatted_errors = "\n".join(
                f" - {error}"
                for error in errors
            )

            raise RuntimeError(
                f"Download ISTAT {year} incompleto:\n"
                f"{formatted_errors}"
            )

        if len(zip_paths) != 6:
            raise RuntimeError(
                f"Attesi 6 ZIP per il {year}, "
                f"scaricati {len(zip_paths)}."
            )

        return zip_paths

    @staticmethod
    def extract_zip(
        zip_path: Path,
        output_dir: Path,
        *,
        overwrite: bool = False,
    ) -> list[Path]:
        """
        Estrae un archivio ZIP e restituisce
        i percorsi dei file estratti.
        """

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            with ZipFile(zip_path) as archive:
                extracted_paths: list[Path] = []

                for member in archive.infolist():
                    if member.is_dir():
                        continue

                    filename = Path(
                        member.filename
                    ).name

                    if not filename:
                        continue

                    destination = (
                        output_dir / filename
                    )

                    if (
                        destination.exists()
                        and not overwrite
                    ):
                        extracted_paths.append(
                            destination
                        )
                        continue

                    with archive.open(member) as source:
                        with destination.open("wb") as target:
                            while True:
                                chunk = source.read(
                                    1024 * 1024
                                )

                                if not chunk:
                                    break

                                target.write(chunk)

                    extracted_paths.append(
                        destination
                    )

        except BadZipFile as exc:
            raise RuntimeError(
                f"Archivio ZIP non valido: {zip_path}"
            ) from exc

        return extracted_paths

    def download_and_extract_puglia(
        self,
        *,
        year: int,
        raw_root: Path,
        overwrite: bool = False,
    ) -> list[Path]:
        """
        Scarica ed estrae tutte le province pugliesi
        per una determinata annualità.

        Struttura prodotta:

        data/raw/demography/<anno>/
            *.zip
            extracted/
                *.csv
        """

        year_dir = raw_root / str(year)
        extracted_dir = year_dir / "extracted"

        zip_paths = self.download_puglia(
            year=year,
            output_dir=year_dir,
            overwrite=overwrite,
        )

        csv_paths: list[Path] = []

        for zip_path in zip_paths:
            extracted_paths = self.extract_zip(
                zip_path,
                extracted_dir,
                overwrite=overwrite,
            )

            csv_paths.extend(
                path
                for path in extracted_paths
                if path.suffix.lower() == ".csv"
            )

        # Elimina eventuali duplicati mantenendo
        # un ordinamento stabile.
        csv_paths = sorted(
            set(csv_paths)
        )

        if len(csv_paths) != 6:
            filenames = [
                path.name
                for path in csv_paths
            ]

            raise RuntimeError(
                f"Attesi 6 CSV ISTAT per il {year}, "
                f"trovati {len(csv_paths)}: {filenames}"
            )

        return csv_paths