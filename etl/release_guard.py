"""Prevent legacy ETL from overwriting the scientific release products."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'config/one_health/release_products.json'

def assert_legacy_output_writable(path):
    if not REGISTRY.is_file():return
    target=Path(path).resolve()
    try:relative=target.relative_to(ROOT).as_posix()
    except ValueError:return
    products=json.loads(REGISTRY.read_text()).get('products',{})
    if relative in products:
        raise PermissionError('Prodotto ricalcolato protetto: '+relative+'. Questa procedura precedente non può sovrascriverlo. Usare una cartella di lavoro diversa e verificare il nuovo prodotto prima della sostituzione.')
