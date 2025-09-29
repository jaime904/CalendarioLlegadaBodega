// ========= helpers =========
const num = (n)=> (Number(n)||0).toLocaleString("es-CL");
const $  = (sel)=> document.querySelector(sel);

// ========= pintar tabla de items (preview o detalle) =========
function fillItems(tbody, items, mCell, rCell){
  tbody.innerHTML = "";
  let m=0, r=0;
  for(const it of (items||[])){
    m += Number(it.meters)||0;
    r += Number(it.rolls)||0;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td data-label="Código">${it.code}</td>
      <td data-label="Descripción">${it.description}</td>
      <td data-label="Metros" class="right">${num(it.meters)}</td>
      <td data-label="Rollos" class="right">${num(it.rolls)}</td>`;
    tbody.appendChild(tr);
  }
  if(mCell) mCell.textContent = num(m);
  if(rCell) rCell.textContent = num(r);
}

// ========= subir PDF =========
async function handleUpload(ev){
  ev.preventDefault();
  const form = ev.currentTarget;
  const status = $("#uploadStatus");
  status.textContent = "Subiendo y procesando…";

  const fd = new FormData(form);
  try{
    const r = await fetch("/upload", { method:"POST", body: fd });
    if(!r.ok) throw new Error(await r.text());
    const data = await r.json();

    // preview
    $("#emptyHint").classList.add("hidden");
    $("#preview").classList.remove("hidden");
    $("#pBL").textContent   = data.bl || "—";
    $("#pPort").textContent = data.port || "—";
    $("#pDate").textContent = data.date || "—";
    $("#pNotes").textContent= data.notes || "—";

    // vuelve a leer detalle real (ya guardado) para traer filas
    const detR = await fetch(`/arrival/${encodeURIComponent(data.bl)}`);
    const det  = await detR.json();
    fillItems($("#pRows"), det.items, $("#pM"), $("#pR"));

    status.textContent = "Guardado ✔";
    await loadList();                 // refresca lista
    selectAndShow(data.bl);           // muestra detalle
    form.reset();
  }catch(err){
    console.error(err);
    status.textContent = "Error: " + String(err).slice(0,180);
  }
}

// ========= lista de contenedores =========
async function loadList(){
  const r = await fetch("/events");
  if(!r.ok) throw new Error(await r.text());
  const events = await r.json(); // [{id,title,start}]
  const box = $("#list");
  box.innerHTML = "";

  // más recientes arriba
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
    item.addEventListener("click", ()=> selectAndShow(e.id));
    box.appendChild(item);
  }
}

// ========= detalle =========
async function selectAndShow(bl){
  const cont = document.getElementById("detail");
  cont.classList.remove("hidden");

  const r = await fetch(`/arrival/${encodeURIComponent(bl)}`);
  if(!r.ok){ $("#d_title").textContent = "Error"; $("#d_meta").textContent = await r.text(); return; }
  const data = await r.json();

  $("#d_title").textContent = `Detalle contenedor ${data.bl}`;
  $("#d_meta").textContent  = `Fecha: ${data.date}` +
                              (data.port ? ` | Puerto: ${data.port}` : "") +
                              (data.notes? ` | Notas: ${data.notes}` : "");
  fillItems($("#d_rows"), data.items, $("#d_m_total"), $("#d_r_total"));
}

// ========= init =========
document.addEventListener("DOMContentLoaded", ()=>{
  // estilos del layout (usados por admin.html)
  // si ya están en brand.css, no pasa nada
  const style = document.createElement("style");
  style.textContent = `
    .container-2col{padding:16px;display:grid;grid-template-columns:360px 1fr;gap:16px}
    .row{display:flex;gap:8px;align-items:center;margin-top:10px}
    .row-between{display:flex;justify-content:space-between;align-items:center}
    .cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
    .scroll{max-height:320px;overflow:auto}
    .list{display:flex;flex-direction:column;gap:8px}
    .item{border:1px solid var(--line);border-radius:8px;padding:10px;cursor:pointer;background:#fff}
    .item:hover{background:#fafafa}
    .hidden{display:none}
  `;
  document.head.appendChild(style);

  document.getElementById("uploadForm").addEventListener("submit", handleUpload);
  document.getElementById("btnReload").addEventListener("click", loadList);

  loadList();
});
