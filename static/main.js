// ========= helpers =========
const num = (n)=> (Number(n)||0).toLocaleString("es-CL");
const $  = (sel)=> document.querySelector(sel);

// ========= fetch con manejo de sesión/JSON =========
async function fetchJSON(url, opts={}){
  const r = await fetch(url, {
    credentials: "same-origin", // asegura que envíe cookie de sesión
    ...opts,
  });

  // si el servidor redirige a /login (sesión expirada o sin rol), fetch sigue la redirección y aquí llega 200 HTML
  if (r.redirected && r.url.includes("/login")) {
    const txt = await r.text();
    throw new Error("Sesión expirada o sin permisos (redirigido a /login). Vuelve a iniciar sesión.");
  }

  const ct = r.headers.get("content-type") || "";
  const isJSON = ct.includes("application/json");

  if (!r.ok) {
    // intenta extraer mensaje
    const body = isJSON ? (await r.json()) : (await r.text());
    const msg  = typeof body === "string" ? body : JSON.stringify(body);
    throw new Error(msg.slice(0, 500));
  }

  if (!isJSON) {
    const txt = await r.text();
    throw new Error("Respuesta no-JSON del servidor (¿redirección o error HTML?). " + txt.slice(0, 120));
  }

  return r.json();
}

// ========= estado edición / cambios sin guardar =========
let CURRENT_BL = null;
let EDIT_MODE  = false;

function toggleButtons(){
  const show = !!CURRENT_BL;
  $("#btnEdit").classList.toggle("hidden", !show || EDIT_MODE);
  $("#btnSave").classList.toggle("hidden", !EDIT_MODE);
  $("#btnCancel").classList.toggle("hidden", !EDIT_MODE);
}

// confirmación al salir con edición activa (recarga / cerrar)
window.addEventListener("beforeunload", (e)=>{
  if(EDIT_MODE){
    e.preventDefault();
    e.returnValue = "";
  }
});

// util para proteger acciones que cambian de vista
async function guardLeaveEdit(next){
  if(!EDIT_MODE){ return next(); }
  const ok = confirm("Tienes cambios sin guardar. ¿Deseas salir de la edición?");
  if(ok){ EDIT_MODE = false; toggleButtons(); return next(); }
}

// ========= pintar tabla de items =========
function fillItems(tbody, items, mCell, rCell){
  tbody.innerHTML = "";
  let m=0, r=0;
  for(const it of (items||[])){
    m += Number(it.meters)||0;
    r += Number(it.rolls)||0;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${it.code}</td>
      <td>${it.description}</td>
      <td class="right">${num(it.meters)}</td>
      <td class="right">${num(it.rolls)}</td>
    `;
    tbody.appendChild(tr);
  }
  if(mCell) mCell.textContent = num(m);
  if(rCell) rCell.textContent = num(r);
}

// ========= subir PDF =========
async function handleUpload(ev){
  ev.preventDefault();

  if(EDIT_MODE){
    const ok = confirm("Tienes cambios sin guardar. ¿Continuar y descartar los cambios?");
    if(!ok) return;
    EDIT_MODE = false; toggleButtons();
  }

  const form = ev.currentTarget;
  const status = $("#uploadStatus");
  status.textContent = "Subiendo y procesando…";

  const fd = new FormData(form);
  try{
    const data = await fetchJSON("/upload", { method:"POST", body: fd });

    // preview rápido
    $("#emptyHint").classList.add("hidden");
    $("#preview").classList.remove("hidden");
    $("#pBL").textContent   = data.bl || "—";
    $("#pPort").textContent = data.port || "—";
    $("#pDate").textContent = data.date || "—";
    $("#pNotes").textContent= data.notes || "—";

    // leer detalle real (items)
    const det  = await fetchJSON(`/arrival/${encodeURIComponent(data.bl)}`);
    fillItems($("#pRows"), det.items, $("#pM"), $("#pR"));

    status.textContent = "Guardado ✔";
    await loadList();
    await selectAndShow(data.bl);
    CURRENT_BL = data.bl;
    toggleButtons();
    form.reset();
  }catch(err){
    console.error(err);
    status.textContent = "Error: " + String(err).slice(0,180);
    alert(status.textContent);
  }
}

// ========= lista de contenedores =========
async function loadList(){
  const events = await fetchJSON("/events");
  const box = $("#list");
  box.innerHTML = "";

  events.sort((a,b)=> (b.start||"").localeCompare(a.start||""));

  for(const e of events){
    const item = document.createElement("div");
    item.className = "item";
    item.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <div>
          <strong>${e.title.replace(/^Llegada:\s*/,"")}</strong>
          <span class="pill">${e.start||""}</span>
        </div>
      </div>`;
    item.addEventListener("click", ()=> guardLeaveEdit(()=> selectAndShow(e.id)));
    box.appendChild(item);
  }
}

// ========= detalle =========
async function selectAndShow(bl){
  const cont = document.getElementById("detail");
  cont.classList.remove("hidden");

  const data = await fetchJSON(`/arrival/${encodeURIComponent(bl)}`);

  $("#d_title").textContent = `Detalle contenedor ${data.bl}`;
  $("#d_meta").textContent  = `Fecha: ${data.date}` +
                              (data.port ? ` | Puerto: ${data.port}` : "") +
                              (data.notes? ` | Notas: ${data.notes}` : "");
  fillItems($("#d_rows"), data.items, $("#d_m_total"), $("#d_r_total"));

  // espejo en “Datos detectados”
  $("#emptyHint").classList.add("hidden");
  $("#preview").classList.remove("hidden");
  $("#pBL").textContent   = data.bl || "—";
  $("#pPort").textContent = data.port || "—";
  $("#pDate").textContent = data.date || "—";
  $("#pNotes").textContent= data.notes || "—";
  fillItems($("#pRows"), data.items, $("#pM"), $("#pR"));

  CURRENT_BL = bl;
  EDIT_MODE  = false;
  toggleButtons();
}

// ========= edición =========
function toInput(text, type="text"){
  const i = document.createElement("input");
  i.type = type;
  i.value = text || "";
  i.style.width = "100%";
  i.dataset.role = "editor";
  return i;
}

function enterEditMode(det){
  EDIT_MODE = true;

  const port  = $("#pPort");
  const date  = $("#pDate");
  const notes = $("#pNotes");

  port.replaceChildren(toInput(port.textContent));
  const di = toInput((det.date || "").slice(0,10), "date");
  date.replaceChildren(di);
  const ta = document.createElement("textarea");
  ta.value = notes.textContent || "";
  ta.dataset.role = "editor";
  ta.style.width = "100%";
  notes.replaceChildren(ta);

  const tbody = $("#pRows");
  const rows = Array.from(tbody.querySelectorAll("tr"));
  rows.forEach((tr) => {
    const tds = tr.querySelectorAll("td");
    if (tds.length !== 4) return;
    const [c0,c1,c2,c3] = tds;
    c0.replaceChildren(toInput(c0.textContent));
    c1.replaceChildren(toInput(c1.textContent));
    c2.replaceChildren(toInput((c2.textContent||"").replace(/\./g,"")));
    c3.replaceChildren(toInput(c3.textContent));
  });

  toggleButtons();
}

function exitEditMode(refresh=true){
  EDIT_MODE = false;
  if(refresh && CURRENT_BL){ selectAndShow(CURRENT_BL); }
  toggleButtons();
}

async function saveEdit(){
  if(!CURRENT_BL) return;

  const port  = document.querySelector("#pPort [data-role=editor]")?.value || "";
  const dateI = document.querySelector("#pDate [data-role=editor]")?.value || "";
  const notes = document.querySelector("#pNotes [data-role=editor]")?.value || "";

  const items = [];
  document.querySelectorAll("#pRows tr").forEach(tr=>{
    const ins = tr.querySelectorAll("[data-role=editor]");
    if (ins.length===4){
      const [iCode, iDesc, iMeters, iRolls] = ins;
      if (!iCode.value && !iDesc.value) return;
      items.push({
        code: iCode.value.trim(),
        description: iDesc.value.trim(),
        meters: Number(iMeters.value.replace(",", ".")) || 0,
        rolls:  Number(iRolls.value) || 0
      });
    }
  });

  const payload = { port, notes, date: dateI || null, items };
  await fetchJSON(`/arrival/${encodeURIComponent(CURRENT_BL)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  await loadList();
  EDIT_MODE = false;
  selectAndShow(CURRENT_BL);
  toggleButtons();
}

// ========= init =========
document.addEventListener("DOMContentLoaded", ()=>{
  $("#uploadForm").addEventListener("submit", handleUpload);
  $("#btnReload").addEventListener("click", ()=> guardLeaveEdit(loadList));

  $("#btnEdit").addEventListener("click", async ()=>{
    if(!CURRENT_BL) return;
    const det = await fetchJSON(`/arrival/${encodeURIComponent(CURRENT_BL)}`);
    enterEditMode(det);
  });
  $("#btnSave").addEventListener("click", async ()=>{
    try{ await saveEdit(); }catch(e){ alert("Error al guardar: " + e.message); }
  });
  $("#btnCancel").addEventListener("click", ()=> exitEditMode(true));

  const logout = document.getElementById("logoutLink");
  if(logout){
    logout.addEventListener("click", (ev)=>{
      if(EDIT_MODE){
        ev.preventDefault();
        const ok = confirm("Tienes cambios sin guardar. ¿Deseas salir igualmente?");
        if(ok){ EDIT_MODE = false; window.location.href = logout.href; }
      }
    });
  }

  loadList();
});
