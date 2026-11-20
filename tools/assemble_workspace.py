"""Assembla una copia di esecuzione dei tre componenti OneHealthAI."""
from pathlib import Path
import argparse,hashlib,json,shutil

NAMES={role:f'perfez-2526-onehealth-{role}-stefanizzi' for role in ['backend','frontend','data-research']}

def assemble(repositories,destination,allow_modified=False):
    repositories=repositories.expanduser().resolve();destination=destination.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('La destinazione deve essere nuova o vuota. La cartella di lavoro originale non viene aggiornata.')
    plan={};sources={};requirements=[]
    for role,name in NAMES.items():
        repo=repositories/name
        if destination==repo or destination.is_relative_to(repo):
            raise ValueError('La copia di esecuzione deve essere esterna ai repository.')
        manifest=repo/'REPOSITORY_MANIFEST.json'
        if not manifest.is_file():raise FileNotFoundError(f'Manca {manifest}. Clonare tutti e tre i componenti.')
        data=json.loads(manifest.read_text());sources[role]=data['source_snapshot']
        for item in data['runtime_files']:
            rel=Path(item['path']);src=repo/rel
            if rel.is_absolute() or '..' in rel.parts or src.is_symlink() or not src.resolve().is_relative_to(repo.resolve()):
                raise ValueError('Percorso non valido nel manifest: '+str(rel))
            if not src.is_file():raise FileNotFoundError(src)
            digest=hashlib.sha256(src.read_bytes()).hexdigest()
            if digest!=item['sha256'] and not allow_modified:
                raise ValueError(f'File modificato rispetto alla consegna: {src}. Aggiornare il manifest oppure usare --allow-modified consapevolmente.')
            if str(rel) in plan:raise ValueError('Percorso assegnato a due componenti: '+str(rel))
            plan[str(rel)]=src
        for line in (repo/'requirements.txt').read_text().splitlines():
            line=line.strip()
            if line and not line.startswith('#') and line not in requirements:requirements.append(line)
    # Finish all checks before creating the workspace.
    destination.mkdir(parents=True,exist_ok=True)
    for rel,src in plan.items():
        target=destination/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
    (destination/'requirements.txt').write_text('\n'.join(requirements)+'\n')
    shutil.copy2(repositories/NAMES['backend']/'.env.example',destination/'.env.example')
    (destination/'ASSEMBLED_COMPONENTS.json').write_text(json.dumps({'sources':sources,'files':len(plan),'note':'Copia generata; modificare i sorgenti nei rispettivi repository.'},indent=2))
    (destination/'README_WORKSPACE.md').write_text('''# OneHealthAI copia di esecuzione

Questa cartella riunisce i sorgenti dei tre repository mantenendo i percorsi originali. Non contiene dati, risultati o credenziali e non è un ulteriore repository da pubblicare. Modificare il codice nei repository di origine e creare una nuova copia per le prove successive.

1. Installare le dipendenze in un ambiente dedicato: `python -m pip install -r requirements.txt`.
2. Configurare `.env` a partire dai segnaposto di `.env.example`.
3. Predisporre PostgreSQL/PostGIS, tabelle e prodotti dati richiesti dalle viste. I dati e i risultati devono essere ottenuti separatamente e collocati in `data/` e `reports/`, rispettando i percorsi indicati nei cataloghi e nei protocolli.
4. Eseguire dalla radice di questa cartella `python scripts/maintenance/onehealth_runtime.py check` per verificare i prerequisiti. Il launcher `start` richiede Docker e il database configurato; non crea automaticamente un database mancante.
5. Per l’avvio manuale locale dell’API: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Per la dashboard: `python -m streamlit run app/dashboard/main.py` in un altro terminale. Le viste delle priorità e quelle ambientali richiedono anche i servizi indicati nel Compose.

L’assemblaggio non esegue questi passaggi, non avvia servizi e non ricalcola le analisi. Usare una sola installazione per volta sulle porte predefinite, evitando conflitti con l’installazione di lavoro già avviata.
''')
    print(f'Copia di esecuzione creata: {destination} ({len(plan)} sorgenti/configurazioni). Nessun dato, risultato o .env copiato; nessun servizio avviato.')
    return len(plan)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repositories-dir',type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--allow-modified',action='store_true')
    args=p.parse_args()
    try:assemble(args.repositories_dir,args.output,args.allow_modified)
    except (ValueError,OSError,KeyError) as exc:p.exit(2,str(exc)+'\n')

if __name__=='__main__':main()
