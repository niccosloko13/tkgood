"""Search-only publication-time evidence. Never infers dates from TikTok IDs."""
import re,json
from datetime import datetime,timezone

def migrate(c):
    c.execute('''CREATE TABLE IF NOT EXISTS search_recency_evidence (
      observation_id INTEGER PRIMARY KEY REFERENCES search_observations(id),published_at TEXT,
      age_hours REAL,recency_bucket TEXT NOT NULL,recency_source TEXT NOT NULL,
      recency_confidence TEXT NOT NULL,evidence_text TEXT,computed_at TEXT NOT NULL)''')

def bucket(age):
    if age is None:return 'UNKNOWN'
    if age<6:return '<6h'
    if age<12:return '6-12h'
    if age<24:return '12-24h'
    if age<48:return '24-48h'
    if age<72:return '48-72h'
    return '>72h'

def explicit_age(text):
    # Only standalone, human-visible relative-age markers; IDs/counters never qualify.
    m=re.search(r'(?<!\d)(\d{1,3})\s*(h|hr|hrs|hora|horas|d|dia|dias|w|semana|semanas)\s*(?:ago|atrás)?\b',text or '',re.I)
    if not m:return None
    value=float(m.group(1));unit=m.group(2).lower()
    return value*(24 if unit.startswith('d') or unit.startswith('sem') or unit=='w' else 168 if unit=='w' else 1)

def reprocess(c,mission_id):
    migrate(c); rows=c.execute("SELECT o.id,o.raw_visible_text,o.card_snapshot,o.observed_at FROM search_observations o JOIN bridge_commands b ON o.capture_id='command:'||b.id WHERE json_extract(b.options_json,'$.mission_contract_id')=?",(mission_id,)).fetchall(); counts={}
    for r in rows:
        raw=' '.join(x or '' for x in (r['raw_visible_text'],r['card_snapshot']))
        age=explicit_age(raw); stamp=datetime.now(timezone.utc).isoformat(); b=bucket(age)
        c.execute('INSERT INTO search_recency_evidence VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(observation_id) DO UPDATE SET published_at=excluded.published_at,age_hours=excluded.age_hours,recency_bucket=excluded.recency_bucket,recency_source=excluded.recency_source,recency_confidence=excluded.recency_confidence,evidence_text=excluded.evidence_text,computed_at=excluded.computed_at',(r['id'],None,age,b,'SEARCH_CARD_VISIBLE_RELATIVE_TIME' if age is not None else 'NONE','HIGH' if age is not None else 'NONE',raw[:500] if age is not None else None,stamp));counts[b]=counts.get(b,0)+1
    return len(rows),counts
