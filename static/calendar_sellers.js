// --- helpers ---
const pad2 = (n)=> String(n).padStart(2,"0");
const ymd = (d)=> `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`;
const num = (n)=> (Number(n)||0).toLocaleString("es-CL");
const esCL = new Intl.DateTimeFormat("es-CL", {month:"long", year:"numeric"});

// Trae eventos desde /events y los normaliza
async function loadEvents(){
  const r = await fetch("/events");
  if(!r.ok) throw new Error(await r.text());
  const arr = await r.json();
  // esperamos: [{id, title, start, port?, notes?, pdf?}]
  return arr.map(e=>({
    id: e.id || e.title,
    title: e.title || e.id,
    date: (e.start||"").slice(0,10), // YYYY-MM-DD
    port: e.port || e.extendedProps?.port || null,
    notes: e.notes || e.extendedProps?.notes || null,
    pdf: e.pdf || e.extendedProps?.pdf || null
  }));
}

// Rellena una semana inicial (lunes-domingo) antes del día 1
function startOfCalendar(year, monthIndex){ // monthIndex: 0..11
  const d1 = new Date(year, monthIndex, 1);
  let dow = d1.getDay(); if(dow===0) dow=7;          // domingo -> 7
  const offset = dow - 1;                           // cuántos días retroceder
  const start = new Date(d1); start.setDate(d1.getDate() - offset);
  return start;
}

function endOfCalendar(year, monthIndex){
  const dLast = new Date(year, monthIndex+1, 0);    // último día del mes
  let dow = dLast.getDay(); if(dow===0) dow=7;
  const forward = 7 - dow;
  const end = new Date(dLast); end.setDate(dLast.getDate() + forward);
  return end;
}

// --- render detalle ---
async function renderDetail(bl){
  const d_title = document.getElementById("d_title");
  const d_meta  = document.getElementById("d_meta");
  const d_rows  = document.getElementById("d_rows");
  const d_m     = document.getElementById("d_m_total");
  const d_r     = document.getElementById("d_r_total");
  d_rows.innerHTML = ""; d_m.textContent = ""; d_r.textContent = "";

  try{
    const r = await fetch(`/arrival/${encodeURIComponent(bl)}`);
    if(!r.ok) throw new Error(await r.text());
    const data = await r.json();

    d_title.textContent = `Detalle contenedor ${data.bl}`;
    d_meta.textContent  = `Fecha: ${data.date} ${data.port? " | Puerto: "+data.port:""} ${data.notes? " | Notas: "+data.notes:""}`;

    let m=0,r2=0;
    for(const it of (data.items||[])){
      m += Number(it.meters)||0;
      r2 += Number(it.rolls)||0;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td data-label="Código">${it.code}</td>
        <td data-label="Descripción">${it.description}</td>
        <td data-label="Metros" class="right">${num(it.meters)}</td>
        <td data-label="Rollos" class="right">${num(it.rolls)}</td>
      `;
      d_rows.appendChild(tr);
    }
    d_m.textContent = num(m);
    d_r.textContent = num(r2);

  }catch(err){
    d_title.textContent = "Error cargando detalle";
    d_meta.textContent = String(err);
  }
}

// --- render calendar ---
async function renderCalendar(state){
  const grid = document.getElementById("calGrid");
  const title = document.getElementById("calTitle");
  grid.innerHTML = "";

  // título
  title.textContent = `${esCL.format(new Date(state.year, state.month, 1))}`
                        .replace(/^\w/, c=>c.toUpperCase());

  // rango visible
  const start = startOfCalendar(state.year, state.month);
  const end   = endOfCalendar(state.year, state.month);

  // eventos
  const events = await loadEvents();
  const eventsByDate = events.reduce((acc,e)=>{
    if(e.date){ (acc[e.date] ||= []).push(e); }
    return acc;
  }, {});

  // pintar celdas
  for(let d=new Date(start); d<=end; d.setDate(d.getDate()+1)){
    const iso = ymd(d);
    const inMonth = (d.getMonth() === state.month);

    const cell = document.createElement("div");
    cell.className = "cell" + (inMonth? "" : " out");

    const day = document.createElement("div");
    day.className = "day";
    day.textContent = String(d.getDate());
    cell.appendChild(day);

    const evs = eventsByDate[iso] || [];
    if(evs.length === 0){
      const span = document.createElement("div");
      span.className = "no-events";
      span.textContent = "—";
      cell.appendChild(span);
    }else{
      evs.forEach(e=>{
        const pill = document.createElement("div");
        pill.className = "pill";
        pill.title = e.title + (e.port? ` • ${e.port}` : "");
        pill.textContent = e.title;
        pill.addEventListener("click", ()=> renderDetail(e.id));
        cell.appendChild(pill);
      });
    }

    grid.appendChild(cell);
  }
}

// --- init ---
document.addEventListener("DOMContentLoaded", ()=>{
  const state = { year: new Date().getFullYear(), month: new Date().getMonth() };

  document.getElementById("prevBtn").addEventListener("click", ()=>{
    if(state.month===0){ state.month=11; state.year--; } else { state.month--; }
    renderCalendar(state);
  });
  document.getElementById("nextBtn").addEventListener("click", ()=>{
    if(state.month===11){ state.month=0; state.year++; } else { state.month++; }
    renderCalendar(state);
  });
  document.getElementById("todayBtn").addEventListener("click", ()=>{
    const now = new Date();
    state.year = now.getFullYear(); state.month = now.getMonth();
    renderCalendar(state);
  });

  renderCalendar(state);
});
