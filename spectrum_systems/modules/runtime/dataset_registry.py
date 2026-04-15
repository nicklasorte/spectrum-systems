"""DAT dataset registry helpers."""
from __future__ import annotations

def validate_dataset_registration(*, dataset_record: dict, required_freshness_days: int = 30) -> tuple[bool, list[str]]:
    reasons=[]
    if not dataset_record.get('dataset_id'): reasons.append('missing_dataset_id')
    if not dataset_record.get('lineage_ref'): reasons.append('missing_lineage_ref')
    if int(dataset_record.get('age_days', 0)) > required_freshness_days: reasons.append('stale_dataset')
    return (len(reasons)==0, reasons)

def emit_dataset_lineage_record(*, dataset_id:str, source_refs:list[str], version:str)->dict:
    return {
        'artifact_type':'dataset_lineage_record','artifact_version':'1.0.0','schema_version':'1.0.0','standards_version':'1.9.1',
        'record_id':f'DLIN-{dataset_id}-{version}','owner':'DAT','created_at':'2026-04-15T00:00:00Z','artifact_family':'prompt_task_bundle',
        'details':{'dataset_id':dataset_id,'source_refs':sorted(source_refs),'version':version}
    }
