#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from spectrum_systems.modules.runtime.agent_core_loop_proof import build_agent_core_loop_record


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--work-item-id",required=True)
    p.add_argument("--agent-type",default="unknown")
    p.add_argument("--source-artifact")
    p.add_argument("--output")
    p.add_argument("--base-ref")
    p.add_argument("--head-ref")
    a=p.parse_args()
    out=Path(a.output or f"artifacts/agent_core_loop/{a.work_item_id}.agent_core_loop_run_record.json")
    out.parent.mkdir(parents=True,exist_ok=True)
    rec=build_agent_core_loop_record(a.work_item_id,a.agent_type,a.source_artifact)
    out.write_text(json.dumps(rec,indent=2)+"\n",encoding="utf-8")
    print(out)
    return 0
if __name__=="__main__":
    raise SystemExit(main())
