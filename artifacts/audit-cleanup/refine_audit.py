"""Refine static findings after checking transitive imports and router prefixes."""
import ast,json,re
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
def load(n):return json.loads((OUT/n).read_text(encoding='utf-8'))
def save(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
data=load('DEPENDENCIES.json')
for d in data:
 if d['name']=='torchvision':
  d.update(classification='USED',evidence=['.venv/Lib/site-packages/open_clip/transform.py:9','.venv/Lib/site-packages/open_clip/utils.py:8'],note='Confirmed transitive import by open_clip; no direct app import does not mean unused.')
save('DEPENDENCIES.json',data)
p=OUT/'DEPENDENCIES.txt';text=p.read_text();text=text[:text.index('Installed distributions')];installed=p.read_text().split('Installed distributions',1)[1];p.write_text('Declared dependencies (transitive check refined):\n'+json.dumps(data,indent=2)+'\n\nInstalled distributions'+installed,encoding='utf-8')
static=load('STATIC_REFERENCES.json');corpus={}
for folder in ('app','extension','scripts','tests','docs','config'):
 for p in (ROOT/folder).rglob('*'):
  if p.suffix not in ('.py','.js','.cjs','.html','.md','.json') or '__pycache__' in p.parts or p.name=='dev_config.js':continue
  try:corpus[p.relative_to(ROOT).as_posix()]=p.read_text(encoding='utf-8-sig')
  except (UnicodeError,OSError):pass
for endpoint in static['endpoints']:
 path=endpoint['location'].rsplit(':',1)[0];text=corpus[path];prefix=''
 try:
  tree=ast.parse(text)
  for n in ast.walk(tree):
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='APIRouter':
    for k in n.keywords:
     if k.arg=='prefix' and isinstance(k.value,ast.Constant):prefix=k.value.value
 except SyntaxError:pass
 route=prefix+endpoint['declared_path'];literal=route.split('{')[0]
 if literal=='/':pattern=r'(?:href=["\']/(?:["\'])|["\']/["\'])'
 else:pattern=re.escape(literal.rstrip('/'))
 rr=[]
 if pattern:
  for p,t in corpus.items():
   if p!=path and (m:=re.search(pattern,t)):rr.append(f'{p}:{t[:m.start()].count(chr(10))+1}')
 endpoint.update(effective_path=route,consumers=rr,certainty='Includes constant APIRouter prefix; literal/dynamic-prefix evidence only, not full call graph')
save('STATIC_REFERENCES.json',static)
p=OUT/'CODE_AUDIT.md';text=p.read_text();start=text.index('## Endpoint consumer gaps');end=text.index('## Exact normalized',start)
section='## Endpoint consumer gaps (router prefixes resolved)\n\nConstant APIRouter prefixes included. Dynamic-prefix matches do not prove each verb/parameter variant is used.\n\n'
gaps=[e for e in static['endpoints'] if not e['consumers']]
for e in gaps:section+=f"- `{e['location']}` {e['method']} `{e['effective_path']}`: no literal consumer found; REVIEW FIRST.\n"
text=text[:start]+section+'\n'+text[end:];text=text.replace('torchvision: **POSSIBLY UNUSED**. Evidence: . Optional intelligence/model pipeline; not necessary for search-only mode','torchvision: **USED** transitively. Evidence: open_clip/transform.py:9 and open_clip/utils.py:8. Required by optional OpenCLIP pipeline.').replace('torchvision may be needed by open_clip transitively','torchvision is imported by open_clip transitively')
text+='\npsutil is declared in both requirements files with the same version. This is declaration duplication, not two installations and not removal authorization.\n'
p.write_text(text,encoding='utf-8')
p=OUT/'ARCHITECTURE_REVIEW.md';text=p.read_text().replace('lists 11 endpoint literal-consumer gaps','lists endpoint literal-consumer gaps after resolving constant router prefixes');p.write_text(text,encoding='utf-8')
print('remaining endpoint gaps',[(e['location'],e['effective_path']) for e in gaps])
