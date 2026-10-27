"""Local byte ingestion only. No remote fetch, capture, browser or provider invocation."""
from datetime import datetime,timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
from typing import Literal
import uuid
import warnings
from PIL import Image,UnidentifiedImageError
from pydantic import BaseModel,ConfigDict,Field
from . import db

ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=10*1024*1024
MAX_PIXELS=20_000_000
MAX_SIDE=8192
MIMES={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}
EXTENSIONS={'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}


class SourceMetadata(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_type:Literal['manual_upload','future_capture','imported_asset']
    filename:str|None=Field(default=None,max_length=255)
    content_type:str|None=Field(default=None,max_length=100)
    notes:str=Field(default='',max_length=4000)
    capture_id:str|None=Field(default=None,max_length=128)


def migrate(con):
    columns={r[1] for r in con.execute('PRAGMA table_info(visual_image_assets)')}
    for name,definition in {'width':'INTEGER','height':'INTEGER','created_at':'TEXT','original_filename':'TEXT',
                            'source_metadata_json':"TEXT NOT NULL DEFAULT '{}'"}.items():
        if name not in columns:con.execute('ALTER TABLE visual_image_assets ADD COLUMN '+name+' '+definition)
    con.execute('''CREATE TABLE IF NOT EXISTS visual_asset_selections (
        video_id INTEGER PRIMARY KEY REFERENCES videos(id),asset_id INTEGER NOT NULL REFERENCES visual_image_assets(id),selected_at TEXT NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS visual_assisted_sessions (
        id INTEGER PRIMARY KEY,video_id INTEGER NOT NULL REFERENCES videos(id),image_sha256 TEXT NOT NULL,
        asset_id INTEGER REFERENCES visual_image_assets(id),created_at TEXT NOT NULL,
        UNIQUE(video_id,image_sha256))''')
    web_columns={r[1] for r in con.execute('PRAGMA table_info(visual_product_search_evidence)')}
    if 'domain' not in web_columns:con.execute('ALTER TABLE visual_product_search_evidence ADD COLUMN domain TEXT')


def validate_image(data,metadata):
    if not isinstance(data,(bytes,bytearray)):raise ValueError('Image bytes required')
    if not data or len(data)>MAX_BYTES:raise ValueError('Image must contain 1 byte to 10 MiB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(BytesIO(data),formats=list(MIMES)) as image:
                fmt=image.format;width,height=image.size
                if min(width,height)<1 or max(width,height)>MAX_SIDE or width*height>MAX_PIXELS:
                    raise ValueError('Image dimensions exceed 8192 per side or 20 million pixels')
                if getattr(image,'n_frames',1)!=1:raise ValueError('Animated images are not supported')
                image.verify()
            # Verify the decoded pixels too, not only extension/MIME/magic bytes.
            with Image.open(BytesIO(data),formats=list(MIMES)) as image:image.load()
    except (UnidentifiedImageError,OSError,SyntaxError,Image.DecompressionBombError,Image.DecompressionBombWarning) as exc:
        raise ValueError('Invalid or corrupt PNG/JPEG/WebP image') from exc
    mime=MIMES[fmt];declared=(metadata.content_type or '').split(';',1)[0].lower()
    if declared and declared not in (mime,'application/octet-stream'):
        raise ValueError('Declared MIME does not match decoded image')
    if metadata.filename:
        suffix=Path(metadata.filename).suffix.lower()
        expected={'.jpg':'JPEG','.jpeg':'JPEG','.png':'PNG','.webp':'WEBP'}.get(suffix)
        if expected!=fmt:raise ValueError('Filename format must match decoded jpg/jpeg/png/webp image')
    return {'mime_type':mime,'extension':EXTENSIONS[fmt],'width':width,'height':height,
            'sha256':hashlib.sha256(data).hexdigest()}


def asset_record(row):
    return {'asset_id':row['id'],'video_id':row['video_id'],'source_type':row['source_type'],
        'local_path':row['relative_path'],'sha256':row['sha256'],'width':row['width'],'height':row['height'],
        'mime_type':row['mime_type'],'created_at':row['created_at'] or row['observed_at']}


def persist_visual_asset(video_id,data,source_metadata,con=None):
    """Future contract: persist already-authorized visible bytes once; never acquires them."""
    metadata=SourceMetadata.model_validate(source_metadata)
    if con is None:
        with db.connect() as connection:return persist_visual_asset(video_id,data,metadata,connection)
    if not con.execute('SELECT 1 FROM videos WHERE id=?',(video_id,)).fetchone():raise KeyError('Video not found')
    if metadata.source_type=='future_capture':
        row=con.execute("SELECT value_json FROM system_state WHERE key='browser_security_stop'").fetchone()
        if row and json.loads(row[0]).get('reason'):raise ValueError('future_capture is disabled while security stop is active')
    info=validate_image(data,metadata);created=datetime.now(timezone.utc).isoformat()
    old=con.execute('SELECT * FROM visual_image_assets WHERE video_id=? AND sha256=?',(video_id,info['sha256'])).fetchone()
    # User filenames never become filesystem paths. Resolve every target inside this workspace.
    folder=(ROOT/'data/visual_assets'/str(video_id)).resolve()
    boundary=(ROOT/'data/visual_assets').resolve()
    if not boundary.is_relative_to(ROOT.resolve()) or not folder.is_relative_to(boundary):raise ValueError('Invalid asset destination')
    folder.mkdir(parents=True,exist_ok=True)
    target=folder/(info['sha256']+info['extension'])
    exists=(target.resolve().is_relative_to(folder) and target.is_file() and target.stat().st_size==len(data) and
            hashlib.sha256(target.read_bytes()).hexdigest()==info['sha256'])
    if not exists:
        temporary=folder/(info['sha256']+'.'+uuid.uuid4().hex+'.tmp')
        try:
            with temporary.open('xb') as stream:stream.write(data)
            os.replace(temporary,target)
        finally:
            if temporary.exists():temporary.unlink()
    path=target.relative_to(ROOT.resolve()).as_posix()
    con.execute('''INSERT OR IGNORE INTO visual_image_assets(video_id,relative_path,source_type,sha256,mime_type,
        observed_at,width,height,created_at,original_filename,source_metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
        (video_id,path,metadata.source_type,info['sha256'],info['mime_type'],created,info['width'],info['height'],created,
         metadata.filename,json.dumps(metadata.model_dump(),ensure_ascii=False)))
    if old and not str(old['relative_path']).startswith('data/visual_assets/'):
        # Explicit re-ingest of a legacy asset: keep its identity and archive
        # the old provenance while supplying validated dimensions/managed bytes.
        con.execute('''UPDATE visual_image_assets SET relative_path=?,source_type=?,width=?,height=?,created_at=?,
            source_metadata_json=? WHERE id=?''',
            (path,metadata.source_type,info['width'],info['height'],old['created_at'] or old['observed_at'],
             json.dumps({'legacy_asset':dict(old),'ingest':metadata.model_dump()},ensure_ascii=False),old['id']))
    row=con.execute('SELECT * FROM visual_image_assets WHERE video_id=? AND sha256=?',(video_id,info['sha256'])).fetchone()
    con.execute('''INSERT INTO visual_asset_selections(video_id,asset_id,selected_at) VALUES (?,?,?)
        ON CONFLICT(video_id) DO UPDATE SET asset_id=excluded.asset_id,selected_at=excluded.selected_at''',(video_id,row['id'],created))
    return {'asset':asset_record(row),'duplicate':old is not None,'thumbnail_url_changed':False}
