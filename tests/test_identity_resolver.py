"""Resolver-only offline tests; no browser or production database."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from app.product_identity_resolver import compare,configuration,generate_pairs,resolve,records,occurrences
from app.product_detection import detect
from test_product_detection import library,seed
from test_capture import api,database


def occurrence(phrase,video=1,candidate=1,**kwargs):
    return {'id':f'{candidate}:{video}','phrase':phrase,'aliases':[phrase],'captions':[],
      'video_id':video,'candidate_id':candidate,'creator':f'@creator{video}',**kwargs}


@pytest.mark.parametrize('a,b,result',[('dish brush','floor brush','different'),('portable dryer','hair dryer','insufficient'),
 ('brush','brush','insufficient'),('3 in 1 window cleaner','2 in 1 window cleaner','different')])
def test_generic_and_negative_pairs(a,b,result):
    r=compare(occurrence(a),occurrence(b,2))
    assert r['identity_score']<40 and r['semantic_result']==result
    assert r['features']['generic_head_overlap']['contribution']==0


def test_exact_specific_phrase_and_modifiers_are_auditable():
    a=occurrence('electric rotating shower scrubber');b=occurrence(a['phrase'],2)
    r=compare(a,b)
    assert r['semantic_result']=='possible_same_product' and r['identity_score']==70
    assert r['features']['exact_normalized_phrase']['contribution']==30
    assert r['features']['modifier_overlap']['contribution']==20
    assert all({'value','weight','explanation','contribution'}<=f.keys() for f in r['features'].values())
    assert r['not_merged']
    assert compare(a,{**b,'video_id':1})['semantic_result']=='insufficient'


def test_conflicting_usage_modifiers_override_overlap():
    r=compare(occurrence('electric rotating dish brush'),occurrence('electric rotating floor brush',2))
    assert r['features']['modifier_overlap']['contribution']>0
    assert r['features']['modifier_conflict']['contribution']<0
    assert r['semantic_result']=='different'


def test_exact_public_listing_is_strong_but_profile_or_unbound_context_is_not():
    url='https://store.example/products/brush?sku=A'
    a=occurrence('dish brush',urls=[{'url':url,'url_type':'commercial_link','extracted_text':'dish brush'}])
    b=deepcopy(a);b['video_id']=2
    assert compare(a,b)['semantic_result']=='possible_same_product'
    assert compare(a,b)['features']['commercial_url_match']['contribution']==75
    for kind in ('creator_profile','profile_link'):
        a['urls'][0]['url_type']=kind;b['urls'][0]['url_type']=kind
        assert compare(a,b)['features']['commercial_url_match']['contribution']==0
    a['urls'][0].update(url_type='external_link',extracted_text='other product')
    assert compare(a,b)['features']['commercial_url_match']['contribution']==0


def test_explicit_brand_like_tokens_not_inferred_brand_fields():
    r=compare(occurrence('Ninja Blast Portable Blender'),occurrence('Ninja Blast blender',2))
    assert r['features']['brand_token_match']['value']==['blast','ninja']
    assert r['features']['brand_token_match']['contribution']==35
    assert r['semantic_result']=='possible_same_product'
    assert 'brand' not in r and 'model' not in r
    assert compare(occurrence('portable blender'),occurrence('mini portable blender',2))['features']['brand_token_match']['value']==[]


def test_explicit_dimensions_and_model_conflict():
    r=compare(occurrence('electric rotating brush A12 10cm'),occurrence('electric rotating brush A13 20cm',2))
    assert r['features']['model_conflict']['contribution']<0
    assert r['features']['dimension_conflict']['contribution']<0
    assert r['semantic_result']=='different'
    decimal=compare(occurrence('electric rotating brush 1.5cm'),occurrence('electric rotating brush 1 5cm',2))
    assert decimal['features']['dimension_conflict']['contribution']<0
    assert decimal['semantic_result']=='different'
    bundle=compare(occurrence('3-in-1 window cleaner'),occurrence('3-in-1 window cleaner',2))
    assert bundle['features']['model_token_match']['value']==[]
    caption_numbers=compare(occurrence('electric rotating window cleaner',captions=['3 in 1 electric rotating window cleaner']),
                            occurrence('electric rotating window cleaner',2,captions=['2 in 1 electric rotating window cleaner']))
    assert caption_numbers['semantic_result']=='different'
    assert caption_numbers['features']['number_conflict']['contribution']==-60


def test_unresolved_phrases_can_compare_without_promotion():
    r=compare(occurrence('vacuum cleaner'),occurrence('Mini Vacuum Cleaner',2))
    assert r['features']['specific_token_overlap']['value']==['vacuum']
    assert r['semantic_result']=='insufficient'
    assert r['occurrence_b']['phrase']=='Mini Vacuum Cleaner'


def test_specific_comments_are_capped_and_generic_comments_ignored():
    a=occurrence('rotating brush',comments=['wow','need this','link?'])
    b=occurrence('rotating brush',2,comments=['wow','need this','link?'])
    assert compare(a,b)['features']['supporting_comment_phrase_overlap']['contribution']==0
    a['comments']=['where is this rotating brush?']*30;b['comments']=['rotating brush?']*30
    r=compare(a,b)
    assert r['features']['supporting_comment_phrase_overlap']['contribution']==10
    assert r['semantic_result']=='insufficient'


def test_pair_generation_indexed_bounded_and_cross_candidate():
    items=[occurrence('portable blender',candidate=1),occurrence('mini portable blender',2,2)]
    pairs,diag=generate_pairs(items)
    assert (0,1) in pairs and not diag['truncated']
    cfg=configuration();cfg['resolver']['max_pairs']=3;cfg['resolver']['max_bucket_size']=5
    items=[occurrence('electric rotating shower scrubber',n+1,n+1) for n in range(500)]
    pairs,diag=generate_pairs(items,config=cfg)
    assert len(pairs)==3 and diag['truncated']
    unrelated=[occurrence('brush',n+1,n+1) for n in range(500)]
    assert generate_pairs(unrelated)[0]=={}


def test_resolver_no_global_alias_leak_no_merge_idempotency(library):
    with library.connect() as con:
        seed(con,'portable blender');seed(con,'mini blender',username='@other',n=2)
    with library.connect() as con:
        detect(con)
        con.execute("UPDATE product_candidate_aliases SET alias='Ninja Blast Blender',normalized_alias='ninja blast blender'")
        tables=['product_candidates','product_candidate_evidence','product_candidate_aliases','candidate_reference_urls','product_detection_runs','candidate_semantics']
        before={t:[tuple(r) for r in con.execute('SELECT * FROM '+t)] for t in tables}
        first=resolve(con);persisted=[tuple(r) for r in con.execute('SELECT * FROM product_identity_pairs')]
        assert all('Ninja' not in o['aliases'] for o in occurrences(con))
        assert all(p['semantic_result']!='possible_same_product' for p in first['pairs'])
        assert resolve(con)==first
        assert persisted==[tuple(r) for r in con.execute('SELECT * FROM product_identity_pairs')]
        assert before=={t:[tuple(r) for r in con.execute('SELECT * FROM '+t)] for t in tables}
        assert con.execute('SELECT count(*) FROM product_candidates').fetchone()[0]==2
        assert all(p['created_at'] and p['updated_at'] and p['id'] for p in records(con))


def test_real_escova_occurrences_remain_insufficient():
    fixture=json.loads((Path(__file__).parent/'fixtures/product-identity-escova.json').read_text(encoding='utf-8'))
    a,b=[occurrence('escova',v['id'],8,creator=v['username'],captions=[v['caption']],video_url=v['canonical_url']) for v in fixture['videos']]
    r=compare(a,b)
    assert r['semantic_result']=='insufficient' and r['identity_score']<40
    assert r['features']['modifier_overlap']['value']==['elétrica']
    assert r['features']['exact_normalized_phrase']['value'] is True
    assert r['features']['exact_normalized_phrase']['contribution']==0


def test_local_resolver_api_breakdown_and_missing_pair(api):
    from app import db
    _,call=api
    with db.connect() as con:seed(con,'escova');seed(con,'escova',username='@other',n=2)
    assert call('/api/product-candidates/detect',{})[0]==200
    status,report=call('/api/product-candidates/resolve-identity',{})
    assert status==200 and report['pairs_evaluated']==1
    status,data=call('/api/product-candidates/resolver-pairs')
    assert status==200 and data['not_merged']
    p=data['items'][0]
    assert p['identity_score']==0 and p['semantic_result']=='insufficient'
    assert call('/api/product-candidates/resolver-pairs/'+p['id'])[1]['evidence']['features']
    assert call('/api/product-candidates/resolver-pairs/missing')[0]==404
