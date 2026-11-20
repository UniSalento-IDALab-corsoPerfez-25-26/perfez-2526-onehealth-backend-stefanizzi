"""Esporta i sorgenti condivisibili, senza dati, credenziali o backup."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[2]
FOLDERS={'app','etl','services','shared','research','scripts','tests','gateway','config','docs'}
SUFFIXES={'.py','.md','.txt','.toml','.yaml','.yml','.ini','.cfg','.sql','.json','.csv','.sh','.ps1','.bat'}
ROOT_NAMES={'Dockerfile','Makefile','pyproject.toml','docker-compose.yml','compose.yml','.gitignore','.dockerignore'}
FORBIDDEN={'__pycache__','backup_dashboard','backup_codice','.git','.venv','venv','env','node_modules'}
def allowed(rel):
 if any(p in FORBIDDEN or p.startswith('.') for p in rel.parts):
  return len(rel.parts)==1 and rel.name in {'.gitignore','.dockerignore','.env.example'}
 if any(s in rel.name.lower() for s in ['secret','credential','password','private_key','access_token']):return False
 if rel.suffix.lower() in {'.pem','.key','.p12','.pfx','.pyc','.pyo','.sqlite','.db'}:return False
 if len(rel.parts)==1:return rel.name in ROOT_NAMES or (rel.name.lower().startswith(('readme','requirements','condivisione')) and rel.suffix in SUFFIXES) or rel.name=='verifica_codice_onehealth.py'
 return rel.parts[0] in FOLDERS and (rel.suffix in SUFFIXES or rel.name=='Dockerfile')
def export(project,destination):
 project=project.resolve();destination=destination.resolve()
 if destination.exists():raise FileExistsError('Archivio già esistente: scegliere un nuovo nome.')
 if not (project/'app/dashboard/main.py').is_file():raise ValueError('Radice del progetto non riconosciuta.')
 files=[p for p in project.rglob('*') if p.is_file() and not p.is_symlink() and allowed(p.relative_to(project))]
 destination.parent.mkdir(parents=True,exist_ok=True)
 manifest={}
 with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
  for p in sorted(files):
   rel=p.relative_to(project);data=p.read_bytes();archive.writestr(str(Path('one-health-puglia')/rel),data);manifest[str(rel)]=hashlib.sha256(data).hexdigest()
  archive.writestr('one-health-puglia/SHARED_CODE_MANIFEST.json',json.dumps(manifest,indent=2))
 print('Archivio creato:',destination,'| File di codice/configurazione/documentazione:',len(files))
 print('Dati e risultati non sono inclusi. Gli script che li richiedono ne indicano gli input. Controllare eventuali informazioni riservate inserite manualmente nei sorgenti prima della distribuzione.')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,default=ROOT);p.add_argument('--output',type=Path,required=True);a=p.parse_args();export(a.project,a.output)
if __name__=='__main__':main()
