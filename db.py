import logging
import os
import re
import hashlib
import psycopg2
import psycopg2.extras

global DB
DB = dict()

def connect():
    global DB
    url = os.environ.get('DATABASE_URL')
    c = psycopg2.connect(url)
    c.autocommit = False
    DB['conn'] = c
    DB['cursor'] = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    logging.info('Connected to PostgreSQL')

def execute(sql, args=None):
    global DB
    sql = re.sub(r'\s+', ' ', sql)
    sql = sql.replace('?', '%s')
    logging.info('SQL: {} Args: {}'.format(sql, args))
    try:
        DB['cursor'].execute(sql, args) if args else DB['cursor'].execute(sql)
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        logging.info('Reconectando...')
        connect()
        DB['cursor'].execute(sql, args) if args else DB['cursor'].execute(sql)
    return DB['cursor']

def close():
    global DB
    DB['conn'].close()

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def create_tables():
    execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id       SERIAL PRIMARY KEY,
            nome     TEXT NOT NULL,
            email    TEXT UNIQUE NOT NULL,
            senha    TEXT NOT NULL,
            aprovado INTEGER DEFAULT 0,
            admin    INTEGER DEFAULT 0,
            data     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
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
    DB['conn'].commit()
