from flask import Flask, render_template, request, redirect, session, jsonify, url_for
import sqlite3
import random
import time
import requests
import os

from authlib.integrations.flask_client import OAuth

app = Flask(__name__)
app.secret_key = "lukintosh-secret-key"

# ================= CONFIG =================
SENDGRID_API_KEY = "SUA_API_KEY_SENDGRID"
EMAIL_REMETENTE = "no-reply@lukintosh.com"
REPLY_TO_EMAIL = "lsilqueiracorre@gmail.com"

GOOGLE_CLIENT_ID = "SEU_GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET = "SEU_GOOGLE_CLIENT_SECRET"

MICROSOFT_CLIENT_ID = "SEU_MICROSOFT_CLIENT_ID"
MICROSOFT_CLIENT_SECRET = "SEU_MICROSOFT_CLIENT_SECRET"
# =========================================

# --------- OAUTH ----------
oauth = OAuth(app)

oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)

oauth.register(
    name="microsoft",
    client_id=MICROSOFT_CLIENT_ID,
    client_secret=MICROSOFT_CLIENT_SECRET,
    server_metadata_url="https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"}
)

# --------- DATABASE ----------
def get_db():
    return sqlite3.connect("users.db")

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            verified INTEGER
        )
    """)
    db.commit()
    db.close()

init_db()

# --------- CODE STORAGE ----------
codigo_data = {}

def gerar_codigo():
    return str(random.randint(100000, 999999))

# --------- SEND EMAIL ----------
def enviar_email(codigo, destino):
    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }

    html = f"""
    <h2>Lukintosh</h2>
    <p>Seu código de verificação:</p>
    <h1>{codigo}</h1>
    <p>Expira em 5 minutos.</p>
    """

    body = {
        "personalizations": [{
            "to": [{"email": destino}]
        }],
        "from": {"email": EMAIL_REMETENTE},
        "reply_to": {"email": REPLY_TO_EMAIL},
        "subject": "Código de verificação – Lukintosh",
        "content": [{
            "type": "text/html",
            "value": html
        }]
    }

    r = requests.post(url, headers=headers, json=body)
    print("SENDGRID:", r.status_code)

# --------- ROUTES ----------
@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    senha = request.form["senha"]

    db = get_db()
    user = db.execute(
        "SELECT password FROM users WHERE email = ?",
        (email,)
    ).fetchone()
    db.close()

    if not user or user[0] != senha:
        return "Login inválido", 401

    session["email"] = email

    # 🔥 SEMPRE ENVIA O CÓDIGO (DEV MODE)
    codigo = gerar_codigo()
    codigo_data[email] = {
        "codigo": codigo,
        "expira": time.time() + 300
    }
    enviar_email(codigo, email)

    return redirect("/verificacao")
@app.route("/reenviar-codigo", methods=["POST"])
def reenviar_codigo():
    email = session.get("email")
    if not email:
        return jsonify({"ok": False})

    codigo = gerar_codigo()
    codigo_data[email] = {
        "codigo": codigo,
        "expira": time.time() + 300
    }

    enviar_email(codigo, email)
    return jsonify({"ok": True})

# --------- GOOGLE ----------
@app.route("/auth/google")
def auth_google():
    return oauth.google.authorize_redirect(
        url_for("auth_google_callback", _external=True)
    )

@app.route("/auth/google/callback")
def auth_google_callback():
    token = oauth.google.authorize_access_token()
    user = oauth.google.parse_id_token(token)

    email = user["email"]

    db = get_db()
    if db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone() is None:
        db.execute(
            "INSERT INTO users (email, password, verified) VALUES (?, '', 0)",
            (email,)
        )
        db.commit()

    session["email"] = email

    codigo = gerar_codigo()
    codigo_data[email] = {
        "codigo": codigo,
        "expira": time.time() + 300
    }

    enviar_email(codigo, email)
    return redirect("/verificacao")

# --------- MICROSOFT ----------
@app.route("/auth/microsoft")
def auth_microsoft():
    return oauth.microsoft.authorize_redirect(
        url_for("auth_microsoft_callback", _external=True)
    )

@app.route("/auth/microsoft/callback")
def auth_microsoft_callback():
    token = oauth.microsoft.authorize_access_token()
    user = oauth.microsoft.parse_id_token(token)

    email = user.get("email") or user.get("preferred_username")

    db = get_db()
    if db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone() is None:
        db.execute(
            "INSERT INTO users (email, password, verified) VALUES (?, '', 0)",
            (email,)
        )
        db.commit()

    session["email"] = email

    codigo = gerar_codigo()
    codigo_data[email] = {
        "codigo": codigo,
        "expira": time.time() + 300
    }

    enviar_email(codigo, email)
    return redirect("/verificacao")

# --------- VERIFICAÇÃO ----------
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

    if not registro:
        return jsonify({"ok": False})

    if time.time() > registro["expira"]:
        return jsonify({"ok": False})

    if registro["codigo"] != codigo:
        return jsonify({"ok": False})

    db = get_db()
    db.execute(
        "UPDATE users SET verified = 1 WHERE email = ?",
        (email,)
    )
    db.commit()

    codigo_data.pop(email)
    return jsonify({"ok": True})

# ---------- MAIN (PRODUÇÃO) ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
