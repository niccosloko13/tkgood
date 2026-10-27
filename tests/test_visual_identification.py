import base64
import json
from datetime import datetime,timezone
from pathlib import Path
import pytest
from app import visual_identification as vi,category_intelligence as ci,gold_set
from app.visual_identification_api import ProductSearchEvidence
from test_product_detection import library,seed
from test_capture import api,database

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6F+QAAAAASUVORK5CYII=')


def local_image(con,tmp_path,monkeypatch,vid=1):
    monkeypatch.setattr(vi,'ROOT',tmp_path)
    folder=tmp_path/'data/visual-images';folder.mkdir(parents=True,exist_ok=True)
    (folder/'frame.png').write_bytes(PNG)
    return vi.register_image(con,vid,'data/visual-images/frame.png','local_frame')


def body(image,**changes):
    return vi.ProposalInput(provider='vision_model',possible_product_name='Portable Blender',
        aliases=['portable blender','Portable blender','Travel blender'],observed_at=datetime(2026,10,23,tzinfo=timezone.utc),
        source_type='vision_model_output',confidence=.95,reason='Visible blender-shaped device; model/SKU unconfirmed',
        provider_version='fixture',image_sha256=image['sha256'],**changes)


def test_schema_migration_preserves_legacy_visual_records(library):
    with library.connect() as con:
        seed(con,'caption')
        con.execute("INSERT INTO visual_product_evidence(video_id,image_source,provider,possible_product_name,review_status,observed_at) VALUES (1,'old','google_lens_assisted','old name','reviewed','2026-01-01')")
        before=tuple(con.execute('SELECT id,video_id,image_source,provider,possible_product_name,review_status,observed_at FROM visual_product_evidence').fetchone())
        vi.migrate(con);vi.migrate(con)
        assert tuple(con.execute('SELECT id,video_id,image_source,provider,possible_product_name,review_status,observed_at FROM visual_product_evidence').fetchone())==before
        assert vi.proposals(con,1)==[]


def test_tiktok_thumbnails_are_unavailable_without_any_network(library,monkeypatch):
    import socket
    monkeypatch.setattr(socket,'create_connection',lambda *a,**k:pytest.fail('No network allowed'))
    with library.connect() as con:
        seed(con,None)
        con.execute("UPDATE videos SET thumbnail_url='https://p16-common-sign.tiktokcdn.com/image.jpg?token=old'")
        source=vi.image_source(con,1)
        assert source['status']=='visual_unavailable' and source['reason']=='blocked_by_security_stop_tiktok_cdn'
        with pytest.raises(ValueError):vi.image_bytes(con,1)
        assert vi.REGISTRY['vision_model'].identify({'image':source})['proposal'] is None


def test_local_priority_hash_binding_and_path_safety(library,tmp_path,monkeypatch):
    with library.connect() as con:
        seed(con,'caption')
        image=local_image(con,tmp_path,monkeypatch)
        assert image['status']=='available' and image['source_type']=='local_frame'
        assert vi.image_bytes(con,1)[0]==PNG
        for path in ['../secret','C:/private.png','//server/share.png','app/main.py','data/visual-images/../other.png']:
            with pytest.raises(ValueError):vi.read_local(path)
        (tmp_path/'data/visual-images/frame.png').write_bytes(b'invalid')
        assert vi.image_source(con,1)['status']=='visual_unavailable'


def test_provider_abstraction_and_assisted_only_contract(library,tmp_path,monkeypatch):
    with pytest.raises(TypeError):vi.VisualSearchProvider()
    with library.connect() as con:
        seed(con,'caption');image=local_image(con,tmp_path,monkeypatch)
        item={'image':image}
        assert all(p.identify(item)['status']=='awaiting_assisted_input' for p in vi.REGISTRY.values())
        proposal=body(image)
        assert vi.REGISTRY['vision_model'].identify(item,proposal.model_dump())['status']=='suggested'
        with pytest.raises(ValueError):vi.REGISTRY['google_lens_assisted'].identify(item,proposal.model_dump())
        with pytest.raises(ValueError):vi.suggest(con,1,proposal.model_copy(update={'image_sha256':'0'*64}))


def test_evidence_aliases_idempotency_and_explicit_human_review(library,tmp_path,monkeypatch):
    with library.connect() as con:
        seed(con,'Portable blender');image=local_image(con,tmp_path,monkeypatch)
        gold_set.migrate(con);before=[tuple(r) for r in con.execute('SELECT * FROM gold_video_labels')]
        row=vi.suggest(con,1,body(image));second=vi.suggest(con,1,body(image))
        assert row['id']==second['id'] and row['review_status']=='suggested'
        assert json.loads(row['aliases_json'])==['Travel blender']
        for status in ['accepted','rejected','unclear']:assert not vi.review_proposal(con,row['id'],status)['product_confirmed']
        assert con.execute('SELECT count(*) FROM visual_review_history').fetchone()[0]==3
        assert con.execute('SELECT count(*) FROM product_candidates').fetchone()[0]==0
        assert [tuple(r) for r in con.execute('SELECT * FROM gold_video_labels')]==before


def add_web(con,eid,url,group,**changes):
    data={'title':'Portable Blender product','url':url,'source':'fixture','observed_at':'2026-10-23T00:00:00Z',
        'possible_match':1,'match_reason':'manual compatible image','visual_compatible':1,'contradiction':0,
        'independence_group':group,'independence_reviewed':1,**changes}
    con.execute('''INSERT INTO visual_product_search_evidence(evidence_id,title,url,source,observed_at,possible_match,match_reason,
        visual_compatible,contradiction,independence_group,independence_reviewed) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        (eid,*[data[k] for k in ['title','url','source','observed_at','possible_match','match_reason','visual_compatible','contradiction','independence_group','independence_reviewed']]))


def test_confidence_multisource_caps_independence_and_contradiction(library,tmp_path,monkeypatch):
    with library.connect() as con:
        seed(con,'Portable blender');image=local_image(con,tmp_path,monkeypatch);row=vi.suggest(con,1,body(image));eid=row['id']
        h=vi.proposals(con,1)[0]['hypothesis'];assert h['identity_confidence']==.35 and not h['product_confirmed']
        add_web(con,eid,'https://shop.example.com/a','one');add_web(con,eid,'https://other.example.com/b','two')
        assert vi.proposals(con,1)[0]['hypothesis']['independent_listing_sources']==1
        add_web(con,eid,'https://independent.invalid/listing','three')
        h=vi.proposals(con,1)[0]['hypothesis'];assert h['identity_confidence']==.6 and not h['product_confirmed']
        add_web(con,eid,'https://contradiction.invalid/no','four',contradiction=1)
        assert vi.proposals(con,1)[0]['hypothesis']['identity_confidence']<=.2


def test_caption_contradiction_and_generic_aliases_do_not_strengthen_identity(library,tmp_path,monkeypatch):
    with library.connect() as con:
        seed(con,'This is not a portable blender');image=local_image(con,tmp_path,monkeypatch)
        vi.suggest(con,1,body(image));h=vi.proposals(con,1)[0]['hypothesis']
        assert h['identity_confidence']<=.2 and 'observed_contradiction_cap' in h['reason']
        con.execute("UPDATE videos SET caption='gadgets'")
        vi.suggest(con,1,body(image).model_copy(update={'aliases':['gadgets'],'provider_version':'other'}))
        assert vi.proposals(con,1)[0]['hypothesis']['identity_confidence']==.25


def test_repeated_comments_add_only_one_support_term_and_preserve_provenance(library,tmp_path,monkeypatch):
    with library.connect() as con:
        seed(con,'Portable blender');image=local_image(con,tmp_path,monkeypatch)
        con.execute("INSERT INTO comment_samples(video_id,command_id,observed_at,target_count,stop_reason,scroll_steps,extractor_version,signals_json,terms_config_json,diagnostics_json) VALUES (1,1,'2026-10-23',30,'target_reached',0,'fixture','{}','{}','{}')")
        for i in range(2):
            con.execute("INSERT INTO comment_observations(sample_id,video_id,comment_key,author_username,text,position,source,observed_at,raw_visible_text,extraction_method,confidence,extractor_version) VALUES (1,1,?,'@viewer','Portable blender?',?,'comments_visible','2026-10-23','Portable blender?','fixture',0.9,'fixture')",(str(i),i+1))
        vi.suggest(con,1,body(image));h=vi.proposals(con,1)[0]['hypothesis']
        assert h['identity_confidence']==.45 and len(h['evidence_sources']['comments'])==2
        assert not h['product_confirmed']


def test_high_pilot_is_bounded_and_unavailable_is_not_a_suggestion(library,monkeypatch):
    with library.connect() as con:
        for n in range(1,17):seed(con,None,username='@maker'+str(n),n=n)
        # Selector itself must remain capped when its input contains more than 14 HIGH.
        monkeypatch.setattr(vi,'audit',lambda con:{'visual_queue':[{'video_id':n,'visual':{'priority':'HIGH' if n<16 else 'MEDIUM'}} for n in range(1,17)]})
        assert len(vi.high_queue(con))==14
        rid=vi.run_pilot(con);m=vi.metrics(con,rid)
        assert m['visual_items_attempted']==14 and m['visual_unavailable']==14
        assert m['provider_calls']==m['visual_suggestions']==0
        assert m['gold_name_match_rate'] is None
        assert json.loads(con.execute('SELECT selected_ids_json FROM visual_pilots').fetchone()[0])==list(range(1,15))


def test_gold_comparison_is_literal_or_separately_reviewed_not_new_gold(library,tmp_path,monkeypatch):
    with library.connect() as con:
        seed(con,'Portable blender');gold_set.migrate(con)
        con.execute("UPDATE gold_video_labels SET review_status='reviewed',reviewer_type='human',product_presence='yes',canonical_product_name='portable blender'")
        image=local_image(con,tmp_path,monkeypatch);vi.suggest(con,1,body(image))
        before=[tuple(r) for r in con.execute('SELECT * FROM gold_video_labels')]
        r=vi.gold_comparison(con)[0]
        assert r['visual_name_match'] is True and r['visual_helpful'] is None and r['visual_wrong'] is None
        assert [tuple(r) for r in con.execute('SELECT * FROM gold_video_labels')]==before


def test_web_evidence_and_reviews_api_require_explicit_valid_input(api,tmp_path,monkeypatch):
    from app import db
    _,call=api
    with db.connect() as con:
        seed(con,'Portable blender');image=local_image(con,tmp_path,monkeypatch);row=vi.suggest(con,1,body(image))
    route='/api/visual-identification/evidence/'+str(row['id'])
    assert call(route+'/review',{'review_status':'accepted'})[0]==422
    assert call(route+'/review',{'review_status':'accepted','human_reviewed':True})[0]==200
    assert call(route+'/product-search',{'title':'x','url':'https://www.tiktok.com/','source':'x','observed_at':'2026-01-01T00:00:00Z','possible_match':True,'match_reason':'test'})[0]==422
    entry={'title':'Portable blender','url':'https://example.invalid/item','source':'manual','observed_at':'2026-10-23T00:00:00Z',
        'possible_match':True,'match_reason':'needs review'}
    assert call(route+'/product-search',entry)[0]==200
    assert call(route+'/product-search',entry)[0]==200
    assert call(route+'/product-search',{**entry,'title':'Changed retry'})[0]==409
    assert call(route+'/product-search',{**entry,'title':'Changed retry','observed_at':'2026-10-23T01:00:00+01:00'})[0]==409
    with db.connect() as con:
        assert con.execute('SELECT count(*) FROM visual_product_search_evidence').fetchone()[0]==1
        assert con.execute('SELECT count(*) FROM product_candidates').fetchone()[0]==0
