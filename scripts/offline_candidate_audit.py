"""Read-only SQLite audit. Never imports app/db, initializes schema or calls an API."""
import ast
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
DATABASE=ROOT/'data/product_hunter.db'


def digest(value):
    return hashlib.sha256(value).hexdigest()


def connect():
    con=sqlite3.connect(DATABASE.as_uri()+'?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    return con


def snapshot():
    with connect() as con:
        tables={}
        for row in con.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
            name=row['name'];quoted='"'+name.replace('"','""')+'"'
            rows=[json.dumps(list(r),ensure_ascii=False,sort_keys=True,default=lambda v:v.hex()) for r in con.execute('SELECT * FROM '+quoted)]
            tables[name]={'rows':len(rows),'sha256':digest('\n'.join(sorted(rows)).encode()),'schema_sha256':digest(row['sql'].encode())}
        states={r['key']:dict(r) for r in con.execute('SELECT * FROM system_state')}
        commands=[dict(r) for r in con.execute('SELECT * FROM bridge_commands ORDER BY id')]
    return {'at':datetime.now(timezone.utc).isoformat(),'file_sha256':digest(DATABASE.read_bytes()),'tables':tables,'system_state':states,'commands':commands,
      'config_sha256':{str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in (ROOT/'config').glob('*.json')},
      'test_sha256':{str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in [ROOT/'tests/test_enrichment.py',ROOT/'tests/test_backlog.py']}}


def git_recovery():
    from process_runtime import hidden_kwargs
    def git(*args):
        return subprocess.run(['git',*args],cwd=ROOT,capture_output=True,**hidden_kwargs())
    result=git('show','HEAD:tests/test_enrichment.py')
    paths=git('ls-tree','-r','--name-only','HEAD','--','tests').stdout.decode().splitlines()
    comparison=[]
    for name in paths:
        original=git('show','HEAD:'+name).stdout
        current=(ROOT/name).read_bytes()
        if name.endswith('.py'):
            def names(value):return {n.name for n in ast.walk(ast.parse(value.decode('utf-8-sig'))) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')}
        elif name.endswith('.test.cjs'):
            def names(value):return set(re.findall(r"test\(\s*(['\"])(.*?)\1",value.decode('utf-8'),re.S))
        else:continue
        before=names(original);after=names(current)
        comparison.append({'path':name,'head_tests':len(before),'current_tests':len(after),'head_tests_missing':sorted(before-after),'bytes_equal':original==current})
    return {'head':git('rev-parse','HEAD').stdout.decode().strip(),'target':'tests/test_enrichment.py','git_show_exit':result.returncode,
      'git_show_error':result.stderr.decode().strip(),'target_present_in_head':result.returncode==0,
      'target_history':git('log','--all','--format=%H','--','tests/test_enrichment.py').stdout.decode().splitlines(),
      'exact_restoration_possible_from_local_git':result.returncode==0,'tracked_test_comparison':comparison}


def audit():
    with connect() as c:
        evidence=[dict(r) for r in c.execute('SELECT * FROM product_candidate_evidence ORDER BY id')]
        candidates=[]
        for r in c.execute('SELECT * FROM product_candidates ORDER BY id'):
            row=dict(r);summary=json.loads(row.pop('summary_json'));ev=[e for e in evidence if e['candidate_id']==row['id']]
            row['summary']=summary;row['aliases']=[dict(x) for x in c.execute('SELECT * FROM product_candidate_aliases WHERE candidate_id=?',(row['id'],))]
            row['urls']=[dict(x) for x in c.execute('SELECT * FROM candidate_reference_urls WHERE candidate_id=?',(row['id'],))]
            row['evidence']=ev
            row['videos']=[dict(x) for x in c.execute('''SELECT DISTINCT v.id,v.video_id,v.canonical_url,v.caption,c.username,c.profile_url
              FROM product_candidate_evidence e JOIN videos v ON v.id=e.video_id LEFT JOIN creators c ON c.creator_id=e.creator_id WHERE e.candidate_id=?''',(row['id'],))]
            row['caption_repetitions']=sum(n-1 for n in Counter((e['video_id'],e['raw_text']) for e in ev if e['evidence_type']=='caption').values())
            row['alias_normalized_names']=sorted({x['normalized_alias'] for x in row['aliases']})
            candidates.append(row)
        unresolved=[]
        for r in c.execute('SELECT * FROM unresolved_product_phrases ORDER BY id'):
            row=dict(r);row['observations']=[dict(x) for x in c.execute('SELECT * FROM unresolved_phrase_observations WHERE phrase_id=?',(r['id'],))]
            row['video']=dict(c.execute('SELECT * FROM videos WHERE id=?',(r['video_id'],)).fetchone());unresolved.append(row)
        flags=[]
        for e in evidence:
            problems=[]
            if not e['raw_text']:problems.append('missing_raw_text')
            if not e['source_url']:problems.append('missing_source_url')
            if not e['observed_at']:problems.append('missing_observed_at')
            if not e['extractor_version']:problems.append('missing_version')
            if e['source_entity_type'] in ('search_observations','video_detail_observations','creator_profile_observations'):
                key=e['source_entity_id'].split(':')[0]
                source=c.execute('SELECT * FROM '+e['source_entity_type']+' WHERE id=?',(key,)).fetchone()
                if not source:problems.append('source_missing')
                elif e['evidence_type']=='caption' and json.loads(source['fields_json']).get('caption')!=e['raw_text']:problems.append('source_caption_mismatch')
            if problems:flags.append({'id':e['id'],'problems':problems})
        return {'at':datetime.now(timezone.utc).isoformat(),'read_only':True,'git':git_recovery(),'candidates':candidates,'unresolved_phrases':unresolved,
          'evidence_quality':{'total':len(evidence),'types':dict(Counter(e['evidence_type'] for e in evidence)),
           'source_types':dict(Counter(e['source_entity_type'] for e in evidence)),'provenance_flags':flags,
           'duplicate_dedup_keys':len(evidence)-len({e['dedup_key'] for e in evidence})},
          'stage_counts':[dict(r) for r in c.execute('SELECT step,status,count(*) AS n FROM enrichment_stages GROUP BY step,status ORDER BY step,status')],
          'batches':[dict(r) for r in c.execute('SELECT * FROM enrichment_batches ORDER BY id')],
          'integrity':c.execute('PRAGMA integrity_check').fetchone()[0],'foreign_key_errors':[tuple(r) for r in c.execute('PRAGMA foreign_key_check')]}


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1] not in ('snapshot','audit'):raise SystemExit('snapshot|audit OUTPUT_JSON')
    report=snapshot() if sys.argv[1]=='snapshot' else audit()
    Path(sys.argv[2]).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Saved offline '+sys.argv[1]+' to '+sys.argv[2])
