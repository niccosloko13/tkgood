"""Explicit one-time official checkpoint download; never imported by backend.

Pinned revision and LFS SHA verified before atomic publish. No TikTok hosts.
"""
from pathlib import Path
import hashlib
import os
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.intelligence_decisions import settings


def main():
    from huggingface_hub import hf_hub_download
    p=settings()['embedding']
    source=Path(hf_hub_download(p['repository'],'open_clip_pytorch_model.bin',revision=p['revision']))
    from app.intelligence_embeddings import OpenCLIPProvider
    if OpenCLIPProvider._hash(source)!=p['sha256']:raise ValueError('Official checkpoint hash mismatch')
    destination=Path(p['checkpoint']);destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix('.download.tmp')
    shutil.copyfile(source,temporary)
    with temporary.open('r+b') as handle:os.fsync(handle.fileno())
    os.replace(temporary,destination)
    print('Verified local checkpoint:',p['sha256'])


if __name__=='__main__':main()
