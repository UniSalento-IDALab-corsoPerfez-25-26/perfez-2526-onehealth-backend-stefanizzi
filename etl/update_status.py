"""Record the actual daily acquisition outcome without storing credentials."""
from pathlib import Path
from datetime import datetime,timezone
import json
ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/'data/processed/one_health/operational/daily_update_status.json'

def record_update(status,stage,measurement_date=None):
    try:data=json.loads(PATH.read_text())
    except (OSError,ValueError):data={}
    now=datetime.now(timezone.utc).isoformat()
    if status=='RUNNING':data['last_attempt_utc']=now
    data.update(status=status,stage=stage,recorded_at_utc=now)
    if status=='OK':data['last_success_utc']=now
    if measurement_date is not None:data['measurement_date']=str(measurement_date)
    PATH.parent.mkdir(parents=True,exist_ok=True)
    temporary=PATH.with_suffix('.tmp');temporary.write_text(json.dumps(data,indent=2));temporary.replace(PATH)
