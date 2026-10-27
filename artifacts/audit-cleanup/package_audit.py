"""Build a sanitized text-only review package; never modify source files."""
import collections,hashlib,json,os,re,zipfile
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
ZIP=OUT/'BABI_ARCHITECTURE_AUDIT.zip'
EXT={'.py','.pyw','.js','.cjs','.mjs','.ts','.tsx','.html','.css','.json','.md','.txt','.toml','.yaml','.yml','.sql','.ini','.cfg','.example','.csv'}
DENY={'.venv','venv','node_modules','.git','__pycache__','.pytest_cache','.mypy_cache','.next','dist','build','.runtime','browser-profiles','downloads','data'}
PRIVATE=re.compile(r'(^\.env$|\.pem$|\.key$|\.p12$|\.pfx$|dev_config\.js$|\.auth\.json$|storage-state|credentials|secrets?\.|cookies|login data|local state)',re.I)
KEYS=re.compile(r'^(?:token|access_token|refresh_token|id_token|api_key|apikey|secret|client_secret|password|passwd|authorization|cookie|cookies|set-cookie|x-ph-dev-token|x-api-key|private_key|credential|credentials)$',re.I)
known=[]
try:
 config=json.loads((ROOT/'.runtime/dev.json').read_text());known.extend(v for k,v in config.items() if KEYS.fullmatch(k) and isinstance(v,str) and len(v)>8)
except (OSError,ValueError):pass
def sanitize(text,suffix):
 for value in known:text=text.replace(value,'[REDACTED_LOCAL_CREDENTIAL]')
 if suffix=='.json':
  try:
   def walk(x):
    if isinstance(x,dict):return {k:'[REDACTED]' if KEYS.fullmatch(k) else walk(v) for k,v in x.items()}
    if isinstance(x,list):return [walk(v) for v in x]
    return x
   text=json.dumps(walk(json.loads(text)),ensure_ascii=False,indent=2)
  except ValueError:pass
 text=re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9_.~+/=-]{16,}',r'\1[REDACTED]',text)
 text=re.sub(r'(?i)([?&](?:token|access_token|refresh_token|auth|signature|x-bogus|mstoken|x-amz-signature|x-goog-signature)=)[^\s"\'<>;&]+',r'\1[REDACTED]',text)
 text=re.sub(r'(?i)((?:api[_-]?key|client_secret|password|access_token|refresh_token|x-ph-dev-token)\s*[=:]\s*["\'])([^"\'\r\n]{12,})(["\'])',r'\1[REDACTED]\3',text)
 text=re.sub(r'(?i)(https?://)[^/\s:@]+:[^/\s@]+@',r'\1[REDACTED]@',text)
 text=re.sub(r'(?<![A-Za-z0-9_-])(?:sk-[A-Za-z0-9_-]{24,}|ghp_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16})','[REDACTED_KEY_PATTERN]',text)
 text=re.sub(r'eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}','[REDACTED_JWT]',text)
 text=re.sub(r'(?i)((?:sessionid|sid_tt|ttwid|msToken)\s*[=:]\s*["\']?)[A-Za-z0-9_%+/=-]{20,}',r'\1[REDACTED_COOKIE]',text)
 return text
entries={};redactions=[];excluded=collections.Counter();excluded_examples=[]
for base,dirs,names in os.walk(ROOT,followlinks=False):
 dirs[:]=[d for d in dirs if d not in DENY and not (Path(base)/d).is_symlink()]
 for name in names:
  path=Path(base)/name;rel=path.relative_to(ROOT).as_posix()
  if path.is_symlink() or path==ZIP:continue
  if path.parent==OUT and name in ('PACKAGE_VALIDATION.json','FILES.txt','TREE.txt'):continue
  reason=''
  if PRIVATE.search(name):reason='credential/private filename'
  elif path.suffix.lower() not in EXT and name not in ('.gitignore','.env.example'):reason='binary/media/non-text type'
  elif path.stat().st_size>8*1024**2:reason='large text over 8 MiB'
  elif path.suffix.lower()=='.log':reason='log'
  if reason:
   excluded[reason]+=1;excluded_examples.append({'path':rel,'reason':reason});continue
  try:raw=path.read_text(encoding='utf-8-sig')
  except (OSError,UnicodeError):excluded['unreadable/non UTF8']+=1;continue
  if '-----BEGIN PRIVATE KEY-----' in raw or '-----BEGIN RSA PRIVATE KEY-----' in raw:
   excluded['private key marker']+=1;continue
  clean=sanitize(raw,path.suffix.lower())
  if clean!=raw:redactions.append(rel)
  entries[rel]=clean.encode('utf-8')

# Required metadata is available at ZIP root as well as in its report directory.
for name in ('DB_SCHEMA.txt','GIT_STATUS.txt','GIT_DIFF_STAT.txt','DEPENDENCIES.txt'):
 entries[name]=sanitize((OUT/name).read_text(encoding='utf-8'),'.txt').encode()
included=sorted([*entries,'FILES.txt','TREE.txt','PACKAGE_POLICY.json'])
manifest='Audit ZIP entries (UTF-8 text only). No database rows/files or browser state.\n'
manifest+='\n'.join(f'{p}\t{len(entries.get(p,b""))}\t{hashlib.sha256(entries[p]).hexdigest() if p in entries else "generated metadata"}' for p in included)+'\n'
tree='BABI AUDIT PACKAGE (only included files; full storage inventory in artifacts/audit-cleanup/inventory.json)\n'
tree_paths=set(included)
for path in included:
 for parent in Path(path).parents:
  if str(parent)!='.':tree_paths.add(parent.as_posix()+'/')
tree+='\n'.join('  '*p.rstrip('/').count('/')+p.rstrip('/').rsplit('/',1)[-1]+('/' if p.endswith('/') else '') for p in sorted(tree_paths))+'\n'
(OUT/'FILES.txt').write_text(manifest,encoding='utf-8');(OUT/'TREE.txt').write_text(tree,encoding='utf-8')
entries['FILES.txt']=manifest.encode();entries['TREE.txt']=tree.encode()
policy={'created_at':datetime.now(timezone.utc).isoformat(),'purpose':'Architecture/code review, not a runnable identity/session backup','excluded_directories':sorted(DENY),'excluded_files':excluded_examples,'excluded_counts':dict(excluded),'sanitized_copy_paths':redactions,'sanitization':'Known local credential replacement; JSON sensitive keys; bearer/signature/query credentials. Original files unchanged. Some fixtures/reports may intentionally differ after redaction.','database':'DDL and row counts only, no rows/files; immutable read-only schema export','images':'All image/video/model/index binaries excluded, including referenced UI logos/fixtures. Paths may remain in source.','data_directory':'Excluded entirely; schemas and counts exported separately','secrets_scan':'Heuristic plus known dev credential match; not an assertion of formal secret-detector completeness'}
entries['PACKAGE_POLICY.json']=json.dumps(policy,indent=2).encode()
with zipfile.ZipFile(ZIP,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for name,content in sorted(entries.items()):z.writestr(name,content)
with zipfile.ZipFile(ZIP) as z:
 assert z.testzip() is None
 names=z.namelist();assert len(names)==len(set(names))
 for name in names:
  assert not (set(Path(name).parts)&DENY) and not PRIVATE.search(Path(name).name)
  assert Path(name).suffix.lower() not in ('.db','.sqlite','.sqlite3','.pem','.png','.jpg','.bin','.zip','.faiss','.log')
  content=z.read(name)
  for value in known:assert value.encode() not in content
  assert b'-----BEGIN PRIVATE KEY-----' not in content and b'-----BEGIN RSA PRIVATE KEY-----' not in content
 stat={'path':str(ZIP.relative_to(ROOT)),'size':ZIP.stat().st_size,'files':len(entries),'uncompressed_size':sum(map(len,entries.values())),'sha256':hashlib.sha256(ZIP.read_bytes()).hexdigest(),'sanitized_files':len(redactions),'zip_crc':'PASS','known_local_credential_scan':'PASS','excluded_path_type_check':'PASS'}
(OUT/'PACKAGE_VALIDATION.json').write_text(json.dumps(stat,indent=2),encoding='utf-8')
print(json.dumps(stat,indent=2))
