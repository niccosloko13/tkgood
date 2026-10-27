"""Local gold set export; --record adds pending rows/run only, never detector outputs."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import gold_set


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record',action='store_true')
    args=parser.parse_args();path=ROOT/'data/product_hunter.db'
    con=sqlite3.connect(path if args.record else path.as_uri()+'?mode=ro',uri=not args.record)
    con.row_factory=sqlite3.Row;con.execute('PRAGMA foreign_keys=ON')
    if args.record:
        with con:gold_set.migrate(con);report=gold_set.benchmark(con)
    else:con.execute('PRAGMA query_only=ON');report=gold_set.benchmark(con,persist=False)
    gold=gold_set.listing(con);con.close();gold_set.export_files(gold,report)
    print(json.dumps({'progress':gold['progress'],'tp':report['tp'],'fp':report['fp'],'fn':report['fn'],'tn':report['tn'],
      'precision':report['precision'],'recall':report['recall'],'f1':report['f1'],'naming_accuracy':report['product_naming_accuracy']}))


if __name__=='__main__':main()
