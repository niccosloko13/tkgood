from copy import deepcopy
import pytest
from app import gold_set
from app.product_detection import detect
from test_product_detection import library,seed
from test_capture import api,database


def review(presence='yes',**kwargs):
    return {'human_reviewed':True,'review_version':'gold-set-v1','product_presence':presence,
      'specificity':'specific','canonical_product_name':None,'raw_product_name':None,'review_notes':'',
      'language':'unknown','candidate_reviews':[],**kwargs}


def prepare(library):
    with library.connect() as con:
        for n,caption in enumerate(['portable blender','dish brush','nothing here','plain text','escova'],1):
            seed(con,caption,username=f'@maker{n}',n=n)
    with library.connect() as con:detect(con);gold_set.migrate(con)


def test_pending_is_not_human_truth_and_null_metrics(library):
    prepare(library)
    with library.connect() as con:
        gold=gold_set.listing(con);r=gold_set.benchmark(con)
        assert gold['progress']=={'total':5,'reviewed':0,'pending':5,'yes':0,'no':0,'unclear':0}
        assert all(c['product_presence'] is None and not c['human_reviewed'] for c in gold['items'])
        assert r['precision'] is None and r['recall'] is None and r['f1'] is None
        assert r['product_naming_accuracy'] is None
        assert all(a['name_match']=='unreviewed' and a['evidence_quality'] is None for a in r['candidate_audit'])


def test_persistence_explicit_review_and_idempotent_history(library):
    prepare(library)
    with library.connect() as con:
        data=review(canonical_product_name='Portable Blender',raw_product_name='PORTABLE blender!',review_notes='Human decision',language='en')
        a=gold_set.save_review(con,1,data);b=gold_set.save_review(con,1,data)
        assert a==b and a['human_reviewed']
        assert a['raw_product_name']=='PORTABLE blender!'
        assert con.execute('SELECT count(*) FROM gold_review_history').fetchone()[0]==1
    with library.connect() as con:assert gold_set.detail(con,1)['canonical_product_name']=='Portable Blender'


def test_tp_fp_fn_tn_unclear_and_all_metrics(library):
    prepare(library)
    with library.connect() as con:
        cid=gold_set.detail(con,1)['candidates'][0]['id']
        gold_set.save_review(con,1,review(candidate_reviews=[{'candidate_id':cid,'name_match':'acceptable','evidence_quality':'strong'}]))
        gold_set.save_review(con,2,review('no',fp_reason='wrong_context'))
        gold_set.save_review(con,3,review(fn_reason='unknown_vocabulary'))
        gold_set.save_review(con,4,review('no'))
        gold_set.save_review(con,5,review('unclear'))
        r=gold_set.benchmark(con)
        assert (r['tp'],r['fp'],r['fn'],r['tn'])==(1,1,1,1)
        assert (r['precision'],r['recall'],r['f1'],r['presence_detection_accuracy'])==(.5,.5,.5,.5)
        assert r['strict_name_aware']['tp']==1
        assert r['excluded']=={'unclear':1}
        assert r['product_naming_accuracy']==1
        assert r['fn_reasons']=={'unknown_vocabulary':1} and r['fp_reasons']=={'wrong_context':1}
        assert r['candidate_coverage']==3/5


def test_wrong_name_and_unreviewed_not_called_correct_identity(library):
    prepare(library)
    with library.connect() as con:
        cid=gold_set.detail(con,1)['candidates'][0]['id']
        gold_set.save_review(con,1,review(candidate_reviews=[{'candidate_id':cid,'name_match':'wrong','evidence_quality':'wrong'}]))
        gold_set.save_review(con,2,review())
        r=gold_set.benchmark(con)
        assert r['presence']['tp']==2
        assert r['primary_metric']=='strict_name_aware' and r['tp']==0 and r['fn']==1
        assert r['strict_name_aware']['tp']==0 and r['strict_name_aware']['fn']==1
        assert r['strict_name_aware']['excluded']['pending_name_match']==1
        assert r['product_naming_accuracy']==0
        assert r['cases'][0]['detected_name_match']=='wrong'
        assert r['cases'][0]['detection_presence_correct'] is True


def test_versioning_run_idempotency_and_no_detector_mutation(library):
    prepare(library)
    with library.connect() as con:
        tables=['videos','product_candidates','product_candidate_evidence','product_candidate_aliases','candidate_reference_urls','product_detection_runs','product_vocabulary_terms','product_vocabulary_state','candidate_semantics','product_identity_pairs']
        before={t:[tuple(r) for r in con.execute('SELECT * FROM '+t)] for t in tables}
        gold_set.save_review(con,3,review(fn_reason='caption_missing'))
        a=gold_set.benchmark(con);b=gold_set.benchmark(con)
        assert a==b and a['run_id']==1
        assert a['gold_set_version']=='gold-set-v1' and a['detector_version']=='product-candidate-v1'
        assert a['vocabulary_version'].startswith('product-vocabulary-v') and a['rules_version']=='product-corroboration-v1'
        gold_set.save_review(con,3,review('no'))
        assert gold_set.benchmark(con)['run_id']==2
        assert before=={t:[tuple(r) for r in con.execute('SELECT * FROM '+t)] for t in tables}


@pytest.mark.parametrize('invalid',[{'human_reviewed':False},{'product_presence':None},{'review_version':'bad'},
 {'fn_reason':'invented'},{'fp_reason':'invented'},{'candidate_reviews':[{'candidate_id':999,'name_match':'exact'}]}])
def test_invalid_labels_rejected(library,invalid):
    prepare(library)
    with library.connect() as con:
        with pytest.raises(ValueError):gold_set.save_review(con,1,review(**invalid))
        assert gold_set.listing(con)['progress']['reviewed']==0


def test_language_is_human_selected_not_inferred(library):
    prepare(library)
    with library.connect() as con:
        gold_set.save_review(con,3,review('no',language='pt'))
        r=gold_set.benchmark(con)
        assert r['language_breakdown']['pt']['presence']['tn']==1
        assert not r['language_breakdown']['pt']['sufficient_data']
        assert r['language_breakdown']['pt']['presence']['accuracy'] is None
        assert r['language_breakdown']['en']['presence']['evaluated_videos']==0
        assert r['language_breakdown']['ar']['presence']['evaluated_videos']==0


def test_gold_api_local_validation_and_no_prefill(api,monkeypatch):
    from app import db
    monkeypatch.setattr(gold_set,'export_files',lambda *a:None)
    _,call=api
    with db.connect() as con:seed(con,'portable blender')
    assert call('/api/gold-set')[1]['progress']['reviewed']==0
    assert call('/api/gold-set/1')[1]['canonical_product_name'] is None
    assert call('/api/gold-set/1/review',review('unclear'))[0]==200
    result=call('/api/gold-set/benchmark',{})[1]
    assert result['reviewed_videos']==1 and result['evaluated_videos']==0 and result['precision'] is None
    assert call('/api/gold-set/benchmark/latest')[1]['run_id']==result['run_id']
    assert call('/api/gold-set/999')[0]==404
    assert call('/api/gold-set/1/review',{**review(),'human_reviewed':False})[0]==422


def test_automatic_partial_at_15_and_final_at_45_without_label_inference(library):
    with library.connect() as con:
        for n in range(1,46):seed(con,'persisted caption',username=f'@maker{n}',n=n)
        gold_set.migrate(con)
        for n in range(1,15):gold_set.save_review(con,n,review(['yes','no','unclear'][(n-1)%3]))
        assert gold_set.automatic_benchmark(con) is None
        assert con.execute('SELECT count(*) FROM detection_benchmark_runs').fetchone()[0]==0
        gold_set.save_review(con,15,review('unclear'))
        partial=gold_set.automatic_benchmark(con)
        assert partial['evaluation_label']=='PARTIAL GOLD SET' and partial['evaluation_stage']=='partial'
        assert partial['progress']=={'total':45,'reviewed':15,'pending':30,'yes':5,'no':5,'unclear':5}
        assert partial['fn']==5 and partial['tn']==5 and partial['tp']==partial['fp']==0
        assert gold_set.automatic_benchmark(con)==partial
        for n in range(16,46):gold_set.save_review(con,n,review('no'))
        final=gold_set.automatic_benchmark(con)
        assert final['evaluation_label']=='FINAL GOLD SET' and final['gold_set_version']=='gold-set-v1'
        assert final['reviewed_videos']==45 and final['progress']['pending']==0
        assert con.execute('SELECT count(*) FROM product_candidates').fetchone()[0]==0
        assert con.execute('SELECT count(*) FROM product_detection_runs').fetchone()[0]==0


def test_review_api_automatically_exports_partial_and_keeps_saved_label_if_export_fails(api,monkeypatch):
    from app import db
    _,call=api;exports=[]
    monkeypatch.setattr(gold_set,'export_files',lambda gold,report:exports.append(report))
    with db.connect() as con:
        for n in range(1,17):seed(con,'persisted caption',username=f'@maker{n}',n=n)
        gold_set.migrate(con)
        for n in range(1,15):gold_set.save_review(con,n,review('no'))
    status,data=call('/api/gold-set/15/review',review('no'))
    assert status==200 and data['automatic_benchmark']['evaluation_label']=='PARTIAL GOLD SET'
    assert len(exports)==1 and exports[0]['reviewed_videos']==15
    def fail(*args):raise OSError('test export unavailable')
    monkeypatch.setattr(gold_set,'export_files',fail)
    status,data=call('/api/gold-set/16/review',review('no'))
    assert status==200 and data['human_reviewed'] is True and data['automatic_benchmark_error']
    assert call('/api/gold-set/16')[1]['human_reviewed'] is True
    assert call('/api/gold-set')[1]['progress']['reviewed']==16
