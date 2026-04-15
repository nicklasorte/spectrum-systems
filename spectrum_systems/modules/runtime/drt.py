"""DRT drift signal emission."""
from __future__ import annotations

def emit_drift_signal(*, metric:str, value:float, threshold:float)->dict:
    return {'artifact_type':'drift_signal_record','artifact_version':'1.0.0','schema_version':'1.0.0','signal':metric,'value':float(value),'threshold':float(threshold),'drift_detected':float(value)>float(threshold)}
