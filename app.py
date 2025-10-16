# app.py (completo, sin app.run)
from flask import Flask, render_template, request, jsonify, abort, redirect, url_for, session
from werkzeug.utils import secure_filename
from pathlib import Path
from datetime import datetime
import re

from db import (
    init_db, upsert_arrival, list_events, get_arrival, get_conn,
    create_user, get_user, verify_password
)
from parser_pdf import parse_pdf

# ------------- Config -------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "cambia-esto-por-uno-muy-seguro"   # cambia por uno largo y aleatorio en prod
app.config["UPLOAD_FOLDER"] = Path("uploads")
app.config["UPLOAD_FOLDER"].mkdir(exist_ok=True)

# ------------- Helpers / Auth -------------
def is_logged() -> bool:
    return "user" in session

def current_role() -> str | None:
    return session.get("role")

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def deco(*args, **kwargs):
        if not is_logged():
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return deco

def role_required(role):
    from functools import wraps
    def wrap(fn):
        @wraps(fn)
        def deco(*args, **kwargs):
            if not is_logged():
                return redirect(url_for("login", next=request.path))
            if session.get("role") != role:
                abort(403)
            return fn(*args, **kwargs)
        return deco
    return wrap

# ------------- App bootstrap -------------
init_db()

# ------------- Views -------------
@app.get("/")
def index():
    if not is_logged():
        return redirect(url_for("login"))
    return redirect("/admin" if session.get("role") == "admin" else "/calendario")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = (request.form.get("username") or "").strip()
        p = (request.form.get("password") or "").strip()
        user = get_user(u)
        if user and verify_password(user["password_hash"], p):
            session["user"] = u
            session["role"] = user["role"]
            nxt = request.args.get("next") or ("/admin" if user["role"] == "admin" else "/calendario")
            return redirect(nxt)
        return render_template("login.html", error="Usuario o contraseña incorrectos")
    return render_template("login.html")

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.get("/admin")
@role_required("admin")
def admin_page():
    return render_template("admin.html")

@app.get("/calendario")
@login_required
def calendar_page():
    # vista para vendedores (rol vendor) y también admin si desea
    return render_template("calendar.html")

# ------------- API -------------
@app.get("/events")
@login_required
def api_events():
    """Retorna lista de eventos para el calendario: [{id, title, start}]"""
    events = list_events()
    return jsonify(events)


@app.get("/arrival/<bl>")
@login_required
def api_get_arrival(bl: str):
    """Retorna detalle de un BL con items (corrige sqlite3.Row -> dict)."""
    bl = bl.strip()
    if not bl:
        abort(400, "BL inválido")

    arrival, items = get_arrival(bl)
    if not arrival:
        abort(404, "BL no encontrado")

    # sqlite3.Row -> dict
    a = dict(arrival)
    its = [dict(i) for i in items]

    payload = {
        "bl":   a.get("bl"),
        "date": a.get("date"),
        "port": a.get("port"),
        "notes":a.get("notes"),
        "items": its,  # cada item: {code, description, meters, rolls}
    }
    return jsonify(payload)

@app.put("/arrival/<bl>")
def api_update_arrival(bl: str):
    if not bl.strip():
        abort(400, "BL inválido")

    data = request.get_json(force=True, silent=True) or {}
    port  = (data.get("port") or None)
    notes = (data.get("notes") or None)
    date  = (data.get("date")  or None)

    items = data.get("items") or []
    norm_items = []
    for it in items:
        if not it.get("code") and not it.get("description"):
            continue
        norm_items.append({
            "code":        (it.get("code") or "").strip(),
            "description": (it.get("description") or "").strip(),
            "meters":      float(it.get("meters") or 0),
            "rolls":       int(it.get("rolls") or 0),
        })

    if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        abort(400, "Formato de fecha inválido (usa YYYY-MM-DD).")

    upsert_arrival(bl=bl, date=date, port=port, notes=notes, items=norm_items)
    return jsonify({"ok": True, "bl": bl, "items": len(norm_items)})

# -------- Upload PDF --------
ALLOWED_EXTENSIONS = {"pdf"}
def allowed_file(name: str) -> bool:
    return "." in name and name.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.post("/upload")
@role_required("admin")
def upload_pdf():
    if "pdf" not in request.files:
        return abort(400, "Falta archivo PDF (campo 'pdf').")
    f = request.files["pdf"]
    if not f or f.filename == "":
        return abort(400, "Archivo vacío.")
    if not allowed_file(f.filename):
        return abort(400, "Solo se permite PDF.")

    bl    = (request.form.get("bl") or "").strip()
    port  = (request.form.get("port") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None
    date  = (request.form.get("date") or "").strip() or None

    pdf_name = secure_filename(f.filename)
    pdf_path = app.config["UPLOAD_FOLDER"] / pdf_name
    f.save(pdf_path)

    if not bl:
        bl = pdf_path.stem

    date_iso, items = parse_pdf(str(pdf_path))
    if not date_iso:
        return abort(400, "No se detectó 'Fecha de llegada a bodega' en el PDF")
    if not items:
        return abort(400, "No se detectaron filas en el PDF")

    if date:
        m1 = re.fullmatch(r"(\d{2})-(\d{2})-(\d{4})", date)
        if m1:
            date_iso = f"{m1.group(3)}-{m1.group(2)}-{m1.group(1)}"
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            date_iso = date

    upsert_arrival(bl=bl, date=date_iso, port=port, notes=notes, items=items)
    return jsonify({"ok": True, "bl": bl, "date": date_iso, "port": port, "notes": notes, "items": len(items)})

# --------- End of file (sin app.run) ---------
