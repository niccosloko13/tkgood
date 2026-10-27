"""Explicit local vocabulary decisions; no automatic product learning."""
import re


def migrate(con):
    con.execute('''CREATE TABLE IF NOT EXISTS product_vocabulary_terms (
        normalized_phrase TEXT PRIMARY KEY,raw_phrase TEXT NOT NULL,active INTEGER NOT NULL,updated_at TEXT NOT NULL)''')
    con.execute('CREATE TABLE IF NOT EXISTS product_vocabulary_state (id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL)')
    con.execute('INSERT OR IGNORE INTO product_vocabulary_state VALUES (1,1)')
    columns={r['name'] for r in con.execute('PRAGMA table_info(product_detection_runs)')}
    if 'vocabulary_version' not in columns:
        con.execute("ALTER TABLE product_detection_runs ADD COLUMN vocabulary_version TEXT NOT NULL DEFAULT 'product-vocabulary-v1'")


def version(con):
    return 'product-vocabulary-v'+str(con.execute('SELECT revision FROM product_vocabulary_state WHERE id=1').fetchone()[0])


def apply_decision(con, phrase, decision, at):
    normalized=phrase['normalized_phrase'];active=decision=='approved'
    previous=con.execute('SELECT active FROM product_vocabulary_terms WHERE normalized_phrase=?',(normalized,)).fetchone()
    changed=(bool(previous[0]) if previous else False)!=active
    con.execute('''INSERT INTO product_vocabulary_terms VALUES (?,?,?,?) ON CONFLICT(normalized_phrase)
        DO UPDATE SET active=excluded.active,updated_at=excluded.updated_at''',(normalized,phrase['raw_phrase'],int(active),at))
    if changed:
        con.execute('UPDATE product_vocabulary_state SET revision=revision+1 WHERE id=1')
    return changed


def augment(config, con):
    config={**config,'product_patterns':list(config['product_patterns']),'vocabulary_version':version(con)}
    for row in con.execute('SELECT normalized_phrase FROM product_vocabulary_terms WHERE active=1 ORDER BY normalized_phrase'):
        config['product_patterns'].append(r'[\s_-]+'.join(re.escape(token) for token in row[0].split()))
    return config
