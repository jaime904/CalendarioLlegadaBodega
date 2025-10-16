
import re
import fitz  # PyMuPDF
from typing import Optional, Tuple, List

# -------------------------------
# Prefijos aceptados (agrega los que necesites)
# -------------------------------
PREFIXES = {
    "DC", "TX", "IMPO",
    "TU", "FK", "PT", "RTN", "HRS", "DG", "TN", "PE","TEC"
}
PREFIX_RE_STR = "(?:" + "|".join(sorted(PREFIXES, key=len, reverse=True)) + ")"

DATE_RE = re.compile(r"(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})", re.IGNORECASE)


def _normalize_number(s: str) -> float:
    """'3.948,80' -> 3948.80  |  '7,025.40' -> 7025.40  |  '7025' -> 7025.0"""
    t = (s or "").strip()
    if "." in t and "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t and "." not in t:
        t = t.replace(",", ".")
    t = re.sub(r"[^0-9.]", "", t)
    try:
        return float(t) if t else 0.0
    except ValueError:
        return 0.0


def _to_iso(date_str: str) -> Optional[str]:
    m = DATE_RE.search(date_str or "")
    if not m:
        return None
    d, mth, y = re.split(r"[\/\-.]", m.group(1))
    if len(y) == 2:
        y = "20" + y
    return f"{y}-{int(mth):02d}-{int(d):02d}"


def _looks_number(tok: str) -> bool:
    return bool(re.fullmatch(r"[\d.,]+", tok or ""))


def _is_int_token(tok: str) -> bool:
    """Entero puro (para rollos)."""
    return bool(re.fullmatch(r"\d{1,6}", tok or ""))


def _is_code_token(tok: str) -> bool:
    """Tokens que forman el código (prefijo + separadores + segmentos numéricos)."""
    t = (tok or "").strip()
    if not t:
        return False
    if re.fullmatch(PREFIX_RE_STR, t.upper()):  # prefijo suelto: DC / TX / IMPO / ...
        return True
    if t in {".", "-", "·"}:
        return True
    if re.fullmatch(r"\d+\.?", t):  # segmento numérico
        return True
    if re.fullmatch(PREFIX_RE_STR + r"\.?", t.upper()):  # prefijo pegado a punto
        return True
    return False


def _join_code(tokens) -> str:
    """Une tokens a 'TX.860.01.0004' / 'IMPO.01.0001' / 'DC.200.96.0003'."""
    out = []
    for t in tokens:
        tt = (t or "").strip()
        out.append("." if tt in {".", "-", "·"} else tt)
    code = "".join(out)
    code = re.sub(r"[^\w\.]", "", code)      # deja letras/números/puntos
    code = re.sub(r"\.+", ".", code).strip(".")
    return code


def _group_words_into_rows(words, y_tol=3.0):
    """Agrupa palabras por renglones usando Y y tolerancia."""
    rows, current, last_y = [], [], None
    for w in sorted(words, key=lambda w: (round(w[1], 1), w[0])):
        y = w[1]
        if last_y is None or abs(y - last_y) <= y_tol:
            current.append(w)
            last_y = y if last_y is None else (last_y + y) / 2
        else:
            rows.append(current)
            current = [w]
            last_y = y
    if current:
        rows.append(current)
    return rows


def _pick_meters_rolls_from_tokens(tokens: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Recorre tokens de derecha a izquierda:
    - ROLLOS = primer ENTERO puro
    - METROS = primer número inmediatamente a su izquierda
    """
    rolls_txt: Optional[str] = None
    meters_txt: Optional[str] = None
    for t in reversed(tokens):
        if _is_int_token(t):
            rolls_txt = t
            break
    if not rolls_txt:
        return None, None
    found_rolls = False
    for t in reversed(tokens):
        if not found_rolls:
            if t == rolls_txt:
                found_rolls = True
            continue
        if _looks_number(t):
            meters_txt = t
            break
    if not meters_txt:
        return None, None
    return meters_txt, rolls_txt


def _parse_rows_layout(page):
    """Intento 1: por layout (palabras con coordenadas)."""
    items = []
    words = page.get_text("words") or []
    for row in _group_words_into_rows(words, y_tol=3.0):
        toks = [w[4] for w in sorted(row, key=lambda w: w[0])]
        if not toks:
            continue
        joined = " ".join(toks).strip()
        if "SUB-TOTAL" in joined.upper():
            continue
        # debe haber un prefijo alfabético (DC/TX/IMPO/TU/...)
        if not any(re.fullmatch(r"[A-Za-z]{2,6}", (t or "")) for t in toks):
            continue

        meters_txt, rolls_txt = _pick_meters_rolls_from_tokens(toks)
        if not meters_txt or not rolls_txt:
            continue

        # izquierda de metros/rollos (para code+desc)
        cut_idx = None
        seen = 0
        for i in range(len(toks) - 1, -1, -1):
            if toks[i] == rolls_txt or toks[i] == meters_txt:
                seen += 1
                if seen == 2:
                    cut_idx = i
                    break
        if cut_idx is None:
            continue
        left = toks[:cut_idx]

        # código y descripción
        code_tokens, i = [], 0
        while i < len(left) and _is_code_token(left[i]):
            code_tokens.append(left[i])
            i += 1
        if not code_tokens:
            continue
        code = _join_code(code_tokens)
        if not re.match(rf"^{PREFIX_RE_STR}\.", code.upper()):
            continue

        desc = " ".join(left[i:]).strip()

        meters = _normalize_number(meters_txt)
        rolls = int(re.sub(r"\D", "", rolls_txt)) if re.search(r"\d", rolls_txt) else 0

        if meters <= 0 and rolls <= 0:
            continue
        if not desc:
            continue

        items.append({"code": code, "description": desc, "meters": meters, "rolls": rolls})
    return items


def _parse_with_tables(page):
    """Intento 2: detección de tablas de PyMuPDF."""
    items = []
    try:
        tf = page.find_tables()
    except Exception:
        return items

    for tb in getattr(tf, "tables", []):
        data = tb.extract()
        if not data or len(data) < 2:
            continue

        # salta encabezados
        start_i = 0
        for i, row in enumerate(data[:3]):
            row_join = " ".join((c or "") for c in row).lower()
            if "código" in row_join or "descripcion" in row_join or "descripción" in row_join:
                start_i = i + 1

        for row in data[start_i:]:
            cells = [(c or "").strip() for c in row]
            if not any(cells):
                continue
            row_text = " ".join(cells)
            if "SUB-TOTAL" in row_text.upper():
                continue

            # código con prefijo válido
            code = ""
            for c in cells:
                if re.match(rf"^{PREFIX_RE_STR}[\s\.\d]+$", c.upper()):
                    code = re.sub(r"\s+", ".", c).replace("..", ".").strip(".")
                    break
            if not code:
                continue

            # rollos y metros (saltando precio)
            rolls_txt = None
            meters_txt = None
            for idx in range(len(cells) - 1, -1, -1):
                c = cells[idx]
                if _is_int_token(c):
                    rolls_txt = c
                    for j in range(idx - 1, -1, -1):
                        if _looks_number(cells[j]):
                            meters_txt = cells[j]
                            break
                    break
            if not rolls_txt or not meters_txt:
                continue

            meters = _normalize_number(meters_txt)
            rolls = int(re.sub(r"\D", "", rolls_txt)) if re.search(r"\d", rolls_txt) else 0

            # descripción: primera celda no numérica distinta del código
            desc = ""
            for c in cells:
                if c and c != code and not _looks_number(c) and not re.match(rf"^{PREFIX_RE_STR}[\s\.\d]+$", c.upper()):
                    desc = c
                    break
            if not desc:
                continue

            items.append({"code": code, "description": desc, "meters": meters, "rolls": rolls})
    return items


# Intento 3: respaldo por líneas (regex)
LINE_RE = re.compile(
    rf"(?P<code>{PREFIX_RE_STR}[\s\.\d]+?)\s+"
    r"(?P<desc>.+?)\s+"
    r"(?P<meters>\d[\d\.,]*)\s+"
    r"(?P<rolls>\d{1,6})(?!\S)",
    re.IGNORECASE
)

def _parse_by_lines(page):
    items = []
    txt = page.get_text("text") or ""
    txt = re.sub(r"[ \t]+", " ", txt)
    for raw in txt.splitlines():
        line = raw.strip()
        if not line or "SUB-TOTAL" in line.upper():
            continue
        m = LINE_RE.search(line)
        if not m:
            continue
        code = re.sub(r"\s+", ".", m.group("code")).strip(".")
        if not re.match(rf"^{PREFIX_RE_STR}\.", code.upper()):
            continue
        desc = m.group("desc").strip()
        meters = _normalize_number(m.group("meters"))
        rolls = int(m.group("rolls"))
        if meters <= 0 and rolls <= 0:
            continue
        items.append({"code": code, "description": desc, "meters": meters, "rolls": rolls})
    return items


def parse_pdf(pdf_path: str):
    doc = fitz.open(pdf_path)

    # ---------- FECHA ----------
    full_text = "\n".join([p.get_text("text") for p in doc])
    m = re.search(r"fecha\s*de\s*llegada[\s\S]{0,120}?a\s*bodega[\s\S]{0,120}", full_text, re.IGNORECASE)
    date_iso = _to_iso(m.group(0)) if m else None
    if not date_iso:
        one_line = re.sub(r"\s+", " ", full_text)
        mm = re.search(r"bodega[^0-9]{0,40}(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})", one_line, re.IGNORECASE)
        if mm:
            date_iso = _to_iso(mm.group(0))

    # ---------- FILAS ----------
    items = []
    for page in doc:
        items.extend(_parse_rows_layout(page))
    if not items:
        for page in doc:
            items.extend(_parse_with_tables(page))
    if not items:
        for page in doc:
            items.extend(_parse_by_lines(page))

    doc.close()
    return date_iso, items
