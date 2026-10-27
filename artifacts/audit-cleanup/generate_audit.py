"""Offline, read-only project audit. Writes only this newly generated audit directory."""
import ast
import collections
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
INV=json.loads((OUT/'inventory.json').read_text(encoding='utf-8'))
FILES=INV['files']
BY={x['path']:x for x in FILES}
TEXT_EXT={'.py','.pyw','.js','.cjs','.mjs','.ts','.tsx','.html','.css','.json','.md','.txt','.toml','.yaml','.yml','.sql','.ini','.cfg','.example','.csv'}
EXCLUDED={'.venv','venv','node_modules','.git','__pycache__','.pytest_cache','.mypy_cache','.next','dist','build','.runtime','browser-profiles','downloads'}
SECRET_NAME=re.compile(r'(^\.env$|\.pem$|\.key$|\.p12$|\.pfx$|dev_config\.js$|\.auth\.json$|storage-state|credentials|secrets?\.|cookies|login data|local state)',re.I)
DB_EXT={'.db','.sqlite','.sqlite3'}
def size(n):return f'{n/1024**2:,.2f} MiB ({n:,} bytes)'
def write(name,value):
 p=OUT/name;p.write_text(value,encoding='utf-8')
def jsonout(name,value):write(name,json.dumps(value,ensure_ascii=False,indent=2))
def refs(term,corpus,exclude=None):
 return [f'{p}:{text[:m.start()].count(chr(10))+1}' for p,text in corpus.items() if p!=exclude and (m:=re.search(r'(?<![\w])'+re.escape(term)+r'(?![\w])',text))]

# Never read profile/cookie/credential contents. The inventory includes only path/stat.
corpus={}
for r in FILES:
 p=Path(r['path'])
 if p.parts[0] not in ('app','extension','scripts','tests','docs','config') and len(p.parts)>1:continue
 if set(p.parts)&EXCLUDED or SECRET_NAME.search(p.name) or p.suffix not in TEXT_EXT or r['size']>4*1024**2:continue
 try:corpus[r['path']]=(ROOT/p).read_text(encoding='utf-8-sig')
 except (OSError,UnicodeError):pass

# Static evidence, not execution/import of application modules.
trees={};functions=collections.defaultdict(list);imports=collections.defaultdict(list)
for path,text in corpus.items():
 if Path(path).suffix not in ('.py','.pyw'):continue
 try:tree=ast.parse(text);trees[path]=tree
 except SyntaxError:continue
 for node in ast.walk(tree):
  if isinstance(node,ast.Import):
   for x in node.names:imports[x.name.split('.')[0]].append(f'{path}:{node.lineno}')
  if isinstance(node,ast.ImportFrom):
   if not node.level and node.module:imports[node.module.split('.')[0]].append(f'{path}:{node.lineno}')
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and len(list(ast.walk(node)))>=20:
   clone=ast.parse(ast.unparse(node)).body[0];clone.name='_FUNCTION_';clone.decorator_list=[]
   if clone.body and isinstance(clone.body[0],ast.Expr) and isinstance(clone.body[0].value,ast.Constant) and isinstance(clone.body[0].value.value,str):clone.body=clone.body[1:]
   digest=hashlib.sha256(ast.dump(clone,include_attributes=False).encode()).hexdigest()
   functions[digest].append({'location':f'{path}:{node.lineno}','name':node.name})
scripts=[];modules=[];endpoints=[]
for path,tree in trees.items():
 stem=Path(path).stem
 if path.startswith('scripts/'):
  scripts.append({'path':path,'entrypoint':"__main__" in corpus[path],'references':refs(stem,corpus,path),'status':'NO_STATIC_CALLSITE_FOUND' if not refs(stem,corpus,path) else 'REFERENCED'})
 if path.startswith('app/') and stem!='__init__':
  rr=refs(stem,corpus,path);modules.append({'path':path,'references':rr,'status':'NO_STATIC_REFERENCE_FOUND' if not rr else 'REFERENCED'})
 for node in ast.walk(tree):
  if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
  for d in node.decorator_list:
   if not (isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr in ('get','post','put','delete','patch') and d.args and isinstance(d.args[0],ast.Constant) and isinstance(d.args[0].value,str)):continue
   route=d.args[0].value;literal=route.split('{')[0].rstrip('/')
   consumers=[f'{p}:{t[:m.start()].count(chr(10))+1}' for p,t in corpus.items() if p!=path and literal and (m:=re.search(re.escape(literal),t))]
   endpoints.append({'location':f'{path}:{node.lineno}','method':d.func.attr.upper(),'declared_path':route,'consumers':consumers,'certainty':'substring heuristic; router prefixes/dynamic clients may hide consumers'})
jsonout('STATIC_REFERENCES.json',{'scripts':scripts,'modules':modules,'endpoints':endpoints,'duplicate_function_bodies':[v for v in functions.values() if len(v)>1]})

# Duplicate hashing outside installations, private profiles and git; budget bounded.
groups=collections.defaultdict(list)
for r in FILES:
 p=Path(r['path'])
 if p.parts[0] in ('.venv','node_modules','.git','browser-profiles') or 'audit-cleanup' in p.parts or r['size']==0:continue
 if SECRET_NAME.search(p.name) or r['size']>64*1024**2:continue
 groups[r['size']].append(r)
hashed=0;duplicates=[];skipped=0
for length,rows in sorted(groups.items()):
 if len(rows)<2:continue
 if hashed+length*len(rows)>512*1024**2:skipped+=len(rows);continue
 buckets=collections.defaultdict(list)
 for r in rows:
  try:
   h=hashlib.sha256()
   with (ROOT/r['path']).open('rb') as f:
    for block in iter(lambda:f.read(1024**2),b''):h.update(block)
   hashed+=length;buckets[h.hexdigest()].append(r['path'])
  except OSError:skipped+=1
 for digest,paths in buckets.items():
  if len(paths)>1:duplicates.append({'sha256':digest,'size_each':length,'recoverable_if_one_retained':length*(len(paths)-1),'paths':paths})
jsonout('DUPLICATES.json',{'algorithm':'SHA256','hashed_bytes':hashed,'skipped_files_budget_or_error':skipped,'excluded_from_hashing':['.venv','node_modules','.git','browser-profiles','secrets','files >64 MiB'],'groups':duplicates})

# Immutable read-only SQLite: no WAL/SHM writes, no application startup/migrations.
schema=[];dbinfo=[]
for r in FILES:
 p=Path(r['path'])
 if p.suffix.lower() not in DB_EXT or p.parts[0] in EXCLUDED:continue
 entry={'path':r['path'],'size':r['size'],'tables':[]};schema.append('\n-- DATABASE: '+r['path']+'\n-- immutable read-only base file; uncheckpointed WAL is not included.\n')
 try:
  con=sqlite3.connect((ROOT/p).as_uri()+'?mode=ro&immutable=1',uri=True)
  con.execute('PRAGMA query_only=ON')
  for kind,name,sql in con.execute("SELECT type,name,sql FROM sqlite_master WHERE type IN ('table','index','trigger','view') ORDER BY type,name").fetchall():
   if sql:schema.append(sql+';\n')
   if kind=='table':
    count=con.execute('SELECT count(*) FROM "'+name.replace('"','""')+'"').fetchone()[0]
    entry['tables'].append({'table':name,'count':count});schema.append(f'-- ROW COUNT {name}: {count}\n')
  con.close()
 except sqlite3.Error as e:entry['error']=type(e).__name__;schema.append('-- unreadable: '+type(e).__name__+'\n')
 dbinfo.append(entry)
write('DB_SCHEMA.txt',''.join(schema));jsonout('DATABASE_INVENTORY.json',dbinfo)

# Direct declared dependencies only. Transitives remain represented by lock/metadata.
mapping={'Pillow':'PIL','open_clip_torch':'open_clip','faiss-cpu':'faiss'}
dependency=[]
for path in sorted(ROOT.glob('requirements*.txt')):
 for line in path.read_text().splitlines():
  m=re.match(r'^([A-Za-z0-9_-]+)(?:\[[^]]+\])?',line)
  if not m:continue
  name=m[1];module=mapping.get(name,name.replace('-','_'));locations=imports.get(module,[])
  runtime=[x for x in locations if not x.startswith('tests/')]
  status='DEV ONLY' if name=='pytest' or (locations and not runtime) else 'USED' if locations else 'POSSIBLY UNUSED'
  try:installed=importlib.metadata.version(name)
  except importlib.metadata.PackageNotFoundError:installed='not installed'
  dependency.append({'name':name,'declaration':path.name,'requirement':line,'installed':installed,'classification':status,'evidence':locations,'note':'Optional intelligence/model pipeline; not necessary for search-only mode' if name in ('torch','torchvision','open_clip_torch','faiss-cpu','numpy') else 'Static imports only; transitive/dynamic use can exist'})
package=json.loads((ROOT/'package.json').read_text());dependency.append({'name':'linkedom','classification':'DEV ONLY','declaration':'package.json devDependencies','evidence':refs('linkedom',corpus)})
jsonout('DEPENDENCIES.json',dependency)
write('DEPENDENCIES.txt','Declared dependencies and static evidence (no installs/removals):\n'+json.dumps(dependency,indent=2)+'\n\nInstalled distributions (metadata only):\n'+'\n'.join(sorted(f'{d.metadata["Name"]}=={d.version}' for d in importlib.metadata.distributions())))

# Per-file classification. Legacy/unused is never inferred solely from absence of refs.
def classify(r):
 p=Path(r['path']);parts=p.parts;name=p.name.lower();suffix=p.suffix.lower()
 if '.git' in parts:return 'KEEP'
 if parts[0]=='browser-profiles':return 'RUNTIME'
 if parts[0]=='.runtime':return 'RUNTIME'
 if any(x in parts for x in ('__pycache__','.pytest_cache','.mypy_cache','.next')):return 'CACHE'
 if parts[0] in ('.venv','node_modules'):return 'GENERATED'
 if suffix in DB_EXT:
  return 'BACKUP' if parts[0]=='artifacts' or 'pre_' in name or 'checkpoint' in name else 'KEEP'
 if any(s in name for s in ('.bak','.backup','.old','~')):return 'BACKUP'
 if parts[0] in ('app','extension','config') or len(parts)==1 and suffix in ('.py','.json','.txt','.toml'):return 'CORE'
 if parts[0] in ('scripts','tests','docs') or name in ('readme.md','agents.md','.gitignore'):return 'KEEP'
 if parts[0]=='artifacts':return 'GENERATED'
 if parts[0]=='data' and suffix in ('.faiss','.npy','.npz'):return 'GENERATED'
 if parts[0]=='data' and suffix in ('.bin','.pt','.pth','.safetensors'):return 'KEEP'
 if parts[0]=='data' and suffix in TEXT_EXT:return 'GENERATED'
 return 'UNKNOWN'
for r in FILES:r['classification']=classify(r)
jsonout('FILE_CLASSIFICATION.json',{'method':'Structural classification; LEGACY/DUPLICATE require separate evidence. DUPLICATES.json lists exact matches, not automatic removal. UNKNOWN retained.','files':FILES})
exts=collections.defaultdict(lambda:{'count':0,'size':0})
for r in FILES:
 e=Path(r['path']).suffix.lower() or '[no extension]';exts[e]['count']+=1;exts[e]['size']+=r['size']
jsonout('EXTENSIONS.json',dict(sorted(exts.items(),key=lambda x:-x[1]['size'])))

# Disjoint candidate groups; excludes browser caches while Chrome may be active.
def candidate_bucket(r):
 p=Path(r['path']);parts=p.parts
 if parts[0] in ('browser-profiles','.git') or SECRET_NAME.search(p.name):return 'DO NOT DELETE'
 if r['classification']=='CACHE':return 'SAFE TO DELETE'
 if parts[0]=='.runtime' and len(parts)>1 and parts[1].startswith('dashboard-ui-test-'):return 'PROBABLY SAFE'
 if r['classification']=='BACKUP' or parts[0] in ('.runtime',) or (parts[0]=='data' and r['classification']=='GENERATED') or parts[0]=='artifacts':return 'REVIEW FIRST'
 return 'DO NOT DELETE'
totals={key:{'count':0,'size':0} for key in ('SAFE TO DELETE','PROBABLY SAFE','REVIEW FIRST','DO NOT DELETE')}
candidates=[]
for r in FILES:
 bucket=candidate_bucket(r);totals[bucket]['count']+=1;totals[bucket]['size']+=r['size']
 # Group bytecode dirs at first cache directory; otherwise immediate relevant unit.
 parts=Path(r['path']).parts
 cache=next((i for i,p in enumerate(parts) if p in ('__pycache__','.pytest_cache','.mypy_cache','.next')),None)
 if cache is not None:unit='/'.join(parts[:cache+1])
 elif parts[0] in ('.runtime','artifacts','data') and len(parts)>2:unit='/'.join(parts[:2])
 elif parts[0] in ('.venv','node_modules','browser-profiles','.git','app','extension','scripts','tests','docs','config'):unit=parts[0]
 else:unit=r['path']
 candidates.append((bucket,unit,r))
grouped={}
for bucket,unit,r in candidates:
 key=(bucket,unit)
 if key not in grouped:grouped[key]={'path':unit,'size':0,'files':0,'bucket':bucket}
 grouped[key]['size']+=r['size'];grouped[key]['files']+=1
for (bucket,unit),item in grouped.items():
 if bucket=='SAFE TO DELETE':reason='Bytecode/test/type cache; no authoritative records';risk='low; stop relevant process first; next run slower';regen='yes'
 elif bucket=='PROBABLY SAFE':reason='Isolated dashboard UI test Chrome profile; confirm no live process owns it';risk='medium if active; loses test diagnostics';regen='yes'
 elif bucket=='REVIEW FIRST':reason='Checkpoint/history/runtime/generated output; unique audit and incident evidence may exist';risk='medium/high; confirm retention, references and reproducibility';regen='unknown (historical observations often no)'
 else:reason='Source/tests/config, installed dependency, active profile, signing key or persistent DB';risk='high; breaks function or loses identity/data';regen='no/unknown; environment only via controlled reinstall'
 item.update(reason=reason,risk=risk,generated_again=regen,used_by_code='yes' if bucket=='DO NOT DELETE' and unit in ('app','extension','config','.venv','node_modules','browser-profiles') else 'unknown',referenced_by_tests='yes' if unit in ('app','extension','tests') else 'unknown',references=refs(Path(unit).name,corpus)[:8])
jsonout('CLEANUP_CANDIDATES.json',{'totals':totals,'groups':list(grouped.values()),'no_deletions':True})
lines=['# Cleanup candidates\n','Nenhum arquivo foi removido ou movido. Tamanhos lógicos; grupos são disjuntos. Ausência de referência não prova desuso. SAFE exige processo relevante parado. Caches dentro do perfil Chrome ficam DO NOT DELETE nesta auditoria.\n']
for bucket in totals:
 lines+=['\n## '+bucket+'\n',f"{totals[bucket]['count']} arquivos; {size(totals[bucket]['size'])}.\n",'| Path | Size / files | Reason | Risk | Generated again? | Used by code? | Tests? |','|---|---:|---|---|---|---|---|']
 for item in sorted((v for v in grouped.values() if v['bucket']==bucket),key=lambda v:-v['size']):lines.append(f"| `{item['path']}` | {size(item['size'])} / {item['files']} | {item['reason']} | {item['risk']} | {item['generated_again']} | {item['used_by_code']} | {item['referenced_by_tests']} |")
write('CLEANUP_CANDIDATES.md','\n'.join(lines))

storage=['# Storage audit\n',f"TOTAL: {size(INV['total'])}; {len(FILES)} arquivos. Snapshot inicial; não inclui os novos relatórios/ZIP. Tamanho lógico, não espaço alocado NTFS. Sem seguir symlinks/reparse points conhecidos. Erros de leitura: {len(INV['errors'])}.\n",'## Top 50 files\n','| Path | Size | Class |','|---|---:|---|']
for r in sorted(FILES,key=lambda r:-r['size'])[:50]:storage.append(f"| `{r['path']}` | {size(r['size'])} | {r['classification']} |")
storage+=['\n## Top 30 directories (recursive; overlap, do not sum)\n','| Path | Size |','|---|---:|']
for p,n in sorted(INV['directories'].items(),key=lambda x:-x[1])[:30]:storage.append(f'| `{p}` | {size(n)} |')
storage+=['\n## File extensions\n','| Extension | Files | Size |','|---|---:|---:|']
for ext,x in sorted(exts.items(),key=lambda x:-x[1]['size']):storage.append(f"| `{ext}` | {x['count']} | {size(x['size'])} |")
storage+=['\n## Categories (overlapping diagnostics; do not sum)\n']
patterns={'caches':lambda r:r['classification']=='CACHE' or '/Cache/' in r['path'] or '/Code Cache/' in r['path'],'databases':lambda r:Path(r['path']).suffix in DB_EXT,'WAL/SHM':lambda r:r['path'].endswith(('-wal','-shm')),'models':lambda r:Path(r['path']).suffix in ('.bin','.pt','.pth','.safetensors','.tflite','.onnx'),'screenshots/images':lambda r:Path(r['path']).suffix.lower() in ('.png','.jpg','.jpeg','.webp','.gif'),'logs':lambda r:Path(r['path']).suffix.lower() in ('.log','.log.1') or '/logs/' in r['path'],'backups':lambda r:r['classification']=='BACKUP','embeddings/indexes':lambda r:Path(r['path']).suffix in ('.faiss','.npy','.npz')}
for label,predicate in patterns.items():
 rows=[r for r in FILES if predicate(r)];storage.append(f'- {label}: {len(rows)} files, {size(sum(r["size"] for r in rows))}.')
storage+=['\n## Hash duplicates\n',f'Hashed {size(hashed)} in bounded non-installation scope; {len(duplicates)} exact duplicate groups. See DUPLICATES.json. Duplicate bytes are not automatically waste: fixtures, checkpoints and isolated profiles can intentionally match. Installation/profile duplicates were not scanned.\n']
for group in sorted(duplicates,key=lambda x:-x['recoverable_if_one_retained'])[:25]:storage.append(f"- {size(group['recoverable_if_one_retained'])} theoretical: "+', '.join('`'+p+'`' for p in group['paths']))
write('STORAGE_AUDIT.md','\n'.join(storage))

dead=['# Static code and dependency audit\n','Evidence is static, conservative and not proof of removability. Runtime plugin registration, CLI entry points, templates and external API clients are not fully resolved. No modules imported, no servers started, no requests submitted.\n','## Scripts with no known static caller\n']
for x in scripts:
 if not x['references']:dead.append(f"- `{x['path']}`: no filename/stem reference in app/extension/scripts/tests/docs/config/root text. CLI entry point={x['entrypoint']}. REVIEW FIRST, not confirmed dead.")
dead+=['\n## Modules with no known static reference\n']
for x in modules:
 if not x['references']:dead.append('- `'+x['path']+'`: no stem reference outside itself; REVIEW FIRST.')
dead+=['\n## Endpoint consumer gaps\n','Declared paths below may have APIRouter prefixes or dynamic consumers. Absence of literal match does not justify API removal. Full endpoint/consumer locations in STATIC_REFERENCES.json.\n']
for x in endpoints:
 if not x['consumers']:dead.append(f"- `{x['location']}` {x['method']} `{x['declared_path']}`: no literal consumer found.")
dead+=['\n## Exact normalized Python function bodies\n','Function names/decorators/docstrings ignored; >=20 AST nodes. Shared helpers and test stubs are expected.\n']
for group in functions.values():
 if len(group)>1:dead.append('- '+'; '.join(f"`{x['location']}` ({x['name']})" for x in group))
dead+=['\n## Dependencies\n']
for d in dependency:dead.append(f"- {d['name']}: **{d['classification']}**. Evidence: "+', '.join(d['evidence'][:8])+'. '+d.get('note',''))
dead+=['\nNo dependency is confirmed removable solely from a missing direct import. torchvision may be needed by open_clip transitively; optional ML is not equivalent to unused code. Keep requirements and lockfiles.\n']
write('CODE_AUDIT.md','\n'.join(dead))

# Export git metadata without diff bodies/untracked content or remotes/credentials.
for name,args in [('GIT_STATUS.txt',['git','status','--short']),('GIT_DIFF_STAT.txt',['git','diff','--stat'])]:
 result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace');write(name,result.stdout+result.stderr)
print(json.dumps({'inventory_files':len(FILES),'total_bytes':INV['total'],'candidate_totals':totals,'duplicates':len(duplicates),'dbs':len(dbinfo),'scripts_without_references':[x['path'] for x in scripts if not x['references']],'modules_without_references':[x['path'] for x in modules if not x['references']],'dependencies':[{k:x[k] for k in ('name','classification')} for x in dependency]},indent=2))
