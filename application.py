from flask import Flask, render_template, request, redirect, abort, session, flash
import db

APP = Flask(__name__)
APP.secret_key = 'ruralmarket_secret_2024'

def usuario_atual():
    uid = session.get('user_id')
    if not uid:
        return None
    return db.execute('SELECT * FROM usuarios WHERE id = ?', [uid]).fetchone()

@APP.route('/')
def index():
    return redirect('/anuncios')

@APP.route('/anuncios')
def lista():
    q         = request.args.get('q', '').strip()
    categoria = request.args.get('categoria', '')
    preco_max = request.args.get('preco_max', '')

    sql  = 'SELECT * FROM anuncios WHERE 1=1'
    args = []

    if q:
        sql += ' AND (titulo LIKE ? OR descricao LIKE ? OR localizacao LIKE ?)'
        args += [f'%{q}%', f'%{q}%', f'%{q}%']
    if categoria:
        sql += ' AND categoria = ?'
        args.append(categoria)
    if preco_max:
        sql += ' AND preco <= ?'
        args.append(float(preco_max))

    sql += ' ORDER BY data DESC'
    anuncios = db.execute(sql, args if args else None).fetchall()
    return render_template('anuncios-lista.html', anuncios=anuncios,
                           user=usuario_atual(), q=q,
                           categoria=categoria, preco_max=preco_max)

import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/fotos'
ALLOWED = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED

@APP.route('/publicar', methods=['GET', 'POST'])
def publicar():
    user = usuario_atual()
    if not user or not user['aprovado']:
        abort(403)
    if request.method == 'POST':
        foto_nome = None
        if 'foto' in request.files:
            f = request.files['foto']
            if f and f.filename and allowed_file(f.filename):
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                foto_nome = secure_filename(f.filename)
                f.save(os.path.join(UPLOAD_FOLDER, foto_nome))

        db.execute(
            '''INSERT INTO anuncios
               (titulo, descricao, preco, categoria, localizacao, contacto, foto)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (request.form['titulo'], request.form['descricao'],
             request.form['preco'], request.form['categoria'],
             request.form['localizacao'], request.form['contacto'],
             foto_nome)
        )
        db.DB['conn'].commit()
        return redirect('/anuncios')
    return render_template('publicar.html', user=user)
    
@APP.route('/anuncio/<int:id>')
def detalhe(id):
    anuncio = db.execute('SELECT * FROM anuncios WHERE id = ?', [id]).fetchone()
    if anuncio is None:
        abort(404, f'Anuncio {id} nao existe.')
    return render_template('anuncio.html', a=anuncio, user=usuario_atual())

@APP.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nome  = request.form['nome']
        email = request.form['email']
        senha = db.hash_senha(request.form['senha'])

        existente = db.execute('SELECT id FROM usuarios WHERE email = ?', [email]).fetchone()
        if existente:
            flash('Este email ja esta registado.')
            return render_template('registro.html')

        total = db.execute('SELECT COUNT(*) FROM usuarios').fetchone()['count']
        es_admin = 1 if total == 0 else 0

        db.execute(
            'INSERT INTO usuarios (nome, email, senha, aprovado, admin) VALUES (?, ?, ?, ?, ?)',
            (nome, email, senha, es_admin, es_admin)
        )
        db.DB['conn'].commit()

        if not es_admin:
            flash('Conta registada. Aguarda aprovacao do administrador.')
        return redirect('/login')

    return render_template('registro.html')

@APP.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = db.hash_senha(request.form['senha'])
        user = db.execute(
    '''SELECT * FROM usuarios 
       WHERE (email = %s OR nome = %s) AND senha = %s''',
    [email, email, senha]
).fetchone()
        if not user:
            flash('Email ou senha incorretos.')
            return render_template('login.html')
        session['user_id'] = user['id']
        return redirect('/anuncios')
    return render_template('login.html')

@APP.route('/logout')
def logout():
    session.clear()
    return redirect('/anuncios')

@APP.route('/admin')
def admin():
    user = usuario_atual()
    if not user or not user['admin']:
        abort(403)
    usuarios = db.execute('SELECT * FROM usuarios ORDER BY data DESC').fetchall()
    return render_template('admin.html', usuarios=usuarios, user=user)

@APP.route('/admin/aprovar/<int:id>')
def aprovar(id):
    user = usuario_atual()
    if not user or not user['admin']:
        abort(403)
    db.execute('UPDATE usuarios SET aprovado = 1 WHERE id = ?', [id])
    db.DB['conn'].commit()
    return redirect('/admin')

@APP.route('/admin/revogar/<int:id>')
def revogar(id):
    user = usuario_atual()
    if not user or not user['admin']:
        abort(403)
    db.execute('UPDATE usuarios SET aprovado = 0 WHERE id = ?', [id])
    db.DB['conn'].commit()
    return redirect('/admin')

@APP.route('/admin/tornar_admin/<int:id>')
def tornar_admin(id):
    user = usuario_atual()
    if not user or not user['admin']:
        abort(403)
    db.execute('UPDATE usuarios SET admin = 1, aprovado = 1 WHERE id = ?', [id])
    db.DB['conn'].commit()
    return redirect('/admin')

@APP.route('/admin/borrar/<int:id>')
def borrar(id):
    db.execute('DELETE FROM anuncios WHERE id = ?', [id])
    db.DB['conn'].commit()
    return redirect('/anuncios')
