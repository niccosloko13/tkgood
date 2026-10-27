"""Fixed, explicitly requested, maximum-five HIGH pilot in existing workspace."""
import sys
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import selective_enrichment as selective


def main():
    ident=selective.create()
    result=selective.run(ident)
    path=Path(__file__).resolve().parents[1]/'artifacts/selective-enrichment/pilot-v1.json'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2),flush=True)
    return 0 if result['run']['status']=='COMPLETED' else 1


if __name__=='__main__':raise SystemExit(main())
