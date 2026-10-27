"""Persisted Library validation only; no browser commands."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import init_db,connect
from app.product_detection import detect,records
from app.candidate_corroboration import relationships
from app.candidate_gaps import unresolved_records
init_db()
with connect() as con:
    first=detect(con)
    initial_items=records(con)
    initial_related=relationships(con)
    initial_unresolved=unresolved_records(con)
with connect() as con:
    second=detect(con)
    items=records(con)
    related=relationships(con)
    unresolved=unresolved_records(con)
idempotency={'candidate_records_unchanged':initial_items==items,
             'relationship_records_unchanged':initial_related==related,
             'unresolved_records_unchanged':initial_unresolved==unresolved,
             'no_new_candidates':second['candidates_created']==0,
             'no_new_evidence':second['evidence_created']==0}
report={'first_run':first,'rerun':second,'idempotency':idempotency,'candidates':items,'relationships':related,'unresolved_phrases':unresolved}
path=Path('data/product_detection_validation.json')
path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'first_run':first,'rerun':second,'idempotency':idempotency,'candidates':[{'id':c['id'],'name':c['canonical_name'],'confidence':c['confidence'],'evidence':c['evidence_count'],'groups':c['unique_evidence_groups'],'independent_videos':c['independent_video_count'],'independent_creators':c['independent_creator_count'],'source_diversity_score':c['source_diversity_score'],'status':c['status'],'url':c['primary_reference_url']} for c in items]},ensure_ascii=True,indent=2))
