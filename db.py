import logging
import sqlite3
import re
import hashlib

global DB
DB = dict()

def connect():
    global DB
    c = sqlite3.connect('anuncios.db', check_same_thread=False)
    c.row_factory = sqlite3.Row
    DB['conn'] = c
    DB['cursor'] = c.cursor()
    logging.info('Connected to database')

def execute(sql, args=None):
    global DB
    sql = re.sub(r'\s+', ' ', sql)
    logging.info('SQL: {} Args: {}'.format(sql, args))
    return DB['cursor'].execute(sql, args) \
        if args is not None else DB['cursor'].execute(sql)

def create_tables():
    execute('''
        CREATE TABLE IF NOT EXISTS anuncios (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo      TEXT NOT NULL,
            descricao   TEXT,
            preco       REAL,
            categoria   TEXT,
            localizacao TEXT,
            contacto    TEXT,
            foto        TEXT,
            data        DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    try:
        execute('ALTER TABLE anuncios ADD COLUMN foto TEXT')
        DB['conn'].commit()
    except:
        pass

    execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            nome     TEXT NOT NULL,
            email    TEXT NOT NULL UNIQUE,
            senha    TEXT NOT NULL,
            aprovado INTEGER DEFAULT 0,
            admin    INTEGER DEFAULT 0,
            data     DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    DB['conn'].commit()

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()


def close():
    global DB
    DB['conn'].close()

# Inicializar a base de dados ao importar o módulo
connect()
create_tables()
