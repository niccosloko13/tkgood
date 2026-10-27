from typing import Literal
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from .db import connect
from . import gold_set

router=APIRouter(prefix='/api/gold-set')


class CandidateReview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    candidate_id:int=Field(gt=0)
    name_match:Literal['exact','acceptable','wrong','unreviewed']
    evidence_quality:Literal['strong','weak','wrong']|None=None
    notes:str=Field(default='',max_length=4000)


class HumanReview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    review_version:Literal['gold-set-v1']
    human_reviewed:Literal[True]
    product_presence:Literal['yes','no','unclear']
    canonical_product_name:str|None=Field(default=None,max_length=300)
    raw_product_name:str|None=Field(default=None,max_length=300)
    specificity:Literal['specific','broad','unclear']
    review_notes:str=Field(default='',max_length=8000)
    language:Literal['pt','en','ar','es','unknown']='unknown'
    fn_reason:Literal['visual_only','visual_helped','generic_caption','missing_enrichment','unknown_vocabulary','caption_missing','product_only_in_comments','generic_phrase','unsupported_language','insufficient_text','normalization_failure','other']|None=None
    fp_reason:Literal['generic_term','wrong_context','creator_context_leak','search_query_leak','comment_noise','other']|None=None
    review_method:Literal['persisted_only','video_opened','lens_assisted']|None=None
    candidate_reviews:list[CandidateReview]=Field(default_factory=list,max_length=100)


@router.get('')
def listing():
    with connect() as con:return gold_set.listing(con)


@router.post('/benchmark')
def benchmark():
    with connect() as con:
        report=gold_set.benchmark(con);gold=gold_set.listing(con)
    gold_set.export_files(gold,report)
    return report


@router.get('/benchmark/latest')
def latest():
    import json
    with connect() as con:
        row=con.execute('SELECT report_json FROM detection_benchmark_runs ORDER BY id DESC LIMIT 1').fetchone()
        return json.loads(row[0]) if row else None


@router.get('/export')
def export_reviews():
    """Download saved human work only; no saves, benchmark runs or remote requests."""
    import csv
    import io
    import json
    import zipfile
    from fastapi.responses import Response
    with connect() as con:
        con.execute('BEGIN')
        gold=gold_set.listing(con)
        reviewed=[v for v in gold['items'] if v['human_reviewed']]
        history=[dict(r) for r in con.execute('SELECT * FROM gold_review_history WHERE review_version=? ORDER BY id',(gold_set.VERSION,))]
        benchmarks=[json.loads(r[0]) for r in con.execute('SELECT report_json FROM detection_benchmark_runs ORDER BY id')]
    bundle={'gold_set_version':gold_set.VERSION,'exported_at':gold_set.now(),
            'progress':gold['progress'],'filter_counts':gold['filter_counts'],
            'reviews':reviewed,'review_history':history}
    columns=['video_id','url','creator_username','caption','product_presence','raw_product_name',
             'canonical_product_name','specificity','benchmark_category','fn_reason','fp_reason',
             'review_method','review_notes','language','reviewed_at','review_version','candidate_reviews']
    csv_file=io.StringIO(newline='');writer=csv.DictWriter(csv_file,fieldnames=columns)
    writer.writeheader()
    for v in reviewed:
        row={k:v.get(k) for k in columns}
        row['candidate_reviews']=json.dumps(v['candidates'],ensure_ascii=False)
        # Spreadsheet applications must treat human text as text, never formulas.
        writer.writerow({k:("'"+x if isinstance(x,str) and x.lstrip().startswith(('=','+','-','@')) else x) for k,x in row.items()})
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('gold_set_reviews.json',json.dumps(bundle,ensure_ascii=False,indent=2))
        archive.writestr('gold_set_reviews.csv',csv_file.getvalue().encode('utf-8-sig'))
        archive.writestr('benchmark_latest.json',json.dumps(benchmarks[-1] if benchmarks else None,ensure_ascii=False,indent=2))
        archive.writestr('benchmark_history.json',json.dumps(benchmarks,ensure_ascii=False,indent=2))
    return Response(output.getvalue(),media_type='application/zip',headers={
        'Content-Disposition':'attachment; filename="babi-gold-set-reviews.zip"',
        'Cache-Control':'no-store'})


@router.get('/{video_id}')
def detail(video_id:int):
    with connect() as con:
        result=gold_set.detail(con,video_id)
        if result is None:raise HTTPException(404,'Video not found')
        return result


@router.post('/{video_id}/review')
def save(video_id:int,body:HumanReview):
    with connect() as con:
        try:result=gold_set.save_review(con,video_id,body.model_dump(exclude_unset=True))
        except KeyError as e:raise HTTPException(404,str(e))
        except ValueError as e:raise HTTPException(422,str(e))
    # The human label is committed first; a report/export failure must not lose it.
    try:
        with connect() as con:
            report=gold_set.automatic_benchmark(con)
            gold=gold_set.listing(con) if report else None
        if report:gold_set.export_files(gold,report)
        result['automatic_benchmark']=report
    except Exception:
        import logging
        logging.getLogger(__name__).exception('Automatic gold benchmark failed after saving human review')
        result['automatic_benchmark']=None
        result['automatic_benchmark_error']='Review saved; automatic benchmark/export failed. Recalculate locally.'
    return result
