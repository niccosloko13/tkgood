"""Creator identity/history and transparent, deterministic performance indicators."""
import json
import re
from urllib.parse import urlsplit
from pathlib import Path
from .creator_schemas import profile_identity, COUNTS, TEXT_FIELDS

CONFIG_PATH = Path(__file__).resolve().parents[1]/'config/creator_signals.json'


def configuration():
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


def bucket(followers, config=None):
    if followers is None:
        return None
    for row in (config or configuration())['buckets']:
        if row['upper_exclusive'] is None or followers < row['upper_exclusive']:
            return row['name']


def ratio(numerator, denominator):
    return round(numerator/denominator, 6) if numerator is not None and denominator is not None and denominator>0 else None


def performance(evidence, followers, config=None):
    config = config or configuration()
    def verified_value(name):
        metric=evidence.get(name,{})
        return metric.get('value') if metric.get('confidence',0)>=config['minimum_metric_confidence'] else None
    result = {f'{name}_to_followers_ratio': ratio(verified_value('comments_count' if name=='comments' else name), followers)
              for name in ('views','likes','comments','shares')}
    size = bucket(followers, config)
    views, likes = result['views_to_followers_ratio'], result['likes_to_followers_ratio']
    score = None
    components = None
    if views is not None and likes is not None and size is not None:
        formula = config['score']
        components = {'views': formula['views_weight']*min(views/formula['views_ratio_cap'], 1),
                      'likes': formula['likes_weight']*min(likes/formula['likes_ratio_cap'], 1),
                      'size_bonus': next(row['bonus'] for row in config['buckets'] if row['name']==size)}
        components = {key:round(value,4) for key,value in components.items()}
        score = round(min(100,max(0,sum(components.values()))),2)
    return {**result, 'creator_size_bucket':size, 'creator_independence_score':score,
            'score_components':components, 'formula_version':config['version'],
            'score_formula':{**config['score'],'size_bonus':next((r['bonus'] for r in config['buckets'] if r['name']==size),0)}}


def term_present(value, terms):
    return any(re.search(r'(?<![a-z])'+re.escape(term)+r'(?![a-z])', value.casefold()) for term in terms)


def profile_signals(fields, links, config=None):
    config = config or configuration()
    text = ' '.join(link['url']+' '+(link.get('label') or '') for link in links)
    followers = fields.get('followers')
    return {'has_external_link': any(urlsplit(link['url']).hostname not in ('www.tiktok.com','tiktok.com') or urlsplit(link['url']).path in ('/link','/link/v2') for link in links),
            'has_commercial_link':term_present(text,config['commercial_terms']),
            'has_shop_signal':term_present(text,config['shop_terms']),
            'follower_count':followers,'total_likes':fields.get('total_likes'),'video_count':fields.get('video_count'),
            'followers_to_video_ratio':ratio(followers,fields.get('video_count')),
            'likes_per_follower_ratio':ratio(fields.get('total_likes'),followers),
            'creator_size_bucket':bucket(followers,config),'config_version':config['version']}


def migrate(con):
    con.execute('''CREATE TABLE IF NOT EXISTS creators (
        creator_id INTEGER PRIMARY KEY AUTOINCREMENT,platform TEXT NOT NULL CHECK(platform='tiktok'),
        username TEXT NOT NULL,profile_url TEXT NOT NULL,display_name TEXT,bio TEXT,avatar_url TEXT,
        followers INTEGER,following INTEGER,total_likes INTEGER,video_count INTEGER,external_link TEXT,
        profile_category TEXT,profile_type TEXT,first_seen_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,
        extractor_version TEXT NOT NULL,field_evidence_json TEXT NOT NULL DEFAULT '{}',
        UNIQUE(platform,username),UNIQUE(platform,profile_url))''')
    con.execute('''CREATE TABLE IF NOT EXISTS video_creators (
        video_id INTEGER PRIMARY KEY REFERENCES videos(id),creator_id INTEGER NOT NULL REFERENCES creators(creator_id),
        linked_at TEXT NOT NULL,source TEXT NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS creator_profile_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,creator_id INTEGER NOT NULL REFERENCES creators(creator_id),
        command_id INTEGER NOT NULL UNIQUE,observed_at TEXT NOT NULL,followers INTEGER,following INTEGER,
        total_likes INTEGER,video_count INTEGER,bio TEXT,external_link TEXT,raw_visible_text TEXT NOT NULL,
        extractor_version TEXT NOT NULL,fields_json TEXT NOT NULL,field_evidence_json TEXT NOT NULL,
        links_json TEXT NOT NULL,signals_json TEXT NOT NULL,config_json TEXT NOT NULL)''')
    con.execute('CREATE INDEX IF NOT EXISTS creator_history ON creator_profile_observations(creator_id,id DESC)')


def link_library(con,video_ids=None):
    """Link observed usernames only; never infer an author from a video URL."""
    for video in con.execute('SELECT * FROM videos WHERE creator_username IS NOT NULL').fetchall():
        if video_ids is not None and video['id'] not in video_ids:continue
        username = video['creator_username']
        if not re.fullmatch(r'@[A-Za-z0-9._]{1,128}', username):
            continue
        provenance = json.loads(video['field_evidence_json']).get('creator_username',{})
        if not provenance.get('confidence',0)>0:
            continue
        url, username = profile_identity('https://www.tiktok.com/'+username)
        creator = con.execute('SELECT creator_id FROM creators WHERE platform=? AND (username=? OR profile_url=?)',('tiktok',username,url)).fetchone()
        if creator is None:
            cursor=con.execute('''INSERT INTO creators(platform,username,profile_url,first_seen_at,last_seen_at,extractor_version)
                VALUES ('tiktok',?,?,?,?, 'unobserved')''',(username,url,video['first_seen_at'],video['last_seen_at']))
            creator={'creator_id':cursor.lastrowid}
        else:
            con.execute('''UPDATE creators SET first_seen_at=MIN(first_seen_at,?),last_seen_at=MAX(last_seen_at,?)
                WHERE creator_id=? AND (first_seen_at>? OR last_seen_at<?)''',
                (video['first_seen_at'],video['last_seen_at'],creator['creator_id'],video['first_seen_at'],video['last_seen_at']))
        con.execute('''INSERT INTO video_creators(video_id,creator_id,linked_at,source) VALUES (?,?,?,?)
            ON CONFLICT(video_id) DO UPDATE SET creator_id=excluded.creator_id,linked_at=excluded.linked_at,source=excluded.source
            WHERE creator_id<>excluded.creator_id''',
            (video['id'],creator['creator_id'],video['last_seen_at'],provenance['source']))


def creator_for_video(con, video_url):
    from .extraction import video_identity
    video=con.execute('SELECT id FROM videos WHERE video_id=?',(video_identity(video_url)[1],)).fetchone()
    link_library(con,[video['id']] if video else [])
    return con.execute('''SELECT c.* FROM creators c JOIN video_creators r ON r.creator_id=c.creator_id
        JOIN videos v ON v.id=r.video_id WHERE v.video_id=?''',(video_identity(video_url)[1],)).fetchone()


def save_profile(con, profile, command_id, now, video_url):
    creator = creator_for_video(con,video_url)
    if creator is None or creator['profile_url']!=profile['profile_url'] or creator['username']!=profile['username'].lower():
        return False
    evidence = {key:{**value,'observed_at':now} for key,value in profile['field_evidence'].items()}
    links = [{**link,'observed_at':now} for link in profile['links']]
    config = configuration()
    signals = profile_signals(profile,links,config)
    con.execute('''INSERT INTO creator_profile_observations(creator_id,command_id,observed_at,followers,following,
        total_likes,video_count,bio,external_link,raw_visible_text,extractor_version,fields_json,
        field_evidence_json,links_json,signals_json,config_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (creator['creator_id'],command_id,now,*[profile.get(k) for k in COUNTS],profile.get('bio'),
         profile.get('external_link'),profile['raw_visible_text'],profile['extractor_version'],json.dumps(profile),
         json.dumps(evidence),json.dumps(links),json.dumps(signals),json.dumps(config)))
    # Metadata is a projection of the latest snapshot, including nulls. Older
    # nonnull values remain in immutable observations, not mixed into this row.
    best = evidence
    fields = COUNTS + TEXT_FIELDS
    con.execute('UPDATE creators SET '+','.join(f'{field}=?' for field in fields)+
                ',last_seen_at=?,extractor_version=?,field_evidence_json=? WHERE creator_id=?',
                (*[best.get(field,{}).get('value') for field in fields],now,profile['extractor_version'],json.dumps(best),creator['creator_id']))
    con.execute('INSERT INTO events(created_at,level,event_type,message) VALUES (?,?,?,?)',
                (now,'INFO','creator',f'Creator profile #{command_id} stored: {creator["username"]}; READ ONLY'))
    return True


def records(con, creator_id=None):
    link_library(con)
    config = configuration()
    rows = con.execute('SELECT * FROM creators WHERE (? IS NULL OR creator_id=?) ORDER BY creator_id',(creator_id,creator_id)).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        evidence = json.loads(item.pop('field_evidence_json'))
        latest = con.execute('SELECT * FROM creator_profile_observations WHERE creator_id=? ORDER BY id DESC LIMIT 1',(row['creator_id'],)).fetchone()
        observation = None
        if latest:
            observation = {**json.loads(latest['fields_json']), 'id':latest['id'],'command_id':latest['command_id'],
                           'observed_at':latest['observed_at'],'field_evidence':json.loads(latest['field_evidence_json']),
                           'links':json.loads(latest['links_json'])}
        # Current calculations use the latest observation, including nulls,
        # never a mixture of old follower counts and new profile fields.
        observed = observation or {}
        related = []
        for video in con.execute('SELECT v.* FROM videos v JOIN video_creators r ON r.video_id=v.id WHERE r.creator_id=? ORDER BY v.last_seen_at DESC',(row['creator_id'],)).fetchall():
            metrics = json.loads(video['field_evidence_json'])
            related.append({'video_id':video['video_id'],'video_url':video['canonical_url'],'caption':video['caption'],
                            'creator_profile_url':row['profile_url'],
                            'metric_evidence':{key:metrics.get(key) for key in ('views','likes','comments_count','shares')},
                            'followers_observed_at':latest['observed_at'] if latest else None,
                            **performance(metrics,observed.get('followers'),config)})
        item.update(field_evidence=evidence,latest_observation=observation,
                    latest_observed_at=latest['observed_at'] if latest else None,
                    observation_count=con.execute('SELECT COUNT(*) FROM creator_profile_observations WHERE creator_id=?',(row['creator_id'],)).fetchone()[0],
                    links=observation['links'] if observation else [],
                    signals=profile_signals(observed,observed.get('links',[]),config),related_videos=related)
        items.append(item)
    return {'items':items}
