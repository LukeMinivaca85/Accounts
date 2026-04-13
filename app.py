from flask import Flask, request, jsonify, send_file
import sqlite3, random, time, requests, os, jwt, datetime, resend

app = Flask(__name__)

# CONFIG
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY", "lukintosh-secret")

resend.api_key = RESEND_API_KEY

codigo_data = {}

# DB
def get_db():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn

# UTIL
def gerar_codigo():
    return str(random.randint(100000, 999999))

def get_ip():
    return request.headers.get("CF-Connecting-IP", request.remote_addr)

def get_device():
    return request.headers.get("User-Agent")

def get_location(ip):
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}").json()
        return f"{res.get('city')}, {res.get('country')}"
    except:
        return "Unknown"

# EMAIL
def enviar_email(codigo, destino, ip, device, location):
    resend.Emails.send({
        "from": "Lukintosh <no-reply@lukintosh.com>",
        "to": [destino],
        "subject": "⚠️ Login detectado",
        "html": f"""
        <h2>Lukintosh Security</h2>
        <h1>{codigo}</h1>
        <p>IP: {ip}</p>
        <p>Local: {location}</p>
        <p>Device: {device}</p>
        <p>Se não foi você, ignore este email.</p>
        """
    })

# HOME (serve o index.html)
@app.route("/")
def home():
    return send_file("index.html")

# REGISTER
@app.route("/register", methods=["POST"])
def register():
    data = request.json

    db = get_db()
    db.execute("INSERT INTO users (email, password) VALUES (?, ?)",
               (data["email"], data["password"]))
    db.commit()
    db.close()

    return {"message": "Conta criada"}

# LOGIN
@app.route("/login", methods=["POST"])
def login():
    data = request.json

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email=?",
                      (data["email"],)).fetchone()
    db.close()

    if not user or user["password"] != data["password"]:
        return {"error": "Login inválido"}, 401

    codigo = gerar_codigo()

    ip = get_ip()
    device = get_device()
    location = get_location(ip)

    codigo_data[data["email"]] = {
        "codigo": codigo,
        "expira": time.time() + 300
    }

    enviar_email(codigo, data["email"], ip, device, location)

    return {"2fa": True}

# VERIFY LOGIN
@app.route("/verify-login", methods=["POST"])
def verify():
    data = request.json

    if data["email"] not in codigo_data:
        return {"error": "Expirado"}, 400

    if codigo_data[data["email"]]["codigo"] != data["codigo"]:
        return {"error": "Código errado"}, 401

    token = jwt.encode({
        "email": data["email"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, SECRET_KEY, algorithm="HS256")

    return {"token": token}

# RUN
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
