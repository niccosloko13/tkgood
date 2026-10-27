"""Lazy local OpenCLIP embeddings, hash cache and cross-process CPU governor.

No downloads occur here. An operator installs a pinned checkpoint separately.
Image bytes must come from the existing validated local asset reader.
"""
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import threading
import time
import gc
from .intelligence_decisions import settings

ROOT = Path(__file__).resolve().parents[1]


class ResourceBusy(RuntimeError):
    pass


class ModelUnavailable(RuntimeError):
    pass


class ResourceGovernor:
    def state(self):
        import psutil
        p = settings()['resources']
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        available=memory.available/1048576
        loaded=bool(globals().get('provider') and provider.model is not None)
        budget=p.get('inference_available_mb',p['min_available_mb']) if loaded else p['min_available_mb']
        critical=available<p.get('stop_available_mb',256) or memory.percent>=p.get('stop_ram_percent',98.5)
        allowed=not critical and cpu<p['max_cpu_percent'] and available>=budget
        state='STOP' if critical else 'RUN' if allowed else 'WAIT' if cpu>=p['max_cpu_percent'] else 'DEFER'
        return {'allowed':allowed,'cpu_percent':cpu,'ram_percent':memory.percent,
                'available_mb':round(available),'state':state,'required_available_mb':budget,
                'reason':'INCREMENTAL_BUDGET_AVAILABLE' if allowed else 'CRITICAL_MEMORY' if critical else 'RESOURCE_COOLDOWN',
                'cooldown_seconds':p.get('cooldown_seconds',20),'device':getattr(globals().get('provider'),'device','unprobed'),
                'gpu_workload':'probed_lazily',
                'concurrency_limit':p['concurrency']}

    @contextmanager
    def reserve(self):
        state = self.state()
        if not state['allowed']: raise ResourceBusy('RESOURCE_PRESSURE')
        directory = ROOT/'data/intelligence'
        directory.mkdir(parents=True,exist_ok=True)
        with (directory/'heavy.lock').open('a+b') as handle:
            if handle.tell()==0:
                handle.write(b'0');handle.flush()
            handle.seek(0)
            try:
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except (OSError,BlockingIOError) as exc:
                raise ResourceBusy('HEAVY_WORK_ALREADY_RUNNING') from exc
            try: yield state
            finally:
                handle.seek(0)
                if os.name=='nt':msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(handle,fcntl.LOCK_UN)


class OpenCLIPProvider:
    def __init__(self):
        self.model = self.preprocess = self.tokenizer = None
        self.cache_hits = 0
        self._lock = threading.Lock()
        self.device='cpu'
        self.last_used=None
        self._idle_timer=None
        self.last_inference=None
        self.runtime_probe=None

    def unload(self,only_if_idle=False):
        with self._lock:
            if only_if_idle and (self.last_used is None or time.monotonic()-self.last_used<settings()['resources']['idle_unload_seconds']):return
            self.model=self.preprocess=self.tokenizer=None
            import sys
            torch=sys.modules.get('torch')
            if torch is not None and self.device.startswith('cuda'):
                torch.cuda.empty_cache()
            gc.collect()

    def _idle_unload(self):
        if self.last_used is None:return
        remaining=settings()['resources']['idle_unload_seconds']-(time.monotonic()-self.last_used)
        if remaining>0:
            # Windows timers may wake early; a single early wake must not leave
            # the model resident forever.
            self._idle_timer=threading.Timer(remaining,self._idle_unload)
            self._idle_timer.daemon=True;self._idle_timer.start()
        else:self.unload(only_if_idle=True)

    def _schedule_unload(self):
        self.last_used=time.monotonic()
        if self._idle_timer:self._idle_timer.cancel()
        self._idle_timer=threading.Timer(settings()['resources']['idle_unload_seconds'],self._idle_unload)
        self._idle_timer.daemon=True;self._idle_timer.start()

    def _select_device(self,torch):
        device='cpu';reason='CUDA_RUNTIME_UNAVAILABLE'
        if getattr(self,'_force_cpu',False):
            self.runtime_probe={'device':'cpu','reason':'GPU_FAILURE_CPU_FALLBACK'}
            return 'cpu'
        try:available=bool(getattr(torch.version,'cuda',None) and torch.cuda.is_available())
        except RuntimeError:available=False;reason='GPU_PROBE_FAILED_CPU_FALLBACK'
        if available:
            try:
                free,total=torch.cuda.mem_get_info()
                if free/1048576>=settings()['resources']['gpu_min_free_mb']:
                    allocation=torch.empty(256,device='cuda');torch.cuda.synchronize();del allocation
                    device='cuda';reason='SMALL_ALLOCATION_PASSED'
                else:reason='GPU_MEMORY_INSUFFICIENT_CPU_FALLBACK'
            except (RuntimeError,MemoryError):reason='GPU_ALLOCATION_FAILED_CPU_FALLBACK'
        self.runtime_probe={'device':device,'reason':reason}
        return device

    @contextmanager
    def _memory_guard(self):
        try:yield
        except (MemoryError,RuntimeError) as exc:
            if not isinstance(exc,MemoryError) and not any(s in str(exc).lower() for s in ('out of memory','allocat')):raise
            self._force_cpu=self.device.startswith('cuda')
            self.model=self.preprocess=self.tokenizer=None
            gc.collect()
            if self._force_cpu:
                import torch
                try:torch.cuda.empty_cache()
                except RuntimeError:pass
            raise ResourceBusy('INFERENCE_MEMORY_DEFERRED') from exc

    @property
    def version(self):
        p = settings()['embedding']
        path = ROOT/p['checkpoint']
        if not path.is_file(): raise ModelUnavailable('LOCAL_CHECKPOINT_MISSING')
        # Memoize only while file size/mtime remain unchanged.
        stamp = (path.stat().st_size,path.stat().st_mtime_ns)
        if getattr(self,'_stamp',None)!=stamp:
            self._digest = hashlib.file_digest(path.open('rb'),'sha256').hexdigest() if hasattr(hashlib,'file_digest') else self._hash(path)
            self._stamp = stamp
        if p.get('sha256') and self._digest!=p['sha256']:raise ModelUnavailable('LOCAL_CHECKPOINT_HASH_MISMATCH')
        return p['version']+':'+self._digest

    @staticmethod
    def _hash(path):
        digest=hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda:handle.read(1048576),b''):digest.update(block)
        return digest.hexdigest()

    def _load(self):
        if self.model is not None:return
        from importlib.metadata import version
        p = settings()['embedding']
        if version('open_clip_torch')!=p['package_version']:raise ModelUnavailable('EMBEDDING_PACKAGE_VERSION_MISMATCH')
        if not (ROOT/p['checkpoint']).is_file():raise ModelUnavailable('LOCAL_CHECKPOINT_MISSING')
        import torch
        import open_clip
        torch.set_num_threads(settings()['resources']['threads'])
        self.device=self._select_device(torch)
        try:
            # Official PyTorch mmap/meta/assign recipe avoids two resident copies
            # of the pinned fp32 weights. No random-weight inference is permitted.
            with torch.device('meta'):
                model,_,preprocess=open_clip.create_model_and_transforms(p['model'],pretrained=None,device='meta')
            weights=torch.load(str(ROOT/p['checkpoint']),map_location='cpu',weights_only=True,mmap=True)
            state=weights.get('state_dict',weights)
            model.load_state_dict(state,strict=True,assign=True)
            if getattr(model,'attn_mask',None) is not None and model.attn_mask.is_meta:
                model.attn_mask=torch.full((model.context_length,model.context_length),float('-inf'),device='cpu').triu_(1)
            if any(t.is_meta for t in [*model.parameters(),*model.buffers()]):raise ModelUnavailable('UNMATERIALIZED_MODEL_TENSOR')
            self.model=model.to(self.device);self.preprocess=preprocess
            del weights,state
        except (RuntimeError,MemoryError) as exc:
            if self.device=='cpu':
                if isinstance(exc,MemoryError) or any(s in str(exc).lower() for s in ('out of memory','allocat')):
                    raise ResourceBusy('MODEL_LOAD_DEFERRED') from exc
                raise ModelUnavailable('LOCAL_MODEL_LOAD_FAILED: '+str(exc)) from exc
            self.device='cpu';torch.cuda.empty_cache();gc.collect()
            self.model,_,self.preprocess=open_clip.create_model_and_transforms(p['model'],pretrained=str(ROOT/p['checkpoint']),device='cpu')
        self.model.eval()
        self.tokenizer = open_clip.get_tokenizer(p['model'])
        self.loaded_version = self.version

    def embed(self,con,kind,value):
        if kind not in ('image','text'):raise ValueError('Unsupported embedding kind')
        if kind=='text' and (not isinstance(value,str) or not value.strip()):raise ValueError('Nonempty text required')
        raw=value.encode() if kind=='text' else value
        digest=hashlib.sha256(raw).hexdigest()
        version=self.version
        row=con.execute('SELECT vector_json FROM intelligence_embeddings WHERE version=? AND kind=? AND sha256=?',(version,kind,digest)).fetchone()
        if row:
            self.cache_hits+=1
            con.execute("UPDATE intelligence_cache_stats SET hits=hits+1 WHERE id=1")
            self.last_inference={'kind':kind,'sha256':digest,'model_version':version,'device':self.device,'duration_ms':0,'dimension':len(json.loads(row[0])),'cache_status':'hit','model_loaded_during_inference':False}
            return json.loads(row[0])
        with self._lock, ResourceGovernor().reserve(), self._memory_guard():
            started=time.monotonic()
            self._load()
            if self.loaded_version!=version:raise ModelUnavailable('CHECKPOINT_CHANGED_RESTART_LOCAL_WORKER')
            import torch
            from PIL import Image
            with torch.inference_mode():
                if kind=='text':
                    tokens=self.tokenizer([value])
                    if hasattr(tokens,'to'):tokens=tokens.to(self.device)
                    vector=self.model.encode_text(tokens,normalize=True)[0]
                else:
                    with Image.open(io.BytesIO(raw)) as image:
                        tensor=self.preprocess(image.convert('RGB')).unsqueeze(0)
                    vector=self.model.encode_image(tensor.to(self.device),normalize=True)[0]
            result=vector.cpu().float().tolist()
            self.last_inference={'kind':kind,'sha256':digest,'model_version':version,'device':self.device,'duration_ms':round((time.monotonic()-started)*1000,2),'dimension':len(result),'cache_status':'miss','model_loaded_during_inference':self.model is not None}
            self._schedule_unload()
        from .intelligence_jobs import now
        con.execute('INSERT OR IGNORE INTO intelligence_embeddings(version,kind,sha256,vector_json,observed_at) VALUES (?,?,?,?,?)',(version,kind,digest,json.dumps(result),now()))
        return result


provider = OpenCLIPProvider()  # No model, torch, numpy or faiss loaded on import.
