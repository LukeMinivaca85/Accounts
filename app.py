from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from authlib.integrations.flask_client import OAuth
import sqlite3
import random
import time
import requests
import os
import re

app = Flask(__name__)
app.secret_key = "lukintosh-secret-key"

# ================= OAUTH =================
oauth = OAuth(app)

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)

oauth.register(
    name="microsoft",
    client_id=os.getenv("MICROSOFT_CLIENT_ID"),
    client_secret=os.getenv("MICROSOFT_CLIENT_SECRET"),
    authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    access_token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
    client_kwargs={"scope": "openid email profile User.Read"}
)

# ================= SENDGRID =================
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_REMETENTE = "lucas@lukintosh.com"
REPLY_TO_EMAIL = "noreply@lukintosh.com"

# ================= DATABASE =================
def get_db():
    return sqlite3.connect("users.db")

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            sobrenome TEXT,
            email TEXT UNIQUE,
            telefone TEXT,
            endereco TEXT,
            cep TEXT,
            password TEXT,
            verified INTEGER
        )
    """)
    db.commit()
    db.close()

init_db()

# ================= VERIFICATION CODE =================
codigo_data = {}

def gerar_codigo():
    return str(random.randint(100000, 999999))

def senha_valida(senha):
    return (
        len(senha) >= 8 and
        re.search(r"[A-Z]", senha) and
        re.search(r"[a-z]", senha) and
        re.search(r"[0-9]", senha)
    )

# ================= EMAIL =================
def enviar_email(codigo, destino):
    html = f"""
    <div style="font-family:system-ui; background:#fff; color:#000; padding:24px">
      <h2>Lukintosh</h2>
      <p>Seu código de verificação:</p>
      <div style="font-size:32px; letter-spacing:6px; font-weight:600">{codigo}</div>
      <p>O código expira em 5 minutos.</p>
      <hr>
      <p style="font-size:12px">Lukintosh Corporation</p>
    </div>
    """

    body = {
        "personalizations": [{"to": [{"email": destino}]}],
        "from": {"email": EMAIL_REMETENTE},
        "reply_to": {"email": REPLY_TO_EMAIL},
        "subject": "Código de verificação – Lukintosh",
        "content": [{"type": "text/html", "value": html}]
    }

    requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        },
        json=body
    )

# ================= ROUTES =================

# LOGIN
@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    senha = request.form["senha"]

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user or user[6] != senha:
        return "Login inválido"

    session["email"] = email

    codigo = gerar_codigo()
    codigo_data[email] = {"codigo": codigo, "expira": time.time() + 300}
    enviar_email(codigo, email)

    return redirect("/verificacao")

# CRIAR CONTA
@app.route("/criar-conta", methods=["GET", "POST"])
def criar_conta():
    if request.method == "GET":
        return render_template("criar_conta.html")

    nome = request.form["nome"]
    sobrenome = request.form["sobrenome"]
    email = request.form["email"]
    telefone = request.form["telefone"]
    endereco = request.form["endereco"]
    cep = request.form["cep"]
    senha = request.form["senha"]

    if not senha_valida(senha):
        return "Senha fraca"

    db = get_db()
    try:
        db.execute("""
            INSERT INTO users
            (nome, sobrenome, email, telefone, endereco, cep, password, verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (nome, sobrenome, email, telefone, endereco, cep, senha))
        db.commit()
    except:
        return "E-mail já cadastrado"

    session["email"] = email
    codigo = gerar_codigo()
    codigo_data[email] = {"codigo": codigo, "expira": time.time() + 300}
    enviar_email(codigo, email)

    return redirect("/verificacao")

# VERIFICAÇÃO
@app.route("/verificacao")
def verificacao_page():
    if "email" not in session:
        return redirect("/")
    return render_template("verificacao.html")

@app.route("/verificar-codigo", methods=["POST"])
def verificar_codigo():
    email = session.get("email")
    codigo = request.json.get("codigo")

    registro = codigo_data.get(email)
    if not registro or time.time() > registro["expira"] or registro["codigo"] != codigo:
        return jsonify({"ok": False})

    db = get_db()
    db.execute("UPDATE users SET verified = 1 WHERE email = ?", (email,))
    db.commit()
    codigo_data.pop(email)

    return jsonify({"ok": True})

# GOOGLE
@app.route("/auth/google")
def auth_google():
    return oauth.google.authorize_redirect(
        redirect_uri=url_for("auth_google_callback", _external=True)
    )

@app.route("/auth/google/callback")
def auth_google_callback():
    oauth.google.authorize_access_token()
    user = oauth.google.userinfo()
    email = user["email"]

    session["email"] = email
    return redirect("/verificacao")

# MICROSOFT / XBOX
@app.route("/auth/microsoft")
def auth_microsoft():
    return oauth.microsoft.authorize_redirect(
        redirect_uri=url_for("auth_microsoft_callback", _external=True)
    )

@app.route("/auth/microsoft/callback")
def auth_microsoft_callback():
    oauth.microsoft.authorize_access_token()
    user = oauth.microsoft.get("https://graph.microsoft.com/v1.0/me").json()
    email = user.get("mail") or user.get("userPrincipalName")

    session["email"] = email
    return redirect("/verificacao")

# ================= MAIN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
