from flask import Flask, render_template, request, jsonify, abort, redirect, url_for, session
from werkzeug.utils import secure_filename
from pathlib import Path
from db import init_db, upsert_arrival, list_events, get_arrival, get_conn
from parser_pdf import parse_pdf

from flask import jsonify, request
import sqlite3
from datetime import datetime
# ------------- Config -------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "cambia-esto-por-uno-muy-seguro"   # necesario para sesiones
app.config["UPLOAD_FOLDER"] = Path("uploads")
app.config["UPLOAD_FOLDER"].mkdir(exist_ok=True)

# Usuarios “hardcodeados” por ahora
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "vendedor": {"password": "vend123", "role": "vendor"},
}

init_db()

# ------------- Helpers de auth -------------
def is_logged():
    return "user" in session

def current_role():
    return session.get("role")

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_logged():
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def role_required(*roles):
    from functools import wraps
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not is_logged():
                return redirect(url_for("login", next=request.path))
            if current_role() not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return deco

# ------------- Auth -------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = (request.form.get("username") or "").strip()
        p = (request.form.get("password") or "").strip()
        user = USERS.get(u)
        if user and user["password"] == p:
            session["user"] = u
            session["role"] = user["role"]
            nxt = request.args.get("next") or ("/admin" if user["role"] == "admin" else "/calendario")
            return redirect(nxt)
        return render_template("login.html", error="Usuario o clave incorrectos")
    return render_template("login.html")

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ------------- Vistas -------------
@app.get("/")
def home():
    # Entra al lugar correcto según rol
    if is_logged():
        return redirect("/admin" if current_role() == "admin" else "/calendario")
    return redirect(url_for("login"))

# ADMIN (sube PDF + agenda/lista)
@app.get("/admin")
@role_required("admin")
def admin():
    return render_template("admin.html")

# Vendedores (solo calendario)
@app.get("/calendario")
@role_required("vendor", "admin")  # los admin también pueden mirar
def calendario():
    return render_template("calendar.html")

# ------------- API -------------
@app.get("/events")
def events():
    # pública/lectura: sirve para el calendario de vendedores también
    return jsonify(list_events())

@app.get("/arrival/<bl>")
def arrival_detail(bl):
    arr, its = get_arrival(bl)
    if not arr:
        abort(404)
    items = [
        dict(code=i["code"], description=i["description"], meters=i["meters"], rolls=i["rolls"])
        for i in its
    ]
    data = dict(bl=arr["bl"], date=arr["date"], port=arr["port"], notes=arr["notes"], items=items)
    return jsonify(data)




@app.post("/upload")
@role_required("admin")  # <-- Solo admin puede subir
def upload():
    bl = (request.form.get("bl") or "").strip()
    port = (request.form.get("port") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None

    f = request.files.get("pdf")
    if not f:
        return abort(400, "Falta PDF")

    fname = secure_filename(f.filename)
    pdf_path = app.config["UPLOAD_FOLDER"] / fname
    f.save(pdf_path)

    if not bl:
        bl = pdf_path.stem

    date_iso, items = parse_pdf(str(pdf_path))
    if not date_iso:
        return abort(400, "No se detectó 'Fecha de llegada a bodega' en el PDF")
    if not items:
        return abort(400, "No se detectaron filas en el PDF")

    upsert_arrival(bl=bl, date=date_iso, port=port, notes=notes, items=items)
    return jsonify({
        "ok": True,
        "bl": bl,
        "date": date_iso,
        "port": port,
        "notes": notes,
        "items": len(items)
    })


   


if __name__ == "__main__":
    app.run(debug=True, port=5000)
