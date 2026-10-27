"""Offline semantic identity tests; existing legacy tests remain untouched."""
import json
from pathlib import Path
import pytest
from app.candidate_semantics import product_signature, pairwise, refresh, migrate, listing_urls, configuration
from app.product_detection import detect, records
from test_product_detection import library, seed
from test_capture import api, database


@pytest.mark.parametrize('a,b',[('brush','floor brush'),('brush','dish brush'),('dish brush','floor brush'),('portable dryer','portable clothes dryer'),('tool','tool')])
def test_generic_or_partial_phrase_does_not_establish_identity(a,b):
    result=pairwise(a,b)
    assert result['concept_similarity_score']>0
    assert result['product_identity_score']==0
    assert result['identity_signals']==[]


def test_specificity_signature_preserves_numbers_and_original():
    assert product_signature('Mini Vacuum Cleaner')['phrase_specificity']>product_signature('vacuum cleaner')['phrase_specificity']
    sig=product_signature('3 in 1 magnetic window cleaner')
    assert sig['specificity_level']=='high'
    assert sig['number_tokens']==['3','1']
    assert sig['raw_phrase']=='3 in 1 magnetic window cleaner'
    assert product_signature('electric long handle spin scrubber')['modifiers']==['electric','long-handle','spin']
    assert pairwise('3 in 1 magnetic window cleaner','9 in 1 magnetic window cleaner')['product_identity_score']==0


def test_specific_shared_modifiers_require_explicit_matching_phrase():
    result=pairwise('electric rotating shower scrubber','electric rotating shower scrubber')
    assert result['product_identity_score']==.85
    assert {s['type'] for s in result['identity_signals']}=={'exact_specific_phrase','specific_modifiers_shared'}
    assert pairwise('electric rotating shower scrubber','electric rotating floor scrubber')['product_identity_score']==0


def test_recurring_generic_concept_legacy_migration_and_idempotency(library):
    with library.connect() as con:
        seed(con,'escova',n=1);seed(con,'escova',username='@other',n=2)
        con.commit();detect(con)
        before=[tuple(r) for r in con.execute('SELECT * FROM product_candidates')]
        con.execute('DELETE FROM candidate_semantic_history');con.execute('DELETE FROM candidate_semantics')
        con.execute("DELETE FROM schema_migrations WHERE name='product-identity-foundation-v1'")
        migrate(con)
        item=records(con)[0]
        assert item['legacy_status']=='corroborated' and item['legacy_confidence']==.64
        assert item['semantic_status']=='concept_recurring'
        assert (item['detection_confidence'],item['recurrence_confidence'],item['identity_confidence'])==(.42,.6,0)
        assert not item['possible_same_product'] and not item['product_matched']
        assert item['semantic_history'][0]['legacy_confidence']==.64
        assert item['semantic_history'][0]['observed_at']
        assert item['identity_pairs'][0]['details']['evidence_ids_a']
        assert [tuple(r) for r in con.execute('SELECT * FROM product_candidates')]==before
        tables=['candidate_semantics','candidate_semantic_history','product_identity_pairs','product_identity_evidence']
        snapshot={t:[tuple(r) for r in con.execute('SELECT * FROM '+t)] for t in tables}
        refresh(con);migrate(con)
        assert snapshot=={t:[tuple(r) for r in con.execute('SELECT * FROM '+t)] for t in tables}


def test_exact_specific_phrase_across_creators_is_only_possible_not_matched(library):
    with library.connect() as con:
        seed(con,'portable blender');seed(con,'portable blender',username='@other',n=2);con.commit();detect(con)
        cid=records(con)[0]['id']
        phrase='electric rotating shower scrubber'
        con.execute('UPDATE product_candidates SET canonical_name=?,normalized_name=? WHERE id=?',(phrase,phrase,cid))
        con.execute('UPDATE product_candidate_evidence SET extracted_text=? WHERE candidate_id=?',(phrase,cid))
        refresh(con);item=records(con)[0]
        assert item['semantic_status']=='possible_same_product' and item['identity_confidence']==.85
        assert not item['product_matched']
        con.execute('UPDATE video_creators SET creator_id=1')
        refresh(con);item=records(con)[0]
        assert item['identity_confidence']==0 and not item['possible_same_product']


def test_profile_links_are_not_bound_listing_identity():
    cfg=configuration();url='https://store.example/products/brush?sku=red&utm_source=test'
    evidence={'evidence_type':'profile_link','extracted_text':'brush','source_url':url}
    assert listing_urls([evidence],'brush',cfg)==set()
    evidence['evidence_type']='external_link';evidence['extracted_text']='unrelated'
    assert listing_urls([evidence],'brush',cfg)==set()
    evidence['extracted_text']='brush'
    bound=listing_urls([evidence],'brush',cfg)
    assert bound=={'https://store.example/products/brush?sku=red'}
    assert pairwise('brush','brush',bound_urls_a=bound,bound_urls_b=bound)['product_identity_score']==.9


def test_related_candidates_are_not_merged(library):
    with library.connect() as con:
        seed(con,'dish brush');seed(con,'long-handled floor brush',username='@other',n=2)
        con.commit();detect(con);items=records(con)
        assert len(items)==2
        assert all(c['semantic_status']=='observed' and c['identity_confidence']==0 for c in items)
        assert all(not c['product_matched'] for c in items)


def test_occurrence_phrases_not_global_aliases_control_identity(library):
    with library.connect() as con:
        seed(con,'portable blender');seed(con,'portable blender',username='@other',n=2);con.commit();detect(con)
        phrase='electric rotating shower scrubber';cid=records(con)[0]['id']
        con.execute('UPDATE product_candidates SET canonical_name=?,normalized_name=? WHERE id=?',(phrase,phrase,cid))
        con.execute('UPDATE product_candidate_aliases SET alias=?,normalized_alias=? WHERE candidate_id=?',(phrase,phrase,cid))
        refresh(con)
        assert records(con)[0]['identity_confidence']==0


def test_real_escova_fixture_is_only_a_recurring_generic_concept():
    fixture=json.loads((Path(__file__).parent/'fixtures/product-identity-escova.json').read_text(encoding='utf-8'))
    assert len(fixture['videos'])==2
    assert len({v['username'] for v in fixture['videos']})==2
    assert fixture['supporting_comment_count']==0
    assert {e['extracted_text'] for e in fixture['evidence'] if e['evidence_type']=='caption'}=={'escova'}
    assert {g['group_key'] for g in fixture['evidence_groups']}=={'video:39','video:40'}
    assert all(v['caption'] and v['canonical_url'] for v in fixture['videos'])
    result=pairwise('escova','escova')
    assert result['concept_similarity_score']==1
    assert result['product_identity_score']==0
    assert result['signature_a']['specific_tokens']==[]


def test_additive_identity_api_fields(api):
    from app import db
    _,call=api
    with db.connect() as con:seed(con,'portable blender')
    status,_=call('/api/product-candidates/detect',{})
    assert status==200
    status,data=call('/api/product-candidates')
    assert status==200
    c=data['items'][0]
    assert c['legacy_status']=='observed' and c['semantic_status']=='observed'
    assert {c['detection_confidence'],c['recurrence_confidence'],c['identity_confidence']}=={.42,0}
    assert call('/api/product-candidates/identity-pairs')[0]==200
