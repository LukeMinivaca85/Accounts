from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import random
import time
import requests
import os

app = Flask(__name__)
app.secret_key = "lukintosh-secret-key"

# ================= CONFIG =================
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_REMETENTE = "lucas@lukintosh.com"
REPLY_TO_EMAIL = "noreply@lukintosh.com"
# ==========================================

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
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial; background:#f4f4f4; padding:30px;">
      <div style="max-width:420px;margin:auto;background:white;
                  padding:30px;border-radius:12px;text-align:center">
        <h2 style="color:#111">Lukintosh</h2>
        <p>Use o código abaixo para verificar sua conta:</p>

        <div style="
          font-size:32px;
          letter-spacing:8px;
          font-weight:bold;
          margin:20px 0;
        ">
          {codigo}
        </div>

        <p style="color:#666">
          Este código expira em 5 minutos.
        </p>

        <hr>
        <p style="font-size:12px;color:#999">
          Lukintosh Corporation<br>
          accounts.lukintosh.com
        </p>
      </div>
    </body>
    </html>
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
    print("SENDGRID STATUS:", r.status_code)

# --------- ROUTES ----------
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
        return "Senha fraca. Use pelo menos 8 caracteres, 1 maiúscula, 1 minúscula e 1 número."

    db = get_db()
    try:
        db.execute("""
            INSERT INTO users
            (nome, sobrenome, email, telefone, endereco, cep, password, verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (nome, sobrenome, email, telefone, endereco, cep, senha))
        db.commit()
    except:
        return "E-mail já cadastrado."

    # cria sessão e envia código
    session["email"] = email

    codigo = gerar_codigo()
    codigo_data[email] = {
        "codigo": codigo,
        "expira": time.time() + 300
    }

    enviar_email(codigo, email)
    return redirect("/verificacao")


@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    senha = request.form["senha"]

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    ).fetchone()

    if user is None:
        db.execute(
            "INSERT INTO users (email, password, verified) VALUES (?, ?, 0)",
            (email, senha)
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
@app.route("/auth/google")
def auth_google():
    return oauth.google.authorize_redirect(
        redirect_uri=url_for("auth_google_callback", _external=True)
    )

@app.route("/auth/google/callback")
def auth_google_callback():
    token = oauth.google.authorize_access_token()
    user = oauth.google.userinfo()
    email = user["email"]

    session["email"] = email
    return redirect("/verificacao")

@app.route("/auth/microsoft")
def auth_microsoft():
    return oauth.microsoft.authorize_redirect(
        redirect_uri=url_for("auth_microsoft_callback", _external=True)
    )

@app.route("/auth/microsoft/callback")
def auth_microsoft_callback():
    token = oauth.microsoft.authorize_access_token()
    user = oauth.microsoft.get(
        "https://graph.microsoft.com/v1.0/me"
    ).json()

    email = user.get("mail") or user.get("userPrincipalName")
    session["email"] = email
    return redirect("/verificacao")


# --------- RUN (RENDER / PROD) ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
