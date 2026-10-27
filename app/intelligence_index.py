"""Immutable FAISS generations with a single atomic manifest switch.

The generation contains the index, mapping and checksum. Readers verify bytes
before deserialization and keep their manifest snapshot throughout a search.
"""
import hashlib
import json
import os
from pathlib import Path
import uuid
from .intelligence_jobs import now


class ProductIndex:
    def __init__(self,directory='data/intelligence/product-index'):
        self.directory=Path(directory)

    def rebuild(self,entries,version,dimension=512,validate_hook=None,source_hash=None):
        import numpy as np
        import faiss
        keys=[e.get('reference_id',e.get('product_id')) for e in entries]
        if None in keys or len(set(keys))!=len(entries):raise ValueError('Duplicate or missing reference IDs')
        vectors=np.asarray([e['vector'] for e in entries],dtype='float32') if entries else np.empty((0,dimension),dtype='float32')
        if vectors.ndim!=2 or vectors.shape[1]!=dimension or not np.isfinite(vectors).all():raise ValueError('Invalid embedding matrix')
        if len(entries) and (np.linalg.norm(vectors,axis=1)==0).any():raise ValueError('Zero embedding')
        faiss.normalize_L2(vectors)
        index=faiss.IndexFlatIP(dimension);index.add(vectors)
        self.directory.mkdir(parents=True,exist_ok=True)
        generation=uuid.uuid4().hex
        temporary=self.directory/(generation+'.tmp');temporary.mkdir()
        path=temporary/'index.faiss';faiss.write_index(index,str(path))
        check=faiss.read_index(str(path))
        if check.ntotal!=len(entries) or check.d!=dimension:raise ValueError('Index validation failed')
        if validate_hook:validate_hook(check)
        metadata={'generation':generation,'embedding_version':version,'observed_at':now(),'dimension':dimension,'source_hash':source_hash,
                  'product_ids':[e.get('product_id') for e in entries], 'kinds':[e.get('kind','image') for e in entries],
                  'references':[{'reference_id':key,'reference_kind':e.get('reference_kind','PRODUCT_ENTITY'),'name':e.get('name'), 'source':e.get('source',{})} for key,e in zip(keys,entries)],
                  'vectors':len(entries),'entities':sum(e.get('reference_kind','PRODUCT_ENTITY')=='PRODUCT_ENTITY' for e in entries),
                  'occurrences':sum(e.get('reference_kind')=='CONFIRMED_OCCURRENCE' for e in entries),
                  'candidate_references':sum(e.get('reference_kind')=='CANDIDATE_REFERENCE' for e in entries),
                  'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        (temporary/'metadata.json').write_text(json.dumps(metadata),encoding='utf-8')
        # Flush all generation contents before publishing the pointer.
        for file in temporary.iterdir():
            with file.open('r+b') as handle:os.fsync(handle.fileno())
        os.replace(temporary,self.directory/generation)
        pointer=self.directory/(generation+'.pointer.tmp')
        with pointer.open('w',encoding='utf-8') as handle:
            json.dump({'generation':generation},handle);handle.flush();os.fsync(handle.fileno())
        os.replace(pointer,self.directory/'current.json')
        return metadata

    def metadata(self):
        pointer=self.directory/'current.json'
        if not pointer.exists():return None
        generation=json.loads(pointer.read_text(encoding='utf-8'))['generation']
        if not generation.isalnum():raise ValueError('Unsafe generation')
        metadata=json.loads((self.directory/generation/'metadata.json').read_text(encoding='utf-8'))
        if metadata['generation']!=generation:raise ValueError('Generation mismatch')
        return metadata

    def search(self,vector,version):
        import faiss
        import numpy as np
        m=self.metadata()
        if m is None:return []
        if m['embedding_version']!=version:raise ValueError('Embedding version mismatch; rebuild required')
        path=self.directory/m['generation']/'index.faiss'
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=m['sha256']:raise ValueError('Index checksum mismatch')
        index=faiss.deserialize_index(np.frombuffer(raw,dtype='uint8'))
        if index.ntotal!=len(m['product_ids']) or index.d!=m['dimension']:raise ValueError('Index metadata mismatch')
        query=np.asarray([vector],dtype='float32')
        if query.shape!=(1,index.d) or not np.isfinite(query).all() or np.linalg.norm(query)==0:raise ValueError('Invalid query')
        faiss.normalize_L2(query)
        scores,ids=index.search(query,min(3,index.ntotal)) if index.ntotal else ([],[])
        return [{**(m.get('references') or [{'reference_id':p,'reference_kind':'PRODUCT_ENTITY'} for p in m['product_ids']])[int(i)],'product_id':m['product_ids'][int(i)],'embedding_kind':m.get('kinds',['image']*index.ntotal)[int(i)],'similarity':float(s),'embedding_version':version,'index_version':m['generation'],'observed_at':now()}
                for s,i in zip(scores[0],ids[0])] if index.ntotal else []
