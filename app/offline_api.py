from fastapi import APIRouter
from .db import connect
from .offline_intelligence import audit

router=APIRouter(prefix='/api/offline-intelligence')

@router.get('')
def insights():
    with connect() as con:
        con.execute('PRAGMA query_only=ON')
        return audit(con)
