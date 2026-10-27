import asyncio
import hashlib
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
import pytest
from PIL import Image
from starlette.requests import Request as ASGIRequest
from fastapi import HTTPException
from app import visual_assets as va,visual_identification as vi,gold_set
from app.visual_identification_api import upload_asset
from test_product_detection import library,seed
from test_capture import api,database


def image_bytes(fmt='PNG',color='red',size=(32,24)):
    data=BytesIO();Image.new('RGB',size,color).save(data,format=fmt);return data.getvalue()


def roots(tmp_path,monkeypatch):
    monkeypatch.setattr(va,'ROOT',tmp_path);monkeypatch.setattr(vi,'ROOT',tmp_path)


def metadata(**changes):return {'source_type':'manual_upload','filename':'test.png','content_type':'image/png',**changes}


@pytest.mark.parametrize('fmt,name,mime',[('PNG','frame.png','image/png'),('JPEG','frame.jpeg','image/jpeg'),('WEBP','frame.webp','image/webp')])
def test_valid_image_formats_dimensions_hash_and_original_bytes(library,tmp_path,monkeypatch,fmt,name,mime):
    roots(tmp_path,monkeypatch);data=image_bytes(fmt)
    with library.connect() as con:
        seed(con,None);con.execute("UPDATE videos SET thumbnail_url='https://p16.tiktokcdn.com/original'")
        result=va.persist_visual_asset(1,data,metadata(filename=name,content_type=mime),con)
        asset=result['asset'];assert asset['video_id']==1 and asset['width']==32 and asset['height']==24
        assert asset['sha256']==hashlib.sha256(data).hexdigest() and asset['mime_type']==mime
        assert asset['local_path'].startswith('data/visual_assets/1/')
        assert (tmp_path/asset['local_path']).read_bytes()==data
        assert vi.image_source(con,1)['status']=='available'
        assert vi.image_bytes(con,1)[0]==data
        assert con.execute('SELECT thumbnail_url FROM videos').fetchone()[0]=='https://p16.tiktokcdn.com/original'


@pytest.mark.parametrize('data,meta',[
    (b'not an image',metadata()),(image_bytes(),metadata(content_type='image/jpeg')),
    (image_bytes(),metadata(filename='bad.gif')),(image_bytes('GIF'),metadata(filename='bad.gif',content_type='image/gif')),
    (b'\x89PNG\r\n\x1a\n'+b'\0'*50,metadata()),
])
def test_invalid_format_mime_and_corrupt_image_create_no_asset(library,tmp_path,monkeypatch,data,meta):
    roots(tmp_path,monkeypatch)
    with library.connect() as con:
        seed(con,None)
        with pytest.raises(ValueError):va.persist_visual_asset(1,data,meta,con)
        assert con.execute('SELECT count(*) FROM visual_image_assets').fetchone()[0]==0
        assert not (tmp_path/'data/visual_assets').exists()


def test_size_dimensions_and_streamed_http_limit(library,tmp_path,monkeypatch):
    roots(tmp_path,monkeypatch)
    with library.connect() as con:
        seed(con,None)
        with pytest.raises(ValueError):va.persist_visual_asset(1,b'x'*(va.MAX_BYTES+1),metadata(),con)
        monkeypatch.setattr(va,'MAX_SIDE',16)
        with pytest.raises(ValueError,match='dimensions'):va.persist_visual_asset(1,image_bytes(),metadata(),con)
    scope={'type':'http','headers':[(b'content-length',str(va.MAX_BYTES+1).encode())],'method':'POST','path':'/'}
    request=ASGIRequest(scope)
    with pytest.raises(HTTPException) as error:asyncio.run(upload_asset(1,request,'test.png'))
    assert error.value.status_code==413
    # A missing Content-Length cannot evade the streaming cap.
    chunks=iter([b'x'*va.MAX_BYTES,b'x'])
    async def receive():return {'type':'http.request','body':next(chunks),'more_body':True}
    request=ASGIRequest({**scope,'headers':[]},receive)
    with pytest.raises(HTTPException) as error:asyncio.run(upload_asset(1,request,'test.png'))
    assert error.value.status_code==413


def test_foreign_upload_origin_is_rejected_before_reading_body_or_storing_data():
    async def receive():pytest.fail('An untrusted origin body must not be consumed')
    request=ASGIRequest({'type':'http','headers':[(b'origin',b'https://evil.invalid'),(b'content-type',b'image/png')],
                         'method':'POST','path':'/'},receive)
    with pytest.raises(HTTPException) as error:asyncio.run(upload_asset(1,request,'test.png'))
    assert error.value.status_code==403


def test_duplicate_and_video_association_are_idempotent_and_not_global(library,tmp_path,monkeypatch):
    roots(tmp_path,monkeypatch);data=image_bytes()
    with library.connect() as con:
        seed(con,None);seed(con,None,username='@other',n=2)
        first=va.persist_visual_asset(1,data,metadata(),con)
        modified=(tmp_path/first['asset']['local_path']).stat().st_mtime_ns
        second=va.persist_visual_asset(1,data,metadata(filename='another.png'),con)
        other=va.persist_visual_asset(2,data,metadata(source_type='imported_asset'),con)
        assert second['duplicate'] and first['asset']['asset_id']==second['asset']['asset_id']
        assert (tmp_path/first['asset']['local_path']).stat().st_mtime_ns==modified
        assert other['asset']['asset_id']!=first['asset']['asset_id'] and other['asset']['video_id']==2
        assert con.execute('SELECT count(*) FROM visual_image_assets').fetchone()[0]==2
        assert len(list((tmp_path/'data/visual_assets/1').iterdir()))==1
        with pytest.raises(KeyError):va.persist_visual_asset(999,data,metadata(),con)


def test_reingested_legacy_asset_retains_id_and_archives_original_provenance(library,tmp_path,monkeypatch):
    roots(tmp_path,monkeypatch);data=image_bytes()
    folder=tmp_path/'data/media';folder.mkdir(parents=True);(folder/'old.png').write_bytes(data)
    with library.connect() as con:
        seed(con,None);vi.register_image(con,1,'data/media/old.png','local_frame')
        old=dict(con.execute('SELECT * FROM visual_image_assets').fetchone())
        result=va.persist_visual_asset(1,data,metadata(),con)
        assert result['duplicate'] and result['asset']['asset_id']==old['id']
        assert result['asset']['width']==32 and result['asset']['height']==24
        assert result['asset']['local_path'].startswith('data/visual_assets/1/')
        provenance=json.loads(con.execute('SELECT source_metadata_json FROM visual_image_assets').fetchone()[0])
        assert provenance['legacy_asset']['relative_path']=='data/media/old.png'
        assert (folder/'old.png').read_bytes()==data


def test_future_capture_contract_cannot_bypass_security_stop(library,tmp_path,monkeypatch):
    roots(tmp_path,monkeypatch)
    with library.connect() as con:
        seed(con,None)
        con.execute("INSERT INTO system_state VALUES ('browser_security_stop','{\"reason\":\"HTTP 403\"}','old')")
        with pytest.raises(ValueError,match='security stop'):
            va.persist_visual_asset(1,image_bytes(),metadata(source_type='future_capture',capture_id='future'),con)
        assert json.loads(con.execute("SELECT value_json FROM system_state WHERE key='browser_security_stop'").fetchone()[0])['reason']=='HTTP 403'


def post_file(base,vid,data,filename='test.png',content_type='image/png',origin=None):
    headers={'Content-Type':content_type}
    if origin:headers['Origin']=origin
    try:
        with urlopen(Request(base+f'/api/visual-identification/videos/{vid}/assets?filename={filename}',data=data,headers=headers),timeout=8) as response:
            return response.status,json.load(response)
    except HTTPError as error:return error.code,json.load(error)


def test_upload_assisted_lens_web_aliases_gold_comparison_and_no_mutations(api,tmp_path,monkeypatch):
    from app import db
    roots(tmp_path,monkeypatch);base,call=api
    import socket
    # Every request in this test is loopback; no image/provider network client exists.
    original=socket.create_connection
    def loopback_only(address,*args,**kwargs):
        assert address[0] in ('127.0.0.1','localhost');return original(address,*args,**kwargs)
    monkeypatch.setattr(socket,'create_connection',loopback_only)
    with db.connect() as con:
        seed(con,None);seed(con,'Easy to clean kitchen',username='@other',n=2);seed(con,'No more stirring',username='@third',n=3)
        con.execute("UPDATE videos SET thumbnail_url='https://p16.tiktokcdn.com/reference'")
        gold_set.migrate(con)
        con.execute("UPDATE gold_video_labels SET review_status='reviewed',reviewer_type='human',product_presence='yes',canonical_product_name='Outlet extender' WHERE video_id=1")
        con.execute("UPDATE gold_video_labels SET review_status='reviewed',reviewer_type='human',product_presence='unclear' WHERE video_id=2")
        gold_before=[tuple(r) for r in con.execute('SELECT * FROM gold_video_labels')]
        assert vi.gold_high_queue(con)[0]['benchmark_category']=='fn'
        assert vi.image_source(con,1)['status']=='visual_unavailable'
    status,uploaded=post_file(base,1,image_bytes());assert status==201
    assert uploaded['image']['status']=='available';sha=uploaded['asset']['sha256']
    assert post_file(base,1,image_bytes())[1]['duplicate']
    # Exercise HTTP rejection without an unread-body TCP reset on Windows.
    # The body-presence/early-rejection invariant is tested directly above.
    assert post_file(base,1,b'',origin='https://evil.invalid')[0]==403
    assert call('/api/visual-identification/videos/1/assisted-identification',{'image_sha256':sha})[0]==200
    assert call('/api/visual-identification/videos/1/assisted-identification',{'image_sha256':sha})[0]==200
    post_file(base,3,image_bytes())
    with db.connect() as con:third=vi.image_source(con,3)['sha256']
    assert call('/api/visual-identification/videos/3/assisted-identification',{'image_sha256':third})[0]==422
    lens={'image_sha256':sha,'possible_product_name':'Electrical Outlet Expander','result_url':'https://retailer.invalid/one',
        'source':'Manual Lens reference','listing_title':'Electrical Outlet Extender','observed_at':'2026-10-23T12:00:00Z','notes':'Compatible outline; identity unconfirmed'}
    status,proposal=call('/api/visual-identification/videos/1/lens-assisted',lens);assert status==200
    assert proposal['review_status']=='suggested' and not proposal['product_confirmed']
    eid=proposal['evidence_id']
    with db.connect() as con:
        assert con.execute('SELECT domain FROM visual_product_search_evidence').fetchone()[0]=='retailer.invalid'
        con.execute("UPDATE videos SET caption='Electrical Outlet Extender' WHERE id=1")
    web={'title':'Electrical Outlet Extender','url':'https://retailer.invalid/one','source':'Manual product reference','observed_at':'2026-10-23T13:00:00Z',
        'possible_match':True,'match_reason':'Compatible image; not final identity','visual_compatible':True,'independence_group':'retailer','independence_reviewed':True}
    assert call(f'/api/visual-identification/evidence/{eid}/product-search',web)[0]==200
    with db.connect() as con:assert vi.proposals(con,1)[0]['hypothesis']['canonical_name_suggestion']=='electrical outlet extender'
    for state in ['accepted','rejected','unclear','accepted']:
        assert call(f'/api/visual-identification/evidence/{eid}/review',{'human_reviewed':True,'review_status':state})[0]==200
    assert call(f'/api/visual-identification/evidence/{eid}/gold-comparison',{'human_reviewed':True,'name_match':'acceptable','helpful':True})[0]==200
    with db.connect() as con:
        m=vi.local_asset_metrics(con);assert m['Gold_FN_tested']==1 and m['visual_helpful']==m['visual_match']==1
        assert con.execute('SELECT count(*) FROM visual_assisted_sessions').fetchone()[0]==1
        assert con.execute('SELECT count(*) FROM visual_review_history').fetchone()[0]==4
        assert [tuple(r) for r in con.execute('SELECT * FROM gold_video_labels')]==gold_before
        assert con.execute('SELECT count(*) FROM product_candidates').fetchone()[0]==0
        assert con.execute("SELECT thumbnail_url FROM videos WHERE id=1").fetchone()[0]=='https://p16.tiktokcdn.com/reference'
    # A new asset must not borrow the accepted proposal or Gold assessment from the old image.
    post_file(base,1,image_bytes(color='blue'))
    with db.connect() as con:
        assert vi.proposals(con,1)[0]['image_matches_current'] is False
        assert vi.local_asset_metrics(con)['Gold_FN_tested']==0
