import logging
import re
import os
from urllib.parse import urlparse
import psycopg2
import psycopg2.extras
import hashlib

DB = dict()

def connect():
    global DB
    url = urlparse(os.environ.get('DATABASE_URL', ''))
    c = psycopg2.connect(
        host=url.hostname,
        port=url.port,
        dbname=url.path[1:],
        user=url.username,
        password=url.password,
        sslmode='require'
    )
    c.autocommit = False
    DB['conn'] = c
    DB['cursor'] = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    logging.info('Connected to database')

def execute(sql, args=None):
    global DB
    sql = re.sub(r'\?', '%s', sql)
    sql = re.sub(r'\s+', ' ', sql)
    logging.info('SQL: {} Args: {}'.format(sql, args))
    if args is not None:
        DB['cursor'].execute(sql, args)
    else:
        DB['cursor'].execute(sql)
    return DB['cursor']

def create_tables():
    execute('''
        CREATE TABLE IF NOT EXISTS anuncios (
            id          SERIAL PRIMARY KEY,
            titulo      TEXT NOT NULL,
            descricao   TEXT,
            preco       REAL,
            categoria   TEXT,
            localizacao TEXT,
            contacto    TEXT,
            foto        TEXT,
            data        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id       SERIAL PRIMARY KEY,
            nome     TEXT NOT NULL,
            email    TEXT NOT NULL UNIQUE,
            senha    TEXT NOT NULL,
            aprovado INTEGER DEFAULT 0,
            admin    INTEGER DEFAULT 0,
            data     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    DB['conn'].commit()

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def close():
    global DB
    DB['conn'].close()
