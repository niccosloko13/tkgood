"""Conservative, persisted-only product hypotheses. No network or physical-product merge."""
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


def configuration():
    return json.loads((Path(__file__).resolve().parents[1]/'config/product_detection.json').read_text(encoding='utf-8'))


def normalize(value):
    return ' '.join(re.sub(r'[^\w\s]', ' ', unicodedata.normalize('NFKC', value).casefold(), flags=re.UNICODE).replace('_',' ').split())


def extractProductCandidatePhrases(text, config=None):
    config = config or configuration()
    if not text:
        return []
    # Split simple CamelCase hashtags without translating or stemming.
    searchable = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)
    result = {}
    for pattern in config['product_patterns']:
        for match in re.finditer(r'(?<!\w)(?:'+pattern+r')(?!\w)', searchable, re.I):
            raw = match.group()
            normalized = normalize(raw)
            if config['minimum_phrase_length'] <= len(normalized) <= config['maximum_phrase_length'] and normalized not in config['stop_terms']:
                language = 'ar' if re.search('[\u0600-\u06ff]',raw) else None
                result[normalized] = dict(raw_phrase=raw, normalized_phrase=normalized, detected_language=language)
    return list(result.values())


def migrate(con):
    statements = [
        '''CREATE TABLE IF NOT EXISTS product_candidates (
        id INTEGER PRIMARY KEY,platform TEXT NOT NULL,canonical_name TEXT NOT NULL,normalized_name TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('observed','corroborated','promoted','rejected')),manual_status TEXT CHECK(manual_status IN ('confirmed','rejected')),
        confidence REAL NOT NULL,first_seen_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,primary_reference_url TEXT NOT NULL,
        detection_version TEXT NOT NULL,summary_json TEXT NOT NULL DEFAULT '{}', UNIQUE(platform,normalized_name))''',
        '''CREATE TABLE IF NOT EXISTS product_candidate_aliases (
        candidate_id INTEGER NOT NULL REFERENCES product_candidates(id),alias TEXT NOT NULL,normalized_alias TEXT NOT NULL,
        source TEXT NOT NULL,confidence REAL NOT NULL,observed_at TEXT NOT NULL,detected_language TEXT,
        UNIQUE(candidate_id,alias,source))''',
        '''CREATE TABLE IF NOT EXISTS product_candidate_evidence (
        id INTEGER PRIMARY KEY,candidate_id INTEGER NOT NULL REFERENCES product_candidates(id),evidence_type TEXT NOT NULL,
        source_entity_type TEXT NOT NULL,source_entity_id TEXT NOT NULL,video_id INTEGER REFERENCES videos(id),creator_id INTEGER REFERENCES creators(creator_id),
        commenter TEXT,source_url TEXT NOT NULL,raw_text TEXT NOT NULL,extracted_text TEXT,confidence REAL NOT NULL,
        observed_at TEXT NOT NULL,extractor_version TEXT NOT NULL,dedup_key TEXT NOT NULL UNIQUE)''',
        '''CREATE TABLE IF NOT EXISTS candidate_reference_urls (
        candidate_id INTEGER NOT NULL REFERENCES product_candidates(id),url TEXT NOT NULL,url_type TEXT NOT NULL,source TEXT NOT NULL,
        observed_at TEXT NOT NULL,UNIQUE(candidate_id,url,url_type,source))''',
        '''CREATE TABLE IF NOT EXISTS product_detection_runs (
        id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,detection_version TEXT NOT NULL,input_scope TEXT NOT NULL,
        videos_processed INTEGER NOT NULL DEFAULT 0,candidates_created INTEGER NOT NULL DEFAULT 0,candidates_updated INTEGER NOT NULL DEFAULT 0,
        evidence_created INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL,report_json TEXT NOT NULL DEFAULT '{}',config_json TEXT NOT NULL)'''
    ]
    for statement in statements:
        con.execute(statement)
    from .candidate_corroboration import migrate as migrate_corroboration
    from .candidate_gaps import migrate as migrate_gaps
    migrate_corroboration(con)
    migrate_gaps(con)
    from .product_vocabulary import migrate as migrate_vocabulary
    migrate_vocabulary(con)


def inputs(con, video):
    vid = video['id']
    creator = con.execute('SELECT c.* FROM creators c JOIN video_creators vc ON vc.creator_id=c.creator_id WHERE vc.video_id=?',(vid,)).fetchone()
    sources = []
    def add(kind, entity, key, text, at, url=None, commenter=None):
        if text:
            sources.append(dict(kind=kind,entity=entity,key=str(key),text=text,at=at,url=url or video['canonical_url'],commenter=commenter))
    for table in ('search_observations','video_detail_observations'):
        for row in con.execute(f'SELECT * FROM {table} WHERE video_id=?',(vid,)):
            fields = json.loads(row['fields_json'])
            caption = fields.get('caption')
            add('caption',table,row['id'],caption,row['observed_at'])
            for tag in re.findall(r'#[\w]+',caption or ''):
                add('hashtag',table,str(row['id'])+':'+tag,tag,row['observed_at'])
            if table == 'search_observations':
                add('search_query',table,row['id'],row['search_query'],row['observed_at'])
    if not sources:
        add('caption','videos',vid,video['caption'],video['last_seen_at'])
    for row in con.execute('SELECT * FROM comment_observations WHERE video_id=?',(vid,)):
        add('comment','comment_observations',row['comment_key'],row['text'],row['observed_at'],commenter=row['author_username'])
    if creator:
        for row in con.execute('SELECT * FROM creator_profile_observations WHERE creator_id=?',(creator['creator_id'],)):
            add('creator_bio','creator_profile_observations',row['id'],row['bio'],row['observed_at'],creator['profile_url'])
            for link in json.loads(row['links_json']):
                add('profile_link','creator_profile_observations',str(row['id'])+':'+link['url'],link.get('label') or link['url'],row['observed_at'],link['url'])
    return creator,sources


def summarize(con, cid, config):
    from .candidate_corroboration import summarize as summarize_support
    return summarize_support(con,cid,config)


def detect(con, video_id=None, latest_capture=False):
    from .product_vocabulary import augment
    config=augment(configuration(),con); now=datetime.now(timezone.utc).isoformat()
    con.execute('BEGIN IMMEDIATE')
    scope={'video_id':video_id,'latest_capture':latest_capture}
    run=con.execute('INSERT INTO product_detection_runs(created_at,detection_version,input_scope,status,config_json) VALUES (?,?,?,?,?)',
        (now,config['version'],json.dumps(scope),'running',json.dumps(config,ensure_ascii=False))).lastrowid
    con.execute('UPDATE product_detection_runs SET vocabulary_version=? WHERE id=?',(config['vocabulary_version'],run))
    videos=con.execute('SELECT * FROM videos WHERE (? IS NULL OR id=?) ORDER BY id',(video_id,video_id)).fetchall()
    if latest_capture:
        latest=con.execute('SELECT capture_id FROM search_captures ORDER BY observed_at DESC LIMIT 1').fetchone()
        ids={r[0] for r in con.execute('SELECT video_id FROM search_observations WHERE capture_id=?',(latest[0],))} if latest else set()
        videos=[v for v in videos if v['id'] in ids]
    created=set(); touched=set(); supported=set(); evidence_created=0
    for video in videos:
        creator,sources=inputs(con,video)
        cid_creator=creator['creator_id'] if creator else None
        matches=[(s,p) for s in sources if s['kind'] not in ('profile_link','search_query')
                 for p in extractProductCandidatePhrases(re.sub(r'#[\w]+','',s['text']) if s['kind']=='caption' else s['text'],config)]
        # Short comment nouns support an existing, unambiguous video hypothesis only.
        # They never create a new standalone name or merge different phrases.
        names={p['normalized_phrase'] for _,p in matches}
        for s in sources:
            if s['kind']!='comment':
                continue
            eligible=[]
            for name in names:
                for term in config['comment_support_terms'].get(name,[]):
                    match=re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)',s['text'],re.I)
                    if match:
                        eligible.append((name,match.group()))
            if len({name for name,_ in eligible})==1 and not any(existing is s for existing,_ in matches):
                name,raw=eligible[0]
                matches.append((s,dict(raw_phrase=raw,normalized_phrase=name,detected_language=None)))
        for source,phrase in matches:
            normalized=phrase['normalized_phrase']
            row=con.execute('SELECT id FROM product_candidates WHERE platform=? AND normalized_name=?',('tiktok',normalized)).fetchone()
            if row:
                cid=row[0]
            else:
                cid=con.execute('INSERT INTO product_candidates(platform,canonical_name,normalized_name,status,confidence,first_seen_at,last_seen_at,primary_reference_url,detection_version) VALUES (?,?,?,?,?,?,?,?,?)',
                    ('tiktok',phrase['raw_phrase'],normalized,'observed',0,source['at'],source['at'],video['canonical_url'],config['version'])).lastrowid
                created.add(cid)
            touched.add(cid); supported.add(video['id'])
            con.execute('UPDATE product_candidates SET first_seen_at=min(first_seen_at,?),last_seen_at=max(last_seen_at,?) WHERE id=?',(source['at'],source['at'],cid))
            con.execute('INSERT OR IGNORE INTO product_candidate_aliases VALUES (?,?,?,?,?,?,?)',(cid,phrase['raw_phrase'],normalize(phrase['raw_phrase']),source['kind'],config['evidence_weights'][source['kind']],source['at'],phrase['detected_language']))
            contextual=[s for s in sources if s['kind']=='profile_link' or (s['kind']=='search_query' and normalized in normalize(s['text']))]
            for s in [source,*contextual]:
                key=hashlib.sha256(json.dumps([cid,s['kind'],s['entity'],s['key'],video['id'],s['text']],ensure_ascii=False).encode()).hexdigest()
                weight=config['confidence_caps']['context'] if s['kind']=='profile_link' else config['evidence_weights'][s['kind']]
                cur=con.execute('INSERT OR IGNORE INTO product_candidate_evidence(candidate_id,evidence_type,source_entity_type,source_entity_id,video_id,creator_id,commenter,source_url,raw_text,extracted_text,confidence,observed_at,extractor_version,dedup_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (cid,s['kind'],s['entity'],s['key'],video['id'],cid_creator,s['commenter'],s['url'],s['text'],None if s['kind']=='profile_link' else phrase['raw_phrase'],weight,s['at'],config['version'],key))
                evidence_created+=cur.rowcount
                url_type='external' if s['kind']=='profile_link' else 'video' if s['kind']!='creator_bio' else 'creator_profile'
                con.execute('INSERT OR IGNORE INTO candidate_reference_urls VALUES (?,?,?,?,?)',(cid,s['url'],url_type,'creator_profile_link' if s['kind']=='profile_link' else s['kind'],s['at']))
            con.execute('INSERT OR IGNORE INTO candidate_reference_urls VALUES (?,?,?,?,?)',(cid,video['canonical_url'],'video','library',source['at']))
            if creator:
                con.execute('INSERT OR IGNORE INTO candidate_reference_urls VALUES (?,?,?,?,?)',(cid,creator['profile_url'],'creator_profile','observed_creator',source['at']))
        con.execute('''INSERT INTO product_video_detection_state VALUES (?,?,?) ON CONFLICT(video_id)
            DO UPDATE SET detected_at=excluded.detected_at,vocabulary_version=excluded.vocabulary_version''',
            (video['id'],now,config['vocabulary_version']))
    # Recalibrate retained hypotheses too; no evidence, aliases or URLs are removed.
    for row in con.execute('SELECT id FROM product_candidates').fetchall():
        summarize(con,row['id'],config)
    from .candidate_corroboration import discover_relationships,relationships
    from .candidate_gaps import analyze_gaps
    discover_relationships(con,config,now)
    gaps=analyze_gaps(con,videos,run,config,now)
    from .candidate_semantics import refresh as refresh_semantics
    refresh_semantics(con)
    from .product_identity_resolver import resolve as resolve_identity
    identity_report=resolve_identity(con)
    items=records(con)
    selected=[c for c in items if c['id'] in touched]
    n=len(videos); count=len(selected)
    supported={v['id'] for v in videos}-{g['video_id'] for g in gaps['detection_gaps']}
    report=dict(run_id=run,videos_processed=n,candidates_created=len(created),candidates_updated=len(touched-created),evidence_created=evidence_created,
        candidates_corroborated=sum(c['status']=='corroborated' for c in selected),videos_without_candidate=n-len(supported),
        unique_creators=len({e['creator_id'] for c in selected for e in c['evidence'] if e['creator_id'] is not None}),
        evidence_count=sum(c['evidence_count'] for c in selected),candidate_detection_rate=len(supported)/n if n else 0,
        candidates_per_video=count/n if n else 0,evidence_per_candidate=sum(c['evidence_count'] for c in selected)/count if count else 0,
        videos_per_candidate=sum(c['unique_video_count'] for c in selected)/count if count else 0,
        creators_per_candidate=sum(c['unique_creator_count'] for c in selected)/count if count else 0)
    edges=relationships(con)
    report.update(gaps)
    report['vocabulary_version']=config['vocabulary_version']
    report['legacy_corroborated_count']=sum(c['status']=='corroborated' for c in items)
    report['identity_resolver']={k:v for k,v in identity_report.items() if k not in ('pairs','possible_matches','top_5')}
    report['semantic_status_counts']={status:sum(c.get('semantic_status')==status for c in items)
        for status in ('observed','concept_recurring','possible_same_product','product_matched')}
    report.update(candidates_total=len(items),related_candidate_pairs=len({(r['candidate_a'],r['candidate_b']) for r in edges}),
                  relationship_count=len(edges),corroboration_version=config['corroboration_version'],
                  independent_video_counts={str(c['id']):c['independent_video_count'] for c in items},
                  independent_creator_counts={str(c['id']):c['independent_creator_count'] for c in items})
    con.execute('UPDATE product_detection_runs SET videos_processed=?,candidates_created=?,candidates_updated=?,evidence_created=?,status=?,report_json=? WHERE id=?',
        (n,len(created),len(touched-created),evidence_created,'succeeded',json.dumps(report),run))
    return report


def records(con, candidate_id=None):
    items=[]
    for row in con.execute('SELECT * FROM product_candidates WHERE (? IS NULL OR id=?) ORDER BY last_seen_at DESC,id DESC',(candidate_id,candidate_id)):
        item=dict(row); item.update(json.loads(item.pop('summary_json')))
        item['broad_concept']=bool(item.get('broad_concept',False))
        for key,table in [('aliases','product_candidate_aliases'),('evidence','product_candidate_evidence'),('urls','candidate_reference_urls')]:
            item[key]=[dict(r) for r in con.execute(f'SELECT * FROM {table} WHERE candidate_id=?',(item['id'],))]
        from .candidate_corroboration import relationships
        item['relationships']=relationships(con,item['id'])
        from .candidate_semantics import public_fields
        item['legacy_status']=item['status']
        item['legacy_confidence']=item['confidence']
        item.update(public_fields(con,item['id']))
        from .product_identity_resolver import records as identity_records
        item['resolver_pairs']=identity_records(con,item['id'])
        item['possible_identity_matches']=sum(p['semantic_result']=='possible_same_product' for p in item['resolver_pairs'])
        items.append(item)
    return items
