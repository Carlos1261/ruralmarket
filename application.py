from flask import Flask, render_template, request, redirect, abort, session, flash
import db
import os
import secrets
import re

APP = Flask(__name__)
APP.secret_key = os.environ.get('SECRET_KEY', 'ruralmarket_secret_2024')

UPLOAD_FOLDER    = 'static/fotos'
ALLOWED_EXT      = {'png', 'jpg', 'jpeg', 'webp'}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_FOTOS        = 15                 # máximo de fotos por anúncio
MAGIC = [
    (b'\xff\xd8\xff', 'jpg'),
    (b'\x89PNG\r\n',  'png'),
    (b'RIFF',         'webp'),
]
LIMITES = {
    'titulo': 120, 'descricao': 2000,
    'localizacao': 120, 'contacto': 80,
    'nome': 80, 'email': 120,
}

# ── CSRF ───────────────────────────────────────────────────────────────────────
def gerar_csrf():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validar_csrf():
    tok = session.get('csrf_token', '')
    if not tok or not secrets.compare_digest(tok, request.form.get('csrf_token', '')):
        abort(403, 'Token de segurança inválido. Recarrega a página.')

APP.jinja_env.globals['csrf_token'] = gerar_csrf

# ── HEADERS ────────────────────────────────────────────────────────────────────
@APP.after_request
def headers_seguranca(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options']        = 'DENY'
    response.headers['X-XSS-Protection']       = '1; mode=block'
    response.headers['Referrer-Policy']        = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "script-src 'self' 'unsafe-inline';"
    )
    return response

# ── VALIDAÇÃO ──────────────────────────────────────────────────────────────────
def campo(nome, valor, obrigatorio=True):
    valor = (valor or '').strip()
    if obrigatorio and not valor:
        flash(f'O campo "{nome}" é obrigatório.')
        return None
    limite = LIMITES.get(nome)
    if limite and len(valor) > limite:
        flash(f'O campo "{nome}" não pode ter mais de {limite} caracteres.')
        return None
    return valor

def preco_valido(valor):
    try:
        p = float(valor)
        if p < 0 or p > 9_999_999:
            raise ValueError
        return p
    except (ValueError, TypeError):
        flash('O preço deve ser um número positivo.')
        return None

def email_valido(e):
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', e):
        flash('Endereço de email inválido.')
        return None
    return e

# ── UPLOAD ─────────────────────────────────────────────────────────────────────
def guardar_foto(f):
    """Guarda uma foto e devolve o nome do ficheiro, ou None se inválido."""
    if not f or not f.filename:
        return None
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext not in ALLOWED_EXT:
        flash('Formato inválido. Usa JPG, PNG ou WebP.')
        return None
    cabecalho = f.stream.read(12)
    f.stream.seek(0)
    if not any(cabecalho.startswith(m) for m, _ in MAGIC):
        flash('O ficheiro não é uma imagem válida.')
        return None
    f.stream.seek(0, 2)
    if f.stream.tell() > MAX_UPLOAD_BYTES:
        flash('Cada imagem não pode ter mais de 5 MB.')
        return None
    f.stream.seek(0)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    nome = f'{secrets.token_hex(16)}.{ext}'
    f.save(os.path.join(UPLOAD_FOLDER, nome))
    return nome

def guardar_fotos_anuncio(anuncio_id, ficheiros, ordem_inicio=0):
    """Guarda múltiplas fotos e insere-as na tabela fotos."""
    guardadas = 0
    for i, f in enumerate(ficheiros):
        nome = guardar_foto(f)
        if nome:
            db.execute(
                'INSERT INTO fotos (anuncio_id, nome, ordem) VALUES (?, ?, ?)',
                [anuncio_id, nome, ordem_inicio + i]
            )
            guardadas += 1
    return guardadas

def fotos_do_anuncio(anuncio_id):
    """Devolve a lista de fotos de um anúncio ordenadas."""
    return db.execute(
        'SELECT * FROM fotos WHERE anuncio_id = ? ORDER BY ordem',
        [anuncio_id]
    ).fetchall()

# ── HELPER ─────────────────────────────────────────────────────────────────────
def usuario_atual():
    uid = session.get('user_id')
    if not uid:
        return None
    return db.execute('SELECT * FROM usuarios WHERE id = ?', [uid]).fetchone()

# ══════════════════════════════════════════════════════
#  ROTAS
# ══════════════════════════════════════════════════════

@APP.route('/')
def index():
    return redirect('/anuncios')


@APP.route('/anuncios')
def lista():
    q         = request.args.get('q', '').strip()[:100]
    categoria = request.args.get('categoria', '')[:60]
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
        try:
            args.append(float(preco_max))
            sql += ' AND preco <= ?'
        except ValueError:
            pass
    sql += ' ORDER BY data DESC'
    anuncios = db.execute(sql, args if args else None).fetchall()

    # Para cada anúncio, busca a primeira foto da tabela fotos (ou usa foto antiga)
    def capa(a):
        f = db.execute(
            'SELECT nome FROM fotos WHERE anuncio_id = ? ORDER BY ordem LIMIT 1',
            [a['id']]
        ).fetchone()
        return f['nome'] if f else a['foto']

    return render_template('anuncios-lista.html', anuncios=anuncios,
                           capa=capa, user=usuario_atual(),
                           q=q, categoria=categoria, preco_max=preco_max)


@APP.route('/publicar', methods=['GET', 'POST'])
def publicar():
    user = usuario_atual()
    if not user or not user['aprovado']:
        abort(403)
    if request.method == 'POST':
        validar_csrf()
        titulo      = campo('titulo',      request.form.get('titulo'))
        descricao   = campo('descricao',   request.form.get('descricao'), obrigatorio=False) or ''
        localizacao = campo('localizacao', request.form.get('localizacao'))
        contacto    = campo('contacto',    request.form.get('contacto'))
        preco       = preco_valido(request.form.get('preco'))
        categoria   = (request.form.get('categoria') or '')[:60]

        if None in (titulo, localizacao, contacto, preco) or not categoria:
            return render_template('publicar.html', user=user)

        db.execute(
            '''INSERT INTO anuncios
               (usuario_id, titulo, descricao, preco, categoria, localizacao, contacto)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user['id'], titulo, descricao, preco, categoria, localizacao, contacto)
        )
        anuncio_id = db.execute('SELECT lastval() as id').fetchone()['id']

        ficheiros = request.files.getlist('fotos')[:MAX_FOTOS]
        guardar_fotos_anuncio(anuncio_id, ficheiros)
        db.DB['conn'].commit()
        return redirect('/anuncios')
    return render_template('publicar.html', user=user)


@APP.route('/anuncio/<int:id>')
def detalhe(id):
    anuncio = db.execute('SELECT * FROM anuncios WHERE id = ?', [id]).fetchone()
    if anuncio is None:
        abort(404)
    fotos = fotos_do_anuncio(id)
    # Compatibilidade: se não há fotos novas mas há foto antiga, usa-a
    if not fotos and anuncio['foto']:
        fotos = [{'nome': anuncio['foto'], 'id': None}]
    return render_template('anuncio.html', a=anuncio, fotos=fotos, user=usuario_atual())


@APP.route('/anuncio/<int:id>/editar', methods=['GET', 'POST'])
def editar(id):
    user    = usuario_atual()
    anuncio = db.execute('SELECT * FROM anuncios WHERE id = ?', [id]).fetchone()
    if anuncio is None:
        abort(404)
    if not user or (user['id'] != anuncio['usuario_id'] and not user['admin']):
        abort(403)

    if request.method == 'POST':
        validar_csrf()
        titulo      = campo('titulo',      request.form.get('titulo'))
        descricao   = campo('descricao',   request.form.get('descricao'), obrigatorio=False) or ''
        localizacao = campo('localizacao', request.form.get('localizacao'))
        contacto    = campo('contacto',    request.form.get('contacto'))
        preco       = preco_valido(request.form.get('preco'))
        categoria   = (request.form.get('categoria') or '')[:60]

        if None in (titulo, localizacao, contacto, preco) or not categoria:
            fotos = fotos_do_anuncio(id)
            return render_template('editar.html', a=anuncio, fotos=fotos, user=user)

        # Elimina fotos marcadas para remoção
        apagar = request.form.getlist('apagar_foto')
        for foto_id in apagar:
            foto = db.execute('SELECT nome FROM fotos WHERE id = ? AND anuncio_id = ?',
                              [foto_id, id]).fetchone()
            if foto:
                try:
                    os.remove(os.path.join(UPLOAD_FOLDER, foto['nome']))
                except OSError:
                    pass
                db.execute('DELETE FROM fotos WHERE id = ?', [foto_id])

        # Conta quantas fotos já existem
        total_atual = db.execute(
            'SELECT COUNT(*) as c FROM fotos WHERE anuncio_id = ?', [id]
        ).fetchone()['c']

        # Adiciona novas fotos (sem exceder o máximo)
        ficheiros = request.files.getlist('fotos')
        disponiveis = MAX_FOTOS - total_atual
        if disponiveis > 0:
            guardar_fotos_anuncio(id, ficheiros[:disponiveis], ordem_inicio=total_atual)

        db.execute(
            '''UPDATE anuncios SET titulo=?, descricao=?, preco=?, categoria=?,
               localizacao=?, contacto=? WHERE id=?''',
            (titulo, descricao, preco, categoria, localizacao, contacto, id)
        )
        db.DB['conn'].commit()
        flash('Anúncio atualizado com sucesso!')
        return redirect(f'/anuncio/{id}')

    fotos = fotos_do_anuncio(id)
    return render_template('editar.html', a=anuncio, fotos=fotos, user=user)


@APP.route('/anuncio/<int:id>/eliminar')
def eliminar(id):
    user    = usuario_atual()
    anuncio = db.execute('SELECT * FROM anuncios WHERE id = ?', [id]).fetchone()
    if anuncio is None:
        abort(404)
    if not user or (user['id'] != anuncio['usuario_id'] and not user['admin']):
        abort(403)
    # Apaga ficheiros físicos das fotos
    fotos = fotos_do_anuncio(id)
    for f in fotos:
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, f['nome']))
        except OSError:
            pass
    db.execute('DELETE FROM anuncios WHERE id = ?', [id])
    db.DB['conn'].commit()
    flash('Anúncio eliminado.')
    return redirect('/anuncios')


@APP.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        validar_csrf()
        nome  = campo('nome',  request.form.get('nome'))
        email = campo('email', request.form.get('email'))
        senha = request.form.get('senha', '')
        if not nome or not email or not email_valido(email):
            return render_template('registro.html')
        if len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.')
            return render_template('registro.html')
        if db.execute('SELECT id FROM usuarios WHERE email = ?', [email]).fetchone():
            flash('Este email já está registado.')
            return render_template('registro.html')
        total    = db.execute('SELECT COUNT(*) as total FROM usuarios').fetchone()['total']
        es_admin = 1 if total == 0 else 0
        db.execute(
            'INSERT INTO usuarios (nome, email, senha, aprovado, admin) VALUES (?, ?, ?, ?, ?)',
            (nome, email, db.hash_senha(senha), es_admin, es_admin)
        )
        db.DB['conn'].commit()
        if not es_admin:
            flash('Conta registada. Aguarda aprovação do administrador.')
        return redirect('/login')
    return render_template('registro.html')


@APP.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        validar_csrf()
        email = (request.form.get('email') or '').strip()[:120]
        senha = db.hash_senha(request.form.get('senha', ''))
        user  = db.execute(
            'SELECT * FROM usuarios WHERE (email = ? OR nome = ?) AND senha = ?',
            [email, email, senha]
        ).fetchone()
        if not user:
            flash('Email ou senha incorretos.')
            return render_template('login.html')
        session.clear()
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
    user = usuario_atual()
    if not user or not user['admin']:
        abort(403)
    db.execute('DELETE FROM anuncios WHERE id = ?', [id])
    db.DB['conn'].commit()
    return redirect('/anuncios')

@APP.route('/admin/borrar_usuario/<int:id>')
def borrar_usuario(id):
    user = usuario_atual()
    if not user or not user['admin']:
        abort(403)
    if user['id'] == id:
        flash('Não podes eliminar a tua própria conta.')
        return redirect('/admin')
    db.execute('DELETE FROM usuarios WHERE id = ?', [id])
    db.DB['conn'].commit()
    flash('Utilizador eliminado.')
    return redirect('/admin')

@APP.route('/change-password', methods=['GET', 'POST'])
def change_password():
    user = usuario_atual()
    if not user:
        return redirect('/login')
    if request.method == 'POST':
        validar_csrf()
        senha_atual = db.hash_senha(request.form.get('senha_atual', ''))
        nova_senha  = request.form.get('nova_senha', '')
        confirmar   = request.form.get('confirmar', '')
        if senha_atual != user['senha']:
            flash('Senha atual incorreta.')
            return render_template('change_password.html', user=user)
        if len(nova_senha) < 6:
            flash('A nova senha deve ter pelo menos 6 caracteres.')
            return render_template('change_password.html', user=user)
        if nova_senha != confirmar:
            flash('As novas senhas não coincidem.')
            return render_template('change_password.html', user=user)
        db.execute('UPDATE usuarios SET senha = ? WHERE id = ?',
                   [db.hash_senha(nova_senha), user['id']])
        db.DB['conn'].commit()
        flash('Senha alterada com sucesso!')
        return redirect('/anuncios')
    return render_template('change_password.html', user=user)
