"""Start, check or stop the existing local dashboard stack without deleting data."""
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit
from urllib.request import urlopen
from urllib.error import URLError,HTTPError
import argparse,json,os,signal,subprocess,sys,time,re,hashlib
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'.onehealth_runtime'
SERVICES={'environment-service':8001,'meteorology-service':8004,'analytics-service':8006,'ai-service':8007}

def command(args,env=None,timeout=30):
    result=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,text=True,timeout=timeout)
    if result.returncode:
        safe=re.sub(r'postgresql[^\s\"\']*://[^\s]+','<database>',result.stderr)
        raise RuntimeError(safe[-2500:] or 'Comando fallito: '+args[0])
    return result.stdout

def request(port,path='/health'):
    try:
        with urlopen(f'http://127.0.0.1:{port}{path}',timeout=4) as response:
            raw=response.read()
        try:return json.loads(raw)
        except ValueError:return raw.decode().strip()
    except (URLError,TimeoutError,OSError):return None

def wait(port,path='/health',seconds=45):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if request(port,path) is not None:return
        time.sleep(1)
    raise RuntimeError(f'Il servizio sulla porta {port} non risponde. Controlla i log prima di riprovare.')

def read_env():
    values=dict(os.environ)
    path=ROOT/'.env'
    if path.is_file():
        from dotenv import dotenv_values
        for key,value in dotenv_values(path).items():
            if value is not None:values.setdefault(key,value)
    return values

def database_env(values,host):
    url=values.get('DATABASE_URL') or values.get('ONEHEALTH_DATABASE_URL')
    if not url:raise RuntimeError('Impostare DATABASE_URL o ONEHEALTH_DATABASE_URL nel file .env.')
    p=urlsplit(url)
    if p.hostname in ('localhost','127.0.0.1','onehealth-db','host.docker.internal'):
        authority=p.netloc.rsplit('@',1)
        address=host+(f':{p.port}' if p.port else '')
        netloc=(authority[0]+'@' if len(authority)==2 else '')+address
        url=urlunsplit((p.scheme,netloc,p.path,p.query,p.fragment))
    return url

def spawn(name,args,env):
    logfile=RUN/(name+'.log')
    with logfile.open('ab') as out:
        process=subprocess.Popen(args,cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
    state=json.loads((RUN/'processes.json').read_text()) if (RUN/'processes.json').is_file() else {}
    state[name]={'pid':process.pid,'log':str(logfile),'started':command(['ps','-p',str(process.pid),'-o','lstart=']).strip()}
    (RUN/'processes.json').write_text(json.dumps(state,indent=2))
    print(f'Avviato {name}; log: {logfile}')

def start():
    RUN.mkdir(exist_ok=True)
    values=read_env()
    print('Verifica Docker...')
    command(['docker','info','--format','{{.ServerVersion}}'],timeout=15)
    command(['docker','start','onehealth-db'])
    ready=False
    for _ in range(30):
        try:command(['docker','exec','onehealth-db','pg_isready'],timeout=5);ready=True;break
        except RuntimeError:time.sleep(1)
    if not ready:raise RuntimeError('PostgreSQL non è pronto: controlla docker logs onehealth-db.')
    docker_env=dict(values);docker_env['ONEHEALTH_DATABASE_URL']=database_env(values,'host.docker.internal')
    print('Avvio dei servizi Docker; la prima compilazione può richiedere alcuni minuti.')
    with (RUN/'docker_build.log').open('w') as log:
        result=subprocess.run(['docker','compose','up','-d','--build',*SERVICES],cwd=ROOT,env=docker_env,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError('Avvio Docker fallito. Controlla .onehealth_runtime/docker_build.log.')
    for name,port in SERVICES.items():wait(port);print(name,'pronto')
    local=dict(values);local['DATABASE_URL']=database_env(values,'127.0.0.1')
    local['PYTHONPATH']=str(ROOT)+os.pathsep+local.get('PYTHONPATH','')
    if request(8000) is None:
        spawn('fastapi',[sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000'],local)
    wait(8000)
    if request(8501,'/_stcore/health') is None:
        spawn('streamlit',[sys.executable,'-m','streamlit','run','app/dashboard/main.py','--server.port','8501','--server.address','127.0.0.1'],local)
    wait(8501,'/_stcore/health')
    check()
    print('Dashboard: http://127.0.0.1:8501')

def check():
    failures=[]
    for name,port in {'FastAPI':8000,**SERVICES}.items():
        good=request(port) is not None;print(name,'OK' if good else 'NON RAGGIUNGIBILE')
        if not good:failures.append(name)
    probes=[(8000,'/measurements/latest?limit=1'),(8001,'/v1/operational-measurements-enriched?limit=1&province=Lecce'),
            (8007,'/v1/dss/scenarios?indicator_code=BPCO&year=2024'),(8000,'/research/environment-history')]
    for port,path in probes:
        data=request(port,path);good=data is not None
        print(f'Porta {port} {path}:', 'OK' if good else 'ERRORE')
        if port==8000 and 'latest' in path and isinstance(data,dict):print('Ultima misura nel database:',data.get('date'))
        if not good:failures.append(path)
    good=request(8501,'/_stcore/health') is not None;print('Streamlit','OK' if good else 'NON RAGGIUNGIBILE')
    if not good:failures.append('Streamlit')
    registry=ROOT/'config/one_health/release_products.json'
    if registry.is_file():
        products=json.loads(registry.read_text()).get('products',{})
        damaged=[]
        for relative,digest in products.items():
            path=ROOT/relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:damaged.append(relative)
        print('Prodotti ricalcolati:', 'OK' if not damaged else 'DIVERSI DALLA VERSIONE CONSEGNATA')
        if damaged:
            print('\n'.join(damaged));failures.append('Prodotti dati modificati o assenti')
    if failures:raise RuntimeError('Verifica incompleta. Vedere i servizi o le operazioni indicati come errore.')

def update():
    values=read_env(); values['DATABASE_URL']=database_env(values,'127.0.0.1')
    print(command([sys.executable,'-m','etl.cli','daily-pipeline','--network','RRQA'],env=values,timeout=600))
    print('Ricarica la dashboard dopo la scadenza della cache (massimo cinque minuti).')

def stop():
    path=RUN/'processes.json'
    if not path.is_file():print('Nessun processo locale registrato.');return
    for name,item in json.loads(path.read_text()).items():
        try:
            args=command(['ps','-p',str(item['pid']),'-o','command='])
            # Do not stop an unrelated process if a PID has been reused.
            marker='uvicorn app.main:app' if name=='fastapi' else 'streamlit run app/dashboard/main.py'
            started=command(['ps','-p',str(item['pid']),'-o','lstart=']).strip()
            if marker in args and item.get('started')==started:os.kill(item['pid'],signal.SIGTERM);print('Arrestato',name)
        except (RuntimeError,ProcessLookupError):pass
    path.unlink()
    print('PostgreSQL e container restano attivi. I processi avviati manualmente non vengono arrestati.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['start','check','stop','update']);args=p.parse_args()
    try:{'start':start,'check':check,'stop':stop,'update':update}[args.action]()
    except (RuntimeError,subprocess.TimeoutExpired,ImportError) as exc:
        print('ERRORE:',exc,file=sys.stderr);sys.exit(1)
