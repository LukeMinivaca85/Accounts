from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import random
import time
import requests
import os

print("🚀 APP.PY DA LUKINTOSH CARREGADO 🚀")



app = Flask(__name__)
app.secret_key = "lukintosh-secret-key"

# ================= CONFIG =================
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
EMAIL_REMETENTE = "lucas@lukintosh.com"
REPLY_TO_EMAIL = "noreply@lukintosh.com"
# =========================================

# ---------- DATABASE ----------
def get_db():
    return sqlite3.connect("users.db")

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            verified INTEGER DEFAULT 0
        )
    """)
    db.commit()
    db.close()

init_db()

# ---------- CÓDIGO DE VERIFICAÇÃO ----------
codigo_data = {}

def gerar_codigo():
    return str(random.randint(100000, 999999))

# ---------- EMAIL (COM DEBUG) ----------
def enviar_email(codigo, destino):
    print("==== ENVIO DE EMAIL ====")
    print("DESTINO:", destino)
    print("SENDGRID_API_KEY EXISTE?", bool(SENDGRID_API_KEY))

    if not SENDGRID_API_KEY:
        print("❌ SENDGRID_API_KEY NÃO DEFINIDA")
        return

    url = "https://api.sendgrid.com/v3/mail/send"
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }

    html = f"""
    <div style="font-family:Arial; color:#000; background:#fff">
        <h2>Lukintosh</h2>
        <p>Seu código de verificação:</p>
        <h1>{codigo}</h1>
        <p>Expira em 5 minutos.</p>
        <hr>
        <p style="font-size:12px">Lukintosh Corporation</p>
    </div>
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
    print("SENDGRID RESPONSE:", r.text)
    print("========================")

# ---------- ROTAS ----------
@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/criar-conta")
def criar_conta_page():
    return render_template("criar_conta.html")

@app.route("/criar-conta", methods=["POST"])
def criar_conta():
    email = request.form["email"]
    senha = request.form["senha"]

    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (email, password, verified) VALUES (?, ?, 0)",
            (email, senha)
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        return "Usuário já existe", 400
    db.close()

    session["email"] = email

    codigo = gerar_codigo()
    codigo_data[email] = {
        "codigo": codigo,
        "expira": time.time() + 300
    }

    enviar_email(codigo, email)
    return redirect("/verificacao")

@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    senha = request.form["senha"]

    db = get_db()
    user = db.execute(
        "SELECT password, verified FROM users WHERE email = ?",
        (email,)
    ).fetchone()
    db.close()

    if not user or user[0] != senha:
        return "Login inválido", 401

    session["email"] = email

    if user[1] != 1:
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
    db.close()

    codigo_data.pop(email)
    return jsonify({"ok": True})

# ---------- MAIN (PRODUÇÃO) ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
