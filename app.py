from flask import Flask, request, jsonify
import sqlite3
import random
import time
import requests
import resend
import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

# =========================
# CONFIG
# =========================

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_REMETENTE = "no-reply@lukintosh.com"

resend.api_key = RESEND_API_KEY

limiter = Limiter(get_remote_address, app=app, default_limits=["10 per minute"])

codigo_data = {}

# =========================
# DATABASE
# =========================

def get_db():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn

# =========================
# UTIL
# =========================

def gerar_codigo():
    return str(random.randint(100000, 999999))

def get_ip():
    return request.headers.get("CF-Connecting-IP", request.remote_addr)

def get_device():
    return request.headers.get("User-Agent", "Desconhecido")

def get_location(ip):
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}").json()
        return f"{res.get('city')}, {res.get('regionName')} - {res.get('country')}"
    except:
        return "Localização desconhecida"

# =========================
# EMAIL
# =========================

def enviar_email(codigo, destino, ip, device, location):
    html = f"""
    <h2>Lukintosh Security Alert</h2>

    <p>Detectamos um login na sua conta.</p>

    <h1>{codigo}</h1>

    <h3>Detalhes do acesso:</h3>
    <ul>
        <li><b>IP:</b> {ip}</li>
        <li><b>Localização:</b> {location}</li>
        <li><b>Dispositivo:</b> {device}</li>
    </ul>

    <p>Se foi você, use o código acima.</p>

    <p><b>Se NÃO foi você:</b></p>
    <ul>
        <li>Ignore este email</li>
        <li>Altere sua senha imediatamente</li>
    </ul>

    <p>Expira em 5 minutos.</p>
    """

    resend.Emails.send({
        "from": f"Lukintosh <{EMAIL_REMETENTE}>",
        "to": [destino],
        "subject": "⚠️ Novo login detectado - Lukintosh",
        "html": html
    })

# =========================
# ROOT (FIX 404)
# =========================

@app.route("/")
def home():
    return {
        "status": "ok",
        "service": "Lukintosh Accounts",
        "version": "1.0"
    }

# =========================
# HEALTH CHECK
# =========================

@app.route("/health")
def health():
    return {"status": "ok"}

# =========================
# REGISTER
# =========================

@app.route("/register", methods=["POST"])
@limiter.limit("5 per minute")
def register():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    db = get_db()
    db.execute("INSERT INTO users (email, password) VALUES (?, ?)", (email, password))
    db.commit()
    db.close()

    return jsonify({"message": "Usuário criado com sucesso"})

# =========================
# LOGIN (STEP 1)
# =========================

@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    db.close()

    if not user:
        return jsonify({"error": "Usuário não encontrado"}), 404

    if user["password"] != password:
        return jsonify({"error": "Senha incorreta"}), 401

    codigo = gerar_codigo()

    ip = get_ip()
    device = get_device()
    location = get_location(ip)

    codigo_data[email] = {
        "codigo": codigo,
        "expira": time.time() + 300
    }

    enviar_email(codigo, email, ip, device, location)

    return jsonify({
        "message": "Código enviado",
        "2fa_required": True
    })

# =========================
# VERIFY LOGIN
# =========================

@app.route("/verify-login", methods=["POST"])
@limiter.limit("10 per minute")
def verify_login():
    data = request.json
    email = data.get("email")
    codigo = data.get("codigo")

    if email not in codigo_data:
        return jsonify({"error": "Código expirado"}), 400

    info = codigo_data[email]

    if time.time() > info["expira"]:
        del codigo_data[email]
        return jsonify({"error": "Código expirado"}), 400

    if info["codigo"] != codigo:
        return jsonify({"error": "Código inválido"}), 401

    del codigo_data[email]

    return jsonify({
        "success": True,
        "message": "Login autorizado"
    })

# =========================
# RUN
# =========================

if __name__ == "__main__":
    app.run()
