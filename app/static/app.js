/* ============================================================
   КАЛЕНДАРЬ ТО — умный календарь ТО (фронтенд)
   ============================================================ */
"use strict";

const FREQS = ["Разовая", "Еженедельно", "Ежемесячно", "Ежеквартально", "Раз в полгода", "Ежегодно", "Раз в 3 года", "Раз в 5 лет"];
const MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
const DOWS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

/* ---------- хелперы ---------- */
const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
const esc = s => String(s === null || s === undefined ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
const fmtMoney = n => new Intl.NumberFormat("ru-RU").format(Math.round(n || 0)) + " ₽";
const fmtDate = s => s ? new Date(s.length === 10 ? s + "T00:00:00" : s).toLocaleDateString("ru-RU") : "—";
const todayISO = () => {
  const d = new Date();
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
};

async function api(url, data, method) {
  method = method || (data === undefined ? "GET" : "POST");
  const opts = {
    method: method,
    headers: { "Content-Type": "application/json" },
    cache: "no-store"
  };
  if (data !== undefined) opts.body = JSON.stringify(data);
  try {
    const r = await fetch(url, opts);
    return await r.json();
  } catch (err) {
    toast("Ошибка сети: " + err.message, "error");
    return { ok: false };
  }
}

function notice(msg, type) {
  const host = $("#toastHost") || document.body;
  const n = document.createElement("div");
  n.className = "toast " + (type || "");
  n.textContent = msg;
  n.addEventListener("click", () => n.remove());
  host.appendChild(n);
  setTimeout(() => {
    n.style.transition = "opacity .3s, transform .3s";
    n.style.opacity = "0";
    n.style.transform = "translateX(20px)";
    setTimeout(() => n.remove(), 320);
  }, 3000);
}
const toast = notice;


function openModal(html) {
  $("#modalBox").innerHTML = html;
  $("#modalOverlay").classList.remove("hidden");
}
function closeModal() { $("#modalOverlay").classList.add("hidden"); }

$("#modalOverlay").addEventListener("click", e => { if (e.target.id === "modalOverlay") closeModal(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

function statusBadge(st, isOverdue) {
  if (isOverdue && st === "Запланировано") return '<span class="badge b-over">Просрочено</span>';
  const map = { "Запланировано": "b-plan", "Выполнено": "b-done", "Перенесено": "b-move", "Отменено": "b-cancel" };
  return '<span class="badge ' + (map[st] || "b-plan") + '">' + esc(st) + "</span>";
}
function freqBadge(f) { return '<span class="badge b-freq">' + esc(f || "—") + "</span>"; }
function kv(k, v, isHtml) {
  const val = isHtml || (typeof v === "string" && v.includes("<span")) ? v : esc(v);
  return '<div><div class="k">' + esc(k) + '</div><div class="v">' + val + "</div></div>";
}
function selectHtml(id, items, selected, allLabel) {
  return '<select class="inp" id="' + id + '"><option value="">' + allLabel + "</option>" +
    items.map(it => '<option value="' + esc(it.value) + '"' + (String(it.value) === String(selected) ? " selected" : "") + ">" + esc(it.label) + "</option>").join("") +
    "</select>";
}

/* ---------- навигация ---------- */
let currentPage = "dashboard";
const PAGES = {
  dashboard:   { title: "Дашборд",    sub: "Сводка по объектам, работам и срокам",       load: loadDashboard },
  calendar:    { title: "Календарь",  sub: "График выполнений по месяцам",               load: () => loadCalendar() },
  objects:     { title: "Объекты",    sub: "Организации и площадки на обслуживании",     load: loadObjects },
  works:       { title: "Виды работ", sub: "Справочник регламентов и норм ПБ",           load: loadWorks },
  assignments: { title: "Назначения", sub: "Договоры, периодичность и автопланирование", load: loadAssignments },
  journal:     { title: "Журнал ТО",  sub: "Фиксация выполнений, переносы, исполнители", load: loadJournal },
  invoices:    { title: "Счета",      sub: "Выставление, оплата и печать счетов", load: loadInvoices },
};

function showPage(name) {
  currentPage = name;
  Object.keys(PAGES).forEach(p => $("#page-" + p).classList.toggle("hidden", p !== name));
  $$(".nx-nav button").forEach(b => b.classList.toggle("active", b.dataset.page === name));
  const sec = $("#page-" + name);
  sec.style.animation = "none";
  void sec.offsetWidth;
  sec.style.animation = "";
  $("#pageTitle").textContent = PAGES[name].title;
  $("#pageSub").textContent = PAGES[name].sub;
  PAGES[name].load();
}

/* ---------- кеши ---------- */
let objectsCache = [], worksCache = [];
async function ensureCaches() {
  if (!objectsCache.length) { const r = await api("/api/objects/"); if (r.ok) objectsCache = r.data; }
  if (!worksCache.length) { const r = await api("/api/works/"); if (r.ok) worksCache = r.data; }
}

/* ---------- дашборд ---------- */
function statCard(label, value, note, tone) {
  return '<div class="stat ' + tone + '"><div class="stat-label">' + esc(label) + '</div><div class="stat-value">' + value + '</div><div class="stat-note">' + esc(note) + "</div></div>";
}
function execTr(e, isOver) {
  return '<tr class="clickable" data-action="exec-open" data-id="' + esc(e.ID) + '">' +
    '<td class="mono">' + fmtDate(e.PlannedDate) + "</td>" +
    "<td><b>" + esc(e.ObjectName) + "</b></td>" +
    "<td>" + esc(e.WorkName) + "</td>" +
    "<td>" + statusBadge(e.Status, isOver || e.IsOverdue) + "</td></tr>";
}
function listTable(rows) {
  return '<table><thead><tr><th>Дата</th><th>Объект</th><th>Работа</th><th>Статус</th></tr></thead><tbody>' + rows + "</tbody></table>";
}

async function loadDashboard() {
  const host = $("#page-dashboard");
  host.innerHTML = '<div class="empty"><span class="big">🦉</span>Считаем показатели…</div>';
  const stats = await api("/api/dashboard/stats");
  const up = await api("/api/dashboard/upcoming");
  const over = await api("/api/dashboard/overdue");
  if (!stats.ok) { host.innerHTML = '<div class="empty"><span class="big">⚠️</span>Не удалось загрузить данные</div>'; return; }
  const s = stats.data;
  const upRows = (up.data || []).map(e => execTr(e)).join("");
  const overRows = (over.data || []).map(e => execTr(e, true)).join("");
  host.innerHTML =
    '<div class="stats">' +
      statCard("Объектов", s.ObjectsCount, "на обслуживании", "") +
      statCard("Видов работ", s.WorksCount, "регламенты ПБ", "moon") +
      statCard("Назначений", s.AssignmentsCount, "активных договоров", "moon") +
      statCard("В этом месяце", s.MonthDone + " / " + s.MonthTotal, "выполнено работ", "") +
      statCard("Просрочено", s.Overdue, s.Overdue > 0 ? "требуют внимания" : "всё по графику", s.Overdue > 0 ? "danger" : "ok") +
    "</div>" +
    '<div class="dash-cols">' +
      '<div class="panel"><h3>Ближайшие работы</h3>' +
        (upRows ? listTable(upRows) : '<div class="empty">Пока ничего не запланировано</div>') +
      "</div>" +
      '<div class="panel"><h3>Просроченные</h3>' +
        (overRows ? listTable(overRows) : '<div class="empty"><span class="big">✅</span>Просрочек нет</div>') +
      "</div>" +
    "</div>";
}

/* ---------- календарь ---------- */
let calY = new Date().getFullYear();
let calM = new Date().getMonth() + 1;
let calObj = "", calWork = "", calStatus = "";

async function loadCalendar(dir) {
  await ensureCaches();
  const host = $("#page-calendar");
  let url = "/api/executions/?year=" + calY + "&month=" + calM;
  if (calObj) url += "&object_id=" + encodeURIComponent(calObj);
  if (calWork) url += "&work_id=" + encodeURIComponent(calWork);
  if (calStatus) url += "&status=" + encodeURIComponent(calStatus);
  const r = await api(url);
  const events = r.ok ? r.data : [];

  const first = new Date(calY, calM - 1, 1);
  const startDow = (first.getDay() + 6) % 7;
  const daysInMonth = new Date(calY, calM, 0).getDate();
  const prevDays = new Date(calY, calM - 1, 0).getDate();
  const today = todayISO();

  let cells = DOWS.map((d, i) => '<div class="cal-dow' + (i > 4 ? " we" : "") + '">' + d + "</div>").join("");
  for (let i = startDow - 1; i >= 0; i--) cells += '<div class="cal-cell out"><div class="dnum">' + (prevDays - i) + "</div></div>";

  for (let d = 1; d <= daysInMonth; d++) {
    const iso = calY + "-" + String(calM).padStart(2, "0") + "-" + String(d).padStart(2, "0");
    const dayEv = events.filter(e => e.PlannedDate === iso);
    const we = (startDow + d - 1) % 7 > 4;
    const chips = dayEv.slice(0, 3).map(e => {
      if (e.IsDeleted) {
        return '<div class="chip cancel" title="Удалено: ' + esc(e.DeletedReason) + '">🗑 ' + esc(e.WorkName) + "</div>";
      }
      let cls = "plan";
      if (e.Status === "Выполнено") cls = "done";
      else if (e.Status === "Отменено") cls = "cancel";
      else if (e.Status === "Перенесено") cls = "move";
      else if (e.IsOverdue) cls = "over";
      return '<div class="chip ' + cls + '" title="' + esc(e.ObjectName) + " — " + esc(e.WorkName) + '">' + esc(e.WorkName) + "</div>";
    }).join("");
    const more = dayEv.length > 3 ? '<div class="cal-more">+' + (dayEv.length - 3) + " ещё</div>" : "";
    cells += '<div class="cal-cell' + (iso === today ? " today" : "") + (we ? " we" : "") + '" data-action="open-day" data-date="' + iso + '">' +
      '<div class="dnum">' + d + "</div>" + chips + more + "</div>";
  }
  const tail = (7 - ((startDow + daysInMonth) % 7)) % 7;
  for (let i = 1; i <= tail; i++) cells += '<div class="cal-cell out"><div class="dnum">' + i + "</div></div>";

  host.innerHTML =
    '<div class="cal-head">' +
      '<button class="cal-nav" data-action="cal-prev" title="Предыдущий месяц">‹</button>' +
      '<div class="cal-title">' + MONTHS[calM - 1] + '<span class="yr">' + calY + "</span></div>" +
      '<button class="cal-nav" data-action="cal-next" title="Следующий месяц">›</button>' +
      '<button class="btn btn-ghost btn-sm" data-action="cal-today">Сегодня</button>' +
      '<div class="cal-spacer"></div>' +
      selectHtml("calFObj", objectsCache.map(o => ({ value: o.ID, label: o.Name })), calObj, "Все объекты") +
      selectHtml("calFWork", worksCache.map(w => ({ value: w.ID, label: w.Code + " · " + w.Name })), calWork, "Все работы") +
      selectHtml("calFStatus", ["Запланировано", "Выполнено", "Перенесено", "Отменено"].map(s => ({ value: s, label: s })), calStatus, "Все статусы") +
    "</div>" +
    '<div class="cal-grid" id="calGrid">' + cells + "</div>" +
    '<div class="cal-legend">' +
      '<span><i style="background:var(--moon)"></i>Запланировано</span>' +
      '<span><i style="background:var(--moss)"></i>Выполнено</span>' +
      '<span><i style="background:var(--amber)"></i>Перенесено</span>' +
      '<span><i style="background:var(--ember)"></i>Просрочено</span>' +
      '<span><i style="background:var(--text-3)"></i>Отменено</span>' +
    "</div>";

  $("#calFObj").addEventListener("change", e => { calObj = e.target.value; loadCalendar(); });
  $("#calFWork").addEventListener("change", e => { calWork = e.target.value; loadCalendar(); });
  $("#calFStatus").addEventListener("change", e => { calStatus = e.target.value; loadCalendar(); });
  if (dir) $("#calGrid").classList.add(dir === "left" ? "slide-l" : "slide-r");
}

async function openDay(iso) {
  const r = await api("/api/executions/by-date?date=" + iso);
  if (!r.ok) return;
  const evs = r.data;
  const title = new Date(iso + "T00:00:00").toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
  let body;
  if (!evs.length) {
    body = '<div class="empty"><span class="big">🌙</span>На эту дату ничего не запланировано</div>';
  } else {
    const pendings = evs.filter(e => !e.IsDeleted && e.Status !== "Выполнено" && e.Status !== "Отменено");
    const batchBarHtml = pendings.length > 0 ? `
      <div class="batch-bar">
        <div class="left">
          <label style="display:flex;align-items:center;gap:6px;cursor:pointer">
            <input type="checkbox" id="batchSelectAll"> Выбрать все (${pendings.length})
          </label>
        </div>
        <div class="right">
          <input type="text" class="inp" id="batchPerformer" placeholder="Исполнитель (ФИО)">
          <button class="btn btn-done btn-sm" id="batchDoneBtn" data-date="${iso}">✓ Выполнить выбранные</button>
        </div>
      </div>
    ` : "";

    const rows = evs.map(e => {
      if (e.IsDeleted) {
        return "<tr><td></td><td><b>" + esc(e.ObjectName) + '</b><div class="sub">' + esc(e.ObjectAddress) + "</div></td>" +
          "<td>" + esc(e.WorkCode) + " · " + esc(e.WorkName) + "</td>" +
          "<td>" + freqBadge(e.Frequency) + "</td>" +
          '<td><span class="badge b-cancel">Удалено</span><div class="sub">' + esc(e.DeletedReason) + "</div></td>" +
          '<td class="mono">—</td>' +
          '<td><div class="row-actions"><button class="btn btn-ghost btn-sm" data-action="assign-restore" data-id="' + esc(e.AssignmentId) + '">↩ Восстановить</button></div></td></tr>';
      }
      const closed = e.Status === "Выполнено" || e.Status === "Отменено";
      const cbHtml = !closed ? `<input type="checkbox" class="batch-cb" value="${esc(e.ID)}">` : "";
      const actions = closed
        ? '<span style="color:var(--text-3)">—</span>'
        : '<button class="btn btn-done btn-sm" data-action="exec-done" data-id="' + esc(e.ID) + '" data-date="' + iso + '" title="Отметить выполнение">✓</button>' +
          '<button class="btn btn-ghost btn-sm" data-action="exec-move" data-id="' + esc(e.ID) + '" title="Перенести">↻</button>' +
          '<button class="btn btn-danger btn-sm" data-action="exec-cancel" data-id="' + esc(e.ID) + '" title="Отменить">✕</button>';
      return "<tr><td style='width:24px;text-align:center'>" + cbHtml + "</td><td><b>" + esc(e.ObjectName) + '</b><div class="sub">' + esc(e.ObjectAddress) + "</div></td>" +
        "<td>" + esc(e.WorkCode) + " · " + esc(e.WorkName) + "</td>" +
        "<td>" + freqBadge(e.Frequency) + "</td>" +
        "<td>" + statusBadge(e.Status, e.IsOverdue) + "</td>" +
        '<td class="mono">' + (e.ActualDate ? fmtDate(e.ActualDate) : "—") + "</td>" +
        '<td><div class="row-actions">' + actions + "</div>" +
        '<div class="resched hidden" id="rs-' + esc(e.ID) + '">' +
          '<input type="date" class="inp" id="rsd-' + esc(e.ID) + '" value="' + iso + '">' +
          '<button class="btn btn-amber btn-sm" data-action="exec-move-save" data-id="' + esc(e.ID) + '">OK</button>' +
        "</div></td></tr>";
    }).join("");
    body = batchBarHtml + '<table><thead><tr><th style="width:24px"></th><th>Объект</th><th>Работа</th><th>Периодичность</th><th>Статус</th><th>Факт</th><th>Действия</th></tr></thead><tbody>' + rows + "</tbody></table>";
  }
  openModal(
    '<div class="modal-head"><div class="modal-title">📅 ' + title + '</div><button class="modal-x" data-action="modal-close">×</button></div>' +
    body +
    '<div class="modal-foot" style="justify-content:space-between">' +
      '<button class="btn btn-ghost" data-action="assign-new" data-date="' + iso + '">+ Назначить на эту дату</button>' +
      '<button class="btn btn-ghost" data-action="modal-close">Закрыть</button>' +
    "</div>"
  );

  const selAll = $("#batchSelectAll");
  if (selAll) {
    selAll.addEventListener("change", e => {
      $$(".batch-cb").forEach(cb => cb.checked = e.target.checked);
    });
  }

  const bDone = $("#batchDoneBtn");
  if (bDone) {
    bDone.addEventListener("click", async () => {
      const selected = $$(".batch-cb:checked").map(cb => cb.value);
      if (!selected.length) { notice("Выберите хотя бы одно выполнение", "error"); return; }
      const perf = ($("#batchPerformer") ? $("#batchPerformer").value : "").trim();
      const res = await api("/api/executions/batch-done", {
        ExecutionIds: selected,
        ActualDate: iso,
        PerformedBy: perf
      });
      if (res.ok) {
        notice(`Выполнено работ: ${res.updated}`);
        closeModal();
        loadCalendar();
        loadNavBadges();
      } else {
        notice(res.detail || "Ошибка выполнения", "error");
      }
    });
  }
}


/* ---------- объекты ---------- */
async function loadObjects() {
  const r = await api("/api/objects/");
  if (!r.ok) return;
  objectsCache = r.data;
  const rows = r.data.map(o => {
    const fpoBadge = '<span class="tag-fpo">' + esc(o.FunctionalHazard || "Ф3.1") + "</span>";
    const fireCatBadge = '<span class="tag-fire-cat">' + esc(o.FireHazardCategory || "В") + "</span>";
    const paramsText = (o.TotalArea ? o.TotalArea + " м²" : "—") + (o.Floors ? " · " + o.Floors + " эт." : "");
    return "<tr><td><b>" + esc(o.Name) + '</b><div class="sub">' + esc(o.Address) + "</div></td>" +
      "<td>" + esc(o.Category || "—") + '<div style="margin-top:3px;display:flex;gap:4px;align-items:center;">' + fpoBadge + " " + fireCatBadge + "</div></td>" +
      '<td class="mono" style="font-size:12px;">' + paramsText + "</td>" +
      '<td class="mono">' + o.AssignmentsCount + "</td>" +
      '<td class="mono">' + o.ExecutionsDone + " / " + o.ExecutionsTotal + "</td>" +
      "<td>" + (o.Overdue ? '<span class="badge b-over">' + o.Overdue + "</span>" : '<span class="badge b-done">0</span>') + "</td>" +
      '<td><div class="row-actions">' +
        '<button class="btn btn-ghost btn-sm" data-action="ai-audit-obj" data-id="' + esc(o.ID) + '" title="Аудит норм и регламентов ПБ">🤖 ИИ</button>' +
        '<button class="btn btn-ghost btn-sm" data-action="obj-view" data-id="' + esc(o.ID) + '">Открыть</button>' +
        '<button class="btn btn-ghost btn-sm" data-action="obj-edit" data-id="' + esc(o.ID) + '">✎</button>' +
        '<button class="btn btn-danger btn-sm" data-action="obj-delete" data-id="' + esc(o.ID) + '" data-name="' + esc(o.Name) + '">✕</button>' +
      "</div></td></tr>";
  }).join("");
  const aiToolbarBtn = (aiStatusCache.enabled && aiStatusCache.has_api_key)
    ? '<button class="btn btn-ghost" data-action="open-ai" style="color:#4ade80;border-color:rgba(34,197,94,0.45);background:rgba(34,197,94,0.08);"><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#4ade80;margin-right:6px;box-shadow:0 0 8px #4ade80;"></span>🤖 ИИ: Онлайн (Активен)</button>'
    : '<button class="btn btn-ghost" data-action="open-ai" style="color:var(--amber-2);border-color:rgba(245,165,36,0.5);background:rgba(245,165,36,0.08);"><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--amber-2);margin-right:6px;"></span>✍️ ИИ: НЕТ API (Ручной ввод)</button>';

  $("#page-objects").innerHTML =
    '<div class="toolbar">' +
      '<button class="btn btn-amber" data-action="obj-new">+ Новый объект</button>' +
      aiToolbarBtn +
      '<div class="search-box"><input type="text" class="inp" id="objSearch" placeholder="Поиск объектов…"></div>' +
      '<span class="toolbar-hint">Всего: <span id="objCount">' + r.data.length + '</span></span>' +
    '</div>' +
    '<div class="panel table-panel"><table id="objectsTable"><thead><tr><th>Объект</th><th>Класс ФПО / Кат.</th><th>Площадь/Этажи</th><th>Назначений</th><th>Выполнено</th><th>Просрочено</th><th></th></tr></thead><tbody>' +
    (rows || '<tr><td colspan="7"><div class="empty"><span class="big">⌂</span>Объектов пока нет — добавьте первый</div></td></tr>') +
    "</tbody></table></div>";

  const searchInput = $("#objSearch");
  if (searchInput) {
    searchInput.addEventListener("input", e => {
      const q = e.target.value.toLowerCase().trim();
      const trs = $$("#objectsTable tbody tr");
      let visible = 0;
      trs.forEach(tr => {
        const text = tr.innerText.toLowerCase();
        const match = !q || text.includes(q);
        tr.classList.toggle("hidden-row", !match);
        if (match) visible++;
      });
      const cnt = $("#objCount");
      if (cnt) cnt.textContent = visible;
    });
  }
}


function objectFormModal(o) {
  o = o || {};
  const fpoList = [
    { code: "Ф3.1", name: "Ф3.1 — Торговые центры, супермаркеты, магазины" },
    { code: "Ф4.3", name: "Ф4.3 — Офисы, бизнес-центры, банки, управления" },
    { code: "Ф5.2", name: "Ф5.2 — Складские здания, логистические центры, стоянки" },
    { code: "Ф5.1", name: "Ф5.1 — Производственные цеха, мастерские, лаборатории" },
    { code: "Ф1.1", name: "Ф1.1 — Школы, детсады, больницы, спальные корпуса" },
    { code: "Ф1.2", name: "Ф1.2 — Гостиницы, общежития, мотели" },
    { code: "Ф1.3", name: "Ф1.3 — Многоквартирные жилые дома" },
    { code: "Ф2.1", name: "Ф2.1 — Театры, кинотеатры, концертные залы" },
    { code: "Ф3.2", name: "Ф3.2 — Кафе, рестораны, столовые, общепит" },
    { code: "Ф3.4", name: "Ф3.4 — Поликлиники и амбулатории" },
    { code: "Ф3.5", name: "Ф3.5 — Почты, сберкассы, транспортные агентства" },
    { code: "Ф5.3", name: "Ф5.3 — Сельскохозяйственные здания" },
  ];

  const fireCatList = [
    { code: "В", name: "Категория В (В1-В4 — пожароопасная)" },
    { code: "А", name: "Категория А (повышенная взрывопожароопасность)" },
    { code: "Б", name: "Категория Б (взрывопожароопасность)" },
    { code: "Г", name: "Категория Г (умеренная пожароопасность)" },
    { code: "Д", name: "Категория Д (пониженная пожароопасность)" },
    { code: "Не категорируется", name: "Не категорируется (общественные/жилые здания)" },
  ];

  const currentFpo = o.FunctionalHazard || "Ф3.1";
  const currentFireCat = o.FireHazardCategory || "В";
  const currentArea = o.TotalArea || "";
  const currentFloors = o.Floors || 1;

  openModal(
    '<div class="modal-head"><div class="modal-title">' + (o.ID ? "Редактировать объект" : "Новый объект (Нормы ПБ)") + '</div><button class="modal-x" data-action="modal-close">×</button></div>' +
    '<div class="field"><label>Название *</label><input class="inp" id="f-obj-name" value="' + esc(o.Name || "") + '"></div>' +
    '<div class="field"><label>Адрес *</label><input class="inp" id="f-obj-addr" value="' + esc(o.Address || "") + '"></div>' +
    '<div class="grid2">' +
      '<div class="field"><label>Контактное лицо</label><input class="inp" id="f-obj-contact" value="' + esc(o.ContactPerson || "") + '"></div>' +
      '<div class="field"><label>Телефон</label><input class="inp" id="f-obj-phone" value="' + esc(o.Phone || "") + '"></div>' +
    "</div>" +
    '<div class="grid2">' +
      '<div class="field"><label>ИНН</label><input class="inp" id="f-obj-inn" value="' + esc(o.Inn || "") + '"></div>' +
      '<div class="field"><label>Email</label><input class="inp" id="f-obj-email" value="' + esc(o.Email || "") + '"></div>' +
    "</div>" +
    '<div class="grid2">' +
      '<div class="field"><label>Тип / Назначение</label><select class="inp" id="f-obj-cat">' +
        ["Торговый центр", "Офис", "Склад", "Производство", "Школа", "Больница", "Другое"].map(c => '<option' + (o.Category === c ? " selected" : "") + ">" + c + "</option>").join("") +
      "</select></div>" +
      '<div class="field"><label>Класс функциональной опасности (ФПО)</label><select class="inp" id="f-obj-fpo">' +
        fpoList.map(item => '<option value="' + item.code + '"' + (currentFpo === item.code ? " selected" : "") + ">" + item.name + "</option>").join("") +
      "</select></div>" +
    "</div>" +
    '<div class="grid2">' +
      '<div class="field"><label>Категория взрывопожароопасности</label><select class="inp" id="f-obj-firecat">' +
        fireCatList.map(item => '<option value="' + item.code + '"' + (currentFireCat === item.code ? " selected" : "") + ">" + item.name + "</option>").join("") +
      "</select></div>" +
      '<div class="grid2">' +
        '<div class="field"><label>Общая площадь (м²)</label><input class="inp" type="number" id="f-obj-area" value="' + esc(currentArea) + '" min="0" step="any"></div>' +
        '<div class="field"><label>Этажность</label><input class="inp" type="number" id="f-obj-floors" value="' + esc(currentFloors) + '" min="1" max="100"></div>' +
      '</div>' +
    "</div>" +
    '<div style="margin:4px 0 12px; display:flex; justify-content:flex-end;">' +
      (aiStatusCache.enabled && aiStatusCache.has_api_key
        ? '<button type="button" class="btn btn-ghost btn-sm" id="btnAiAutofill" style="color:#4ade80;border-color:rgba(34,197,94,0.4);font-size:12px;background:rgba(34,197,94,0.08);">' +
            '✨ Автоподбор параметров через ИИ' +
          '</button>'
        : '<div style="font-size:12px;color:var(--amber-2);display:flex;align-items:center;gap:6px;background:rgba(245,165,36,0.08);padding:4px 10px;border-radius:6px;border:1px solid rgba(245,165,36,0.35);">' +
            '<span>✍️</span> <b>Нет API-ключа в msg.cfg</b> — заполните параметры объекта вручную' +
          '</div>') +
    '</div>' +
    '<div class="field"><label>Примечания и характеристики</label><textarea class="inp" id="f-obj-notes" rows="2">' + esc(o.Notes || "") + "</textarea></div>" +
    '<div class="modal-foot"><button class="btn btn-ghost" data-action="modal-close">Отмена</button>' +
    '<button class="btn btn-amber" data-action="obj-save" data-id="' + esc(o.ID || "") + '">Сохранить</button></div>'
  );

  const btnAi = document.getElementById("btnAiAutofill");
  if (btnAi && aiStatusCache.enabled) {
    btnAi.addEventListener("click", async () => {
      const cat = $("#f-obj-cat").value;
      const r = await api("/api/ai/preset", { query: cat });
      if (r.ok && r.preset) {
        if (r.preset.functional_hazard) $("#f-obj-fpo").value = r.preset.functional_hazard;
        if (r.preset.fire_hazard_category) $("#f-obj-firecat").value = r.preset.fire_hazard_category;
        if (!$("#f-obj-notes").value) $("#f-obj-notes").value = r.preset.notes || "";
        notice("Параметры ПБ предзаполнены ИИ для: " + cat);
      }
    });
  }
}

async function saveObject(id) {
  const data = {
    Name: $("#f-obj-name").value.trim(),
    Address: $("#f-obj-addr").value.trim(),
    ContactPerson: $("#f-obj-contact").value.trim(),
    Phone: $("#f-obj-phone").value.trim(),
    Inn: $("#f-obj-inn").value.trim(),
    Email: $("#f-obj-email").value.trim(),
    Category: $("#f-obj-cat").value,
    FunctionalHazard: $("#f-obj-fpo").value,
    FireHazardCategory: $("#f-obj-firecat").value,
    ConstructionHazard: "С0",
    TotalArea: parseFloat($("#f-obj-area").value) || 0.0,
    Floors: parseInt($("#f-obj-floors").value) || 1,
    Notes: $("#f-obj-notes").value.trim(),
  };
  if (!data.Name || !data.Address) { toast("Заполните название и адрес", "error"); return; }
  const r = id ? await api("/api/objects/" + id, data, "PUT") : await api("/api/objects/", data);
  if (r.ok) { notice(id ? "Объект обновлён" : "Объект добавлен"); closeModal(); loadObjects(); }
  else notice(r.detail || "Ошибка", "error");
}

async function viewObject(id) {
  const r = await api("/api/objects/" + id);
  const a = await api("/api/assignments/?object_id=" + id);
  const aDel = await api("/api/assignments/?object_id=" + id + "&include_deleted=true");
  if (!r.ok) return;
  const o = r.data;
  const assigns = a.ok ? a.data : [];
  const deletedCount = (aDel.ok ? aDel.data.length : 0) - assigns.length;
  const total = assigns.reduce((s, x) => s + (x.TotalPrice || 0), 0);
  const aRows = assigns.map(x => {
    const pct = x.ExecutionsTotal ? Math.round(x.ExecutionsDone / x.ExecutionsTotal * 100) : 0;
    return "<tr><td><b>" + esc(x.WorkName) + '</b><div class="sub mono">' + esc(x.WorkCode) + "</div></td>" +
      "<td>" + freqBadge(x.Frequency) + "</td>" +
      '<td class="mono">' + fmtDate(x.StartDate) + '<div class="sub">по ' + fmtDate(x.EndDate) + "</div></td>" +
      '<td class="mono">' + fmtMoney(x.TotalPrice) + "</td>" +
      '<td><div class="progress"><i style="width:' + pct + '%"></i></div><div class="sub">' + x.ExecutionsDone + " / " + x.ExecutionsTotal + " · " + pct + "%</div></td>" +
      '<td><div class="row-actions">' +
        '<button class="btn btn-ghost btn-sm" data-action="assign-regen" data-id="' + esc(x.ID) + '" title="Перегенерировать расписание">↻</button>' +
        '<button class="btn btn-danger btn-sm" data-action="assign-delete" data-id="' + esc(x.ID) + '" data-work="' + esc(x.WorkName) + '">✕</button>' +
      "</div></td></tr>";
  }).join("");

  const fpoBadge = '<span class="tag-fpo">' + esc(o.FunctionalHazard || "Ф3.1") + "</span>";
  const fireCatBadge = '<span class="tag-fire-cat">Кат. ' + esc(o.FireHazardCategory || "В") + "</span>";

  openModal(
    '<div class="modal-head"><div class="modal-title">⌂ ' + esc(o.Name) + '</div><button class="modal-x" data-action="modal-close">×</button></div>' +
    '<div class="kv">' +
      kv("Адрес", o.Address) +
      kv("Контакт", (o.ContactPerson || "—") + " " + (o.Phone || "")) +
      kv("Класс ФПО / Категория", fpoBadge + " " + fireCatBadge) +
      kv("Параметры здания", (o.TotalArea ? o.TotalArea + " м²" : "—") + " · " + (o.Floors ? o.Floors + " эт." : "1 эт.")) +
    "</div>" +
    '<div class="panel" style="margin-bottom:16px"><h3>Назначения (' + assigns.length + ")</h3>" +
      (deletedCount > 0 ? '<div class="sub" style="margin:-8px 0 12px 0;">В архиве: ' + deletedCount + ' (видны в календаре с пометкой «Удалено»)</div>' : "") +
      (aRows
        ? '<table><thead><tr><th>Работа</th><th>Периодичность</th><th>Период</th><th>Сумма</th><th>Прогресс</th><th></th></tr></thead><tbody>' + aRows + "</tbody></table>"
        : '<div class="empty">Назначений пока нет</div>') +
    "</div>" +
    '<div class="kv">' +
      '<div><div class="k">Итого по договорам</div><div class="v" style="font-family:var(--font-display);font-size:20px;color:var(--amber-2)">' + fmtMoney(total) + "</div></div>" +
      '<div><div class="k">Выполнено работ</div><div class="v">' + o.ExecutionsDone + " из " + o.ExecutionsTotal + "</div></div>" +
      '<div><div class="k">Просрочено</div><div class="v" style="color:' + (o.Overdue ? "var(--ember)" : "var(--moss)") + '">' + o.Overdue + "</div></div>" +
    "</div>" +
    '<div class="modal-foot" style="justify-content:space-between">' +
      '<div style="display:flex;gap:8px;">' +
        '<button class="btn btn-amber" data-action="assign-new" data-object="' + esc(o.ID) + '">+ Назначить работу</button>' +
        '<button class="btn btn-ghost" data-action="ai-audit-obj" data-id="' + esc(o.ID) + '" style="color:var(--amber-2);border-color:rgba(245,165,36,0.4)">🤖 ИИ-Аудит регламентов</button>' +
      '</div>' +
      '<div style="display:flex;gap:8px;">' +
        '<button class="btn btn-ghost" data-action="inv-new" data-object="' + esc(o.ID) + '">💸 Счёт</button>' +
        '<button class="btn btn-ghost" data-action="modal-close">Закрыть</button>' +
      '</div>' +
    "</div>"
  );
}

/* ---------- виды работ ---------- */
async function loadWorks() {
  const r = await api("/api/works/");
  if (!r.ok) return;
  worksCache = r.data;
  const rows = r.data.map(w =>
    '<td class="mono">' + esc(w.Code) + "</td>" +
    "<td><b>" + esc(w.Name) + '</b><div class="sub">' + esc(w.Description) + "</div></td>" +
    "<td>" + esc(w.Category || "—") + "</td>" +
    "<td>" + freqBadge(w.Frequency) + "</td>" +
    '<td class="mono">' + fmtMoney(w.Price) + "</td>" +
    '<td><div class="row-actions">' +
      '<button class="btn btn-ghost btn-sm" data-action="work-edit" data-id="' + esc(w.ID) + '">✎</button>' +
      '<button class="btn btn-danger btn-sm" data-action="work-delete" data-id="' + esc(w.ID) + '">✕</button>' +
    "</div></td>").map ? "" : "";
  const rowsHtml = r.data.map(w =>
    '<tr><td class="mono">' + esc(w.Code) + "</td>" +
    "<td><b>" + esc(w.Name) + '</b><div class="sub">' + esc(w.Description) + "</div></td>" +
    "<td>" + esc(w.Category || "—") + "</td>" +
    "<td>" + freqBadge(w.Frequency) + "</td>" +
    '<td class="mono">' + fmtMoney(w.Price) + "</td>" +
    '<td><div class="row-actions">' +
      '<button class="btn btn-ghost btn-sm" data-action="work-edit" data-id="' + esc(w.ID) + '">✎</button>' +
      '<button class="btn btn-danger btn-sm" data-action="work-delete" data-id="' + esc(w.ID) + '">✕</button>' +
    "</div></td></tr>").join("");
  $("#page-works").innerHTML =
    '<div class="toolbar">' +
      '<button class="btn btn-amber" data-action="work-new">+ Новый вид работы</button>' +
      '<div class="search-box"><input type="text" class="inp" id="workSearch" placeholder="Поиск видов работ…"></div>' +
      '<span class="toolbar-hint">Всего: <span id="workCount">' + r.data.length + '</span></span>' +
    '</div>' +
    '<div class="panel table-panel"><table id="worksTable"><thead><tr><th>Код</th><th>Название</th><th>Категория</th><th>Периодичность</th><th>Цена</th><th></th></tr></thead><tbody>' +
    (rowsHtml || '<tr><td colspan="6"><div class="empty"><span class="big">⚙</span>Справочник пуст</div></td></tr>') +
    "</tbody></table></div>";

  const searchInput = $("#workSearch");
  if (searchInput) {
    searchInput.addEventListener("input", e => {
      const q = e.target.value.toLowerCase().trim();
      const trs = $$("#worksTable tbody tr");
      let visible = 0;
      trs.forEach(tr => {
        const text = tr.innerText.toLowerCase();
        const match = !q || text.includes(q);
        tr.classList.toggle("hidden-row", !match);
        if (match) visible++;
      });
      const cnt = $("#workCount");
      if (cnt) cnt.textContent = visible;
    });
  }
}


function workFormModal(w) {
  w = w || {};
  openModal(
    '<div class="modal-head"><div class="modal-title">' + (w.ID ? "Редактировать вид работы" : "Новый вид работы") + '</div><button class="modal-x" data-action="modal-close">×</button></div>' +
    '<div class="grid2"><div class="field"><label>Код *</label><input class="inp" id="f-w-code" value="' + esc(w.Code || "") + '" placeholder="ПБ-01.03"></div>' +
    '<div class="field"><label>Категория</label><input class="inp" id="f-w-cat" value="' + esc(w.Category || "") + '" placeholder="АПС"></div></div>' +
    '<div class="field"><label>Название *</label><input class="inp" id="f-w-name" value="' + esc(w.Name || "") + '"></div>' +
    '<div class="field"><label>Описание</label><textarea class="inp" id="f-w-desc" rows="2">' + esc(w.Description || "") + "</textarea></div>" +
    '<div class="grid2"><div class="field"><label>Периодичность по умолчанию</label><select class="inp" id="f-w-freq">' +
      FREQS.map(f => '<option' + ((w.Frequency || "Ежегодно") === f ? " selected" : "") + ">" + f + "</option>").join("") +
    "</select></div>" +
    '<div class="field"><label>Цена, ₽</label><input type="number" class="inp" id="f-w-price" value="' + (w.Price || 0) + '"></div></div>' +
    '<div class="grid2"><div class="field"><label>Длительность, ч</label><input type="number" class="inp" id="f-w-hours" value="' + (w.DurationHours || 1) + '"></div>' +
    '<div class="field"><label>Требуемый сертификат</label><input class="inp" id="f-w-cert" value="' + esc(w.RequiredCert || "") + '"></div></div>' +
    '<div class="modal-foot"><button class="btn btn-ghost" data-action="modal-close">Отмена</button>' +
    '<button class="btn btn-amber" data-action="work-save" data-id="' + esc(w.ID || "") + '">Сохранить</button></div>'
  );
}

async function saveWork(id) {
  const data = {
    Code: $("#f-w-code").value.trim(),
    Name: $("#f-w-name").value.trim(),
    Category: $("#f-w-cat").value.trim(),
    Frequency: $("#f-w-freq").value,
    Price: parseFloat($("#f-w-price").value) || 0,
    DurationHours: parseFloat($("#f-w-hours").value) || 0,
    RequiredCert: $("#f-w-cert").value.trim(),
    Description: $("#f-w-desc").value.trim(),
  };
  if (!data.Code || !data.Name) { toast("Заполните код и название", "error"); return; }
  const r = id ? await api("/api/works/" + id, data, "PUT") : await api("/api/works/", data);
  if (r.ok) { notice(id ? "Вид работы обновлён" : "Вид работы добавлен"); closeModal(); loadWorks(); }
  else notice(r.detail || "Ошибка", "error");
}

/* ---------- назначения ---------- */
async function loadAssignments() {
  await ensureCaches();
  const r = await api("/api/assignments/");
  if (!r.ok) return;
  const rows = r.data.map(x => {
    const pct = x.ExecutionsTotal ? Math.round(x.ExecutionsDone / x.ExecutionsTotal * 100) : 0;
    return "<tr><td><b>" + esc(x.ObjectName) + "</b></td>" +
      "<td>" + esc(x.WorkCode) + " · " + esc(x.WorkName) + "</td>" +
      "<td>" + freqBadge(x.Frequency) + "</td>" +
      '<td class="mono">' + fmtDate(x.StartDate) + '<div class="sub">по ' + fmtDate(x.EndDate) + "</div></td>" +
      '<td class="mono">' + fmtMoney(x.PricePerUnit) + '<div class="sub">итого ' + fmtMoney(x.TotalPrice) + "</div></td>" +
      '<td><div class="progress"><i style="width:' + pct + '%"></i></div><div class="sub">' + x.ExecutionsDone + " / " + x.ExecutionsTotal + "</div></td>" +
      '<td><div class="row-actions">' +
        '<button class="btn btn-ghost btn-sm" data-action="assign-regen" data-id="' + esc(x.ID) + '" title="Перегенерировать">↻</button>' +
        '<button class="btn btn-danger btn-sm" data-action="assign-delete" data-id="' + esc(x.ID) + '" data-work="' + esc(x.WorkName) + '">✕</button>' +
      "</div></td></tr>";
  }).join("");
  $("#page-assignments").innerHTML =
    '<div class="toolbar">' +
      '<button class="btn btn-amber" data-action="assign-new">+ Новое назначение</button>' +
      '<div class="search-box"><input type="text" class="inp" id="assignSearch" placeholder="Поиск назначений…"></div>' +
      '<span class="toolbar-hint">Всего: <span id="assignCount">' + r.data.length + '</span></span>' +
    '</div>' +
    '<div class="panel table-panel"><table id="assignmentsTable"><thead><tr><th>Объект</th><th>Работа</th><th>Периодичность</th><th>Период</th><th>Цена</th><th>Прогресс</th><th></th></tr></thead><tbody>' +
    (rows || '<tr><td colspan="7"><div class="empty"><span class="big">⧉</span>Назначений пока нет</div></td></tr>') +
    "</tbody></table></div>";

  const searchInput = $("#assignSearch");
  if (searchInput) {
    searchInput.addEventListener("input", e => {
      const q = e.target.value.toLowerCase().trim();
      const trs = $$("#assignmentsTable tbody tr");
      let visible = 0;
      trs.forEach(tr => {
        const text = tr.innerText.toLowerCase();
        const match = !q || text.includes(q);
        tr.classList.toggle("hidden-row", !match);
        if (match) visible++;
      });
      const cnt = $("#assignCount");
      if (cnt) cnt.textContent = visible;
    });
  }
}


async function assignmentFormModal(prefDate, prefObject) {
  await ensureCaches();
  if (!objectsCache.length) { toast("Сначала добавьте хотя бы один объект", "error"); return; }
  if (!worksCache.length) { toast("Справочник работ пуст", "error"); return; }
  const start = prefDate || todayISO();
  const end = new Date().getFullYear() + "-12-31";
  openModal(
    '<div class="modal-head"><div class="modal-title">Новое назначение</div><button class="modal-x" data-action="modal-close">×</button></div>' +
    '<div class="field"><label>Объект *</label><select class="inp" id="f-a-obj">' +
      objectsCache.map(o => '<option value="' + esc(o.ID) + '"' + (prefObject === o.ID ? " selected" : "") + ">" + esc(o.Name) + " — " + esc(o.Address) + "</option>").join("") +
    "</select></div>" +
    '<div class="field"><label>Вид работы *</label><select class="inp" id="f-a-work">' +
      worksCache.map(w => '<option value="' + esc(w.ID) + '" data-price="' + (w.Price || 0) + '" data-freq="' + esc(w.Frequency || "") + '">' + esc(w.Code) + " — " + esc(w.Name) + " (" + fmtMoney(w.Price) + ")</option>").join("") +
    "</select></div>" +
    '<div class="grid2"><div class="field"><label>Периодичность *</label><select class="inp" id="f-a-freq">' +
      FREQS.map(f => "<option>" + f + "</option>").join("") +
    "</select></div>" +
    '<div class="field"><label>Цена за выполнение, ₽</label><input type="number" class="inp" id="f-a-price" value="0"></div></div>' +
    '<div class="grid2"><div class="field"><label>Дата начала *</label><input type="date" class="inp" id="f-a-start" value="' + start + '"></div>' +
    '<div class="field"><label>Дата окончания *</label><input type="date" class="inp" id="f-a-end" value="' + end + '"></div></div>' +
    '<div class="field"><label>Ответственный</label><input class="inp" id="f-a-resp" placeholder="ФИО"></div>' +
    '<div class="preview" id="aPreview"></div>' +
    '<div class="modal-foot"><button class="btn btn-ghost" data-action="modal-close">Отмена</button>' +
    '<button class="btn btn-amber" data-action="assign-save">Создать с авторасчётом дат</button></div>'
  );
  const workSel = $("#f-a-work");
  const syncFromWork = () => {
    const opt = workSel.selectedOptions[0];
    if (!opt) return;
    $("#f-a-price").value = opt.dataset.price || 0;
    const f = opt.dataset.freq || "";
    if (FREQS.indexOf(f) !== -1) $("#f-a-freq").value = f;
    updateAssignPreview();
  };
  workSel.addEventListener("change", syncFromWork);
  ["f-a-freq", "f-a-price", "f-a-start", "f-a-end"].forEach(id => $("#" + id).addEventListener("input", updateAssignPreview));
  syncFromWork();
}

function freqMonths(f) {
  if (f === "Разовая") return 0;
  if (f === "Еженедельно") return -7;
  if (f === "Ежемесячно") return 1;
  if (f === "Ежеквартально") return 3;
  if (f === "Раз в полгода") return 6;
  if (f === "Ежегодно") return 12;
  if (f === "Раз в 3 года") return 36;
  if (f === "Раз в 5 лет") return 60;
  return 12;
}

function updateAssignPreview() {
  const box = $("#aPreview");
  if (!box) return;
  const freq = $("#f-a-freq").value;
  const start = $("#f-a-start").value;
  const end = $("#f-a-end").value;
  const price = parseFloat($("#f-a-price").value) || 0;
  if (!start || !end || new Date(end) < new Date(start)) {
    box.innerHTML = "⚠️ Укажите корректный период — и я посчитаю количество выполнений";
    return;
  }
  const m = freqMonths(freq);
  let qty = 0;
  if (m === 0) qty = 1;
  else if (m === -7) qty = Math.floor((new Date(end) - new Date(start)) / 604800000) + 1;
  else {
    const s = new Date(start), e = new Date(end);
    const months = (e.getFullYear() - s.getFullYear()) * 12 + (e.getMonth() - s.getMonth());
    qty = Math.max(1, Math.floor(months / m) + 1);
  }
  box.innerHTML = m === 0
    ? "🦉 Разовое выполнение — <b>" + fmtDate(start) + "</b>, сумма <b>" + fmtMoney(price) + "</b>"
    : "🔁 " + esc(freq) + " · выполнений: <b>" + qty + "</b> · сумма: <b>" + fmtMoney(price * qty) + "</b>";
}

async function saveAssignment() {
  const data = {
    ObjectId: $("#f-a-obj").value,
    WorkId: $("#f-a-work").value,
    Frequency: $("#f-a-freq").value,
    StartDate: $("#f-a-start").value,
    EndDate: $("#f-a-end").value,
    PricePerUnit: parseFloat($("#f-a-price").value) || 0,
    Responsible: $("#f-a-resp").value.trim(),
  };
  if (!data.ObjectId || !data.WorkId || !data.StartDate || !data.EndDate) { toast("Заполните обязательные поля", "error"); return; }
  const r = await api("/api/assignments/", data);
  if (r.ok) {
    notice("Назначение создано · выполнений: " + r.created);
    closeModal();
    PAGES[currentPage].load();
  } else notice(r.detail || "Ошибка", "error");
}

/* ---------- журнал ---------- */
let jStatus = "", jObj = "";
async function loadJournal() {
  await ensureCaches();
  let url = "/api/executions/?year=" + new Date().getFullYear();
  if (jStatus) url += "&status=" + encodeURIComponent(jStatus);
  if (jObj) url += "&object_id=" + encodeURIComponent(jObj);
  const r = await api(url);
  const rows = (r.ok ? r.data : []).slice().reverse().map(e =>
    '<tr class="clickable" data-action="exec-open" data-id="' + esc(e.ID) + '">' +
    '<td class="mono">' + fmtDate(e.PlannedDate) + "</td>" +
    "<td><b>" + esc(e.ObjectName) + "</b></td>" +
    "<td>" + esc(e.WorkCode) + " · " + esc(e.WorkName) + "</td>" +
    "<td>" + freqBadge(e.Frequency) + "</td>" +
    "<td>" + statusBadge(e.Status, e.IsOverdue) + "</td>" +
    '<td class="mono">' + (e.ActualDate ? fmtDate(e.ActualDate) : "—") + "</td>" +
    "<td>" + (esc(e.PerformedBy) || "—") + "</td></tr>").join("");
  $("#page-journal").innerHTML =
    '<div class="toolbar">' +
      selectHtml("jFStatus", ["Запланировано", "Выполнено", "Перенесено", "Отменено"].map(s => ({ value: s, label: s })), jStatus, "Все статусы") +
      selectHtml("jFObj", objectsCache.map(o => ({ value: o.ID, label: o.Name })), jObj, "Все объекты") +
      '<span class="toolbar-hint">Клик по строке — открыть и изменить</span>' +
    "</div>" +
    '<div class="panel table-panel"><table><thead><tr><th>План</th><th>Объект</th><th>Работа</th><th>Периодичность</th><th>Статус</th><th>Факт</th><th>Исполнитель</th></tr></thead><tbody>' +
    (rows || '<tr><td colspan="7"><div class="empty"><span class="big">≡</span>Записей нет</div></td></tr>') +
    "</tbody></table></div>";
  $("#jFStatus").addEventListener("change", e => { jStatus = e.target.value; loadJournal(); });
  $("#jFObj").addEventListener("change", e => { jObj = e.target.value; loadJournal(); });
}

async function execModal(id) {
  const r = await api("/api/executions/" + id);
  if (!r.ok) return;
  const e = r.data;
  const deletedBanner = e.IsDeleted
    ? '<div style="background:var(--ember-soft);border:1px solid rgba(242,112,138,.35);border-radius:10px;padding:12px 14px;margin-bottom:16px;color:var(--ember);font-size:13px;">🗑 Задание удалено. Причина: <b>' + esc(e.DeletedReason) + '</b><div style="margin-top:10px;"><button class="btn btn-ghost btn-sm" data-action="assign-restore" data-id="' + esc(e.AssignmentId) + '">↩ Восстановить назначение</button></div></div>'
    : "";
  openModal(
    '<div class="modal-head"><div class="modal-title">Выполнение</div><button class="modal-x" data-action="modal-close">×</button></div>' +
    deletedBanner +
    '<div class="kv">' + kv("Объект", e.ObjectName) + kv("Работа", e.WorkCode + " · " + e.WorkName) +
      kv("Плановая дата", fmtDate(e.PlannedDate)) + kv("Периодичность", e.Frequency || "—") + "</div>" +
    '<div class="grid2"><div class="field"><label>Статус</label><select class="inp" id="f-e-status">' +
      ["Запланировано", "Выполнено", "Перенесено", "Отменено"].map(s => '<option' + (e.Status === s ? " selected" : "") + ">" + s + "</option>").join("") +
    "</select></div>" +
    '<div class="field"><label>Фактическая дата</label><input type="date" class="inp" id="f-e-actual" value="' + (e.ActualDate || "") + '"></div></div>' +
    '<div class="field"><label>Исполнитель</label><input class="inp" id="f-e-by" value="' + esc(e.PerformedBy) + '" placeholder="ФИО"></div>' +
    '<div class="field"><label>Примечания</label><textarea class="inp" id="f-e-notes" rows="2">' + esc(e.Notes) + "</textarea></div>" +
    '<div class="modal-foot"><button class="btn btn-ghost" data-action="modal-close">Отмена</button>' +
    '<button class="btn btn-amber" data-action="exec-save" data-id="' + esc(e.ID) + '">Сохранить</button></div>'
  );
}


/* ---------- модалка действия (вместо confirm/prompt) ---------- */
function actionModal(opts) {
  const danger = opts.danger ? "btn-danger" : "btn-amber";
  const inputs = (opts.inputs || []).map(f =>
    '<div class="field"><label>' + esc(f.label) + (f.required ? " *" : "") + '</label>' +
    (f.type === "textarea"
      ? '<textarea class="inp" id="am-' + f.id + '" rows="3" placeholder="' + esc(f.placeholder || "") + '"></textarea>'
      : '<input class="inp" id="am-' + f.id + '" type="' + (f.type || "text") + '" value="' + esc(f.value || "") + '" placeholder="' + esc(f.placeholder || "") + '">') +
    '</div>').join("");
  openModal(
    '<div class="modal-head"><div class="modal-title">' + esc(opts.title) + '</div><button class="modal-x" data-action="modal-close">×</button></div>' +
    '<div style="color:var(--text-2);font-size:13.5px;line-height:1.6;margin-bottom:14px;">' + (opts.body || "") + '</div>' +
    inputs +
    '<div class="modal-foot"><button class="btn btn-ghost" data-action="modal-close">Отмена</button>' +
    '<button class="btn ' + danger + '" id="am-confirm">' + esc(opts.confirmText || "Подтвердить") + '</button></div>'
  );
  const first = (opts.inputs || [])[0];
  if (first) { const elx = document.getElementById("am-" + first.id); if (elx) elx.focus(); }
  document.getElementById("am-confirm").addEventListener("click", () => {
    const values = {};
    for (const f of (opts.inputs || [])) {
      const elx = document.getElementById("am-" + f.id);
      values[f.id] = elx ? elx.value.trim() : "";
      if (f.required && !values[f.id]) {
        notice(f.label + " — обязательное поле", "error");
        if (elx) elx.focus();
        return;
      }
    }
    opts.onConfirm(values);
  });
}

/* ---------- плавное удаление строки таблицы ---------- */
function fadeRemove(el) {
  if (!el) return;
  el.style.transition = "opacity .22s ease";
  el.style.opacity = "0";
  setTimeout(() => el.remove(), 220);
}

/* ---------- восстановление удалённого назначения ---------- */
async function restoreAssignment(aid) {
  const r = await api("/api/assignments/" + aid + "/restore", {});
  if (r.ok) {
    notice("Назначение восстановлено");
    closeModal();
    PAGES[currentPage].load();
  } else {
    notice(r.detail || "Ошибка восстановления", "error");
  }
}

/* ---------- делегирование действий ---------- */
document.addEventListener("click", async ev => {
  const btn = ev.target.closest("[data-action]");
  if (!btn) return;
  const a = btn.dataset.action;
  const id = btn.dataset.id;
  switch (a) {
    case "nav": showPage(btn.dataset.page); break;
    case "modal-close": closeModal(); break;

    case "cal-prev":
      calM--; if (calM < 1) { calM = 12; calY--; }
      loadCalendar("right"); break;
    case "cal-next":
      calM++; if (calM > 12) { calM = 1; calY++; }
      loadCalendar("left"); break;
    case "cal-today": {
      const n = new Date(); calY = n.getFullYear(); calM = n.getMonth() + 1;
      loadCalendar("left"); break;
    }
    case "open-day": openDay(btn.dataset.date); break;

    case "exec-done":
      await api("/api/executions/" + id + "/done", { ActualDate: btn.dataset.date });
      notice("Отмечено как выполненное");
      closeModal(); PAGES[currentPage].load(); break;
    case "exec-move": $("#rs-" + id).classList.toggle("hidden"); break;
    case "exec-move-save": {
      const nd = $("#rsd-" + id).value;
      if (!nd) { notice("Укажите новую дату", "error"); break; }
      const r = await api("/api/executions/" + id + "/reschedule", { NewDate: nd });
      if (r.ok) { notice("Перенесено на " + fmtDate(nd), "amber"); closeModal(); PAGES[currentPage].load(); }
      else notice(r.detail || "Ошибка", "error");
      break;
    }
    case "exec-cancel":
      actionModal({
        title: "Отмена выполнения",
        danger: true,
        body: "Выполнение будет помечено как «Отменено» и останется в истории.",
        confirmText: "Отменить выполнение",
        onConfirm: async () => {
          const r = await api("/api/executions/" + id + "/cancel", {});
          if (r.ok) { notice("Выполнение отменено"); closeModal(); PAGES[currentPage].load(); }
          else notice(r.detail || "Ошибка", "error");
        }
      });
      break;
    case "exec-open": execModal(id); break;
    case "exec-save": {
      const r = await api("/api/executions/" + id, {
        Status: $("#f-e-status").value,
        ActualDate: $("#f-e-actual").value || null,
        PerformedBy: $("#f-e-by").value.trim(),
        Notes: $("#f-e-notes").value.trim(),
      }, "PUT");
      if (r.ok) { notice("Сохранено"); closeModal(); PAGES[currentPage].load(); }
      else notice(r.detail || "Ошибка", "error");
      break;
    }

    case "open-ai": openAiAdvisorModal(); break;
    case "ai-audit-obj": openAiAdvisorModal(btn.dataset.id); break;

    case "obj-new": objectFormModal(); break;
    case "obj-edit": { const r = await api("/api/objects/" + id); if (r.ok) objectFormModal(r.data); break; }
    case "obj-save": await saveObject(btn.dataset.id); break;
    case "obj-view": viewObject(id); break;
    case "obj-delete":
      actionModal({
        title: "Удаление объекта",
        danger: true,
        body: "<b>" + esc(btn.dataset.name) + "</b><br>Все назначения объекта будут перенесены в архив с причиной «Объект удалён» и исчезнут из календаря вместе с объектом. Данные остаются в базе.",
        inputs: [{ id: "reason", label: "Причина удаления", type: "textarea", required: true, placeholder: "Например: объект снят с обслуживания" }],
        confirmText: "Удалить объект",
        onConfirm: async (vals) => {
          const r = await api("/api/objects/" + id, { Reason: vals.reason }, "DELETE");
          if (r.ok) {
            closeModal();
            notice("Объект удалён. Назначений в архиве: " + r.archived_assignments);
            loadObjects();
          } else {
            notice(r.detail || "Ошибка удаления", "error");
          }
        }
      });
      break;

    case "work-new": workFormModal(); break;
    case "work-edit": { const r = await api("/api/works/" + id); if (r.ok) workFormModal(r.data); break; }
    case "work-save": await saveWork(btn.dataset.id); break;
    case "work-delete":
      actionModal({
        title: "Удаление вида работы",
        danger: true,
        body: "Вид работы будет удалён из справочника. Если он используется в назначениях — удаление будет отклонено.",
        confirmText: "Удалить",
        onConfirm: async () => {
          const r = await api("/api/works/" + id, undefined, "DELETE");
          if (r.ok) { closeModal(); notice("Вид работы удалён"); loadWorks(); }
          else notice(r.detail || "Ошибка", "error");
        }
      });
      break;

    case "assign-new": closeModal(); assignmentFormModal(btn.dataset.date, btn.dataset.object); break;
    case "assign-restore": await restoreAssignment(id); break;
    case "assign-save": await saveAssignment(); break;
    case "assign-regen":
      actionModal({
        title: "Перегенерация расписания",
        body: "Запланированные даты будут пересозданы по периодичности. Выполненные, перенесённые и отменённые выполнения сохранятся.",
        confirmText: "Перегенерировать",
        onConfirm: async () => {
          const r = await api("/api/assignments/" + id + "/regenerate", {});
          if (r.ok) {
            closeModal();
            notice("Расписание обновлено: +" + r.created + ", −" + r.removed);
            if (currentPage === "assignments") loadAssignments();
          } else {
            notice(r.detail || "Ошибка", "error");
          }
        }
      });
      break;
    case "assign-delete": {
      const rowEl = btn.closest("tr");
      const wName = btn.dataset.work || "назначение";
      actionModal({
        title: "Удаление назначения",
        danger: true,
        body: "<b>" + esc(wName) + "</b><br>Выполнения останутся в календаре с пометкой «Удалено» и указанием причины. Назначение можно будет восстановить из модалки дня.",
        inputs: [{ id: "reason", label: "Причина удаления", type: "textarea", required: true, placeholder: "Например: договор расторгнут, услуга больше не нужна" }],
        confirmText: "Удалить",
        onConfirm: async (vals) => {
          const r = await api("/api/assignments/" + id, { Reason: vals.reason }, "DELETE");
          if (r.ok) {
            closeModal();
            notice("Назначение удалено. Выполнения помечены в календаре.");
            fadeRemove(rowEl);
          } else {
            notice(r.detail || "Ошибка удаления", "error");
          }
        }
      });
      break;
    }
  }
});

/* ---------- старт ---------- */
(function init() {
  showPage("dashboard");
  checkAndUpdateAiStatus();
})();



// ===== INVOICES MODULE =====
function addBusinessDays(startISO, days) {
  const d = startISO ? new Date(startISO + "T00:00:00") : new Date();
  let added = 0;
  while (added < days) {
    d.setDate(d.getDate() + 1);
    if (d.getDay() !== 0 && d.getDay() !== 6) added++;
  }
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
}

function invStatusBadge(st) {
  const map = { "Выставлен": "b-plan", "Частично": "b-move", "Оплачен": "b-done", "Просрочен": "b-over", "Отменён": "b-cancel" };
  return '<span class="badge ' + (map[st] || "b-freq") + '">' + esc(st) + "</span>";
}

async function loadInvoices() {
  const host = $("#page-invoices");
  if (!host) return;
  host.innerHTML = '<div class="empty"><span class="big">💸</span>Загружаем счета…</div>';
  const r = await api("/api/invoices/");
  if (!r.ok) { host.innerHTML = '<div class="empty">Не удалось загрузить счета</div>'; return; }

  const rows = r.data.map(i => {
    const canPay = i.Status !== "Оплачен" && i.Status !== "Отменён" && (i.Debt || 0) > 0;
    const canCancel = i.Status !== "Оплачен" && i.Status !== "Отменён" && (i.PaidAmount || 0) === 0;
    const canDelete = (i.PaidAmount || 0) === 0;
    return `<tr>
      <td class="mono">${esc(i.Number)}<div class="sub">${fmtDate(i.Date)}</div></td>
      <td><b>${esc(i.ObjectName)}</b></td>
      <td><div style="font-size:12.5px;color:var(--text)">${esc(i.CompanyName || "—")}</div>${i.CompanyInn ? `<div class="sub">ИНН ${esc(i.CompanyInn)}</div>` : ""}</td>
      <td class="mono">${fmtMoney(i.Total)}<div class="sub">НДС: ${i.VatRate ? i.VatRate + "%" : "без НДС"}</div></td>
      <td class="mono">${fmtMoney(i.PaidAmount)} / ${fmtMoney(i.Total)}</td>
      <td>${invStatusBadge(i.Status)}</td>
      <td class="mono">${i.DueDate ? fmtDate(i.DueDate) : "—"}</td>
      <td><div class="row-actions">
        <button class="btn btn-ghost btn-sm" data-action="inv-print" data-id="${esc(i.ID)}" title="Печать счёта">🖨 Счёт</button>
        <button class="btn btn-ghost btn-sm" data-action="inv-act" data-id="${esc(i.ID)}" title="Печать акта выполненных работ">📄 Акт</button>
        ${canPay ? `<button class="btn btn-done btn-sm" data-action="inv-pay" data-id="${esc(i.ID)}" data-number="${esc(i.Number)}" data-debt="${i.Debt}" title="Оплатить">✓</button>` : ""}
        ${canCancel ? `<button class="btn btn-ghost btn-sm" data-action="inv-cancel" data-id="${esc(i.ID)}" title="Отменить">✕</button>` : ""}
        ${canDelete ? `<button class="btn btn-danger btn-sm" data-action="inv-delete" data-id="${esc(i.ID)}" title="Удалить">🗑</button>` : ""}
      </div></td>
    </tr>`;
  }).join("");

  host.innerHTML = `
    <div class="toolbar">
      <button class="btn btn-amber" data-action="inv-new">+ Новый счёт</button>
      <div class="search-box"><input type="text" class="inp" id="invSearch" placeholder="Поиск счетов…"></div>
      <button class="btn btn-ghost" data-action="inv-settings">🏛 Организации и реквизиты</button>
      <span class="toolbar-hint">Всего: <span id="invCount">${r.data.length}</span></span>
    </div>
    <div class="panel table-panel">
      <table id="invoicesTable">
        <thead><tr><th>№ / дата</th><th>Объект</th><th>Организация</th><th>Сумма</th><th>Оплачено</th><th>Статус</th><th>Срок</th><th></th></tr></thead>
        <tbody>${rows || '<tr><td colspan="8"><div class="empty"><span class="big">💸</span>Счетов пока нет</div></td></tr>'}</tbody>
      </table>
    </div>`;

  const searchInput = $("#invSearch");
  if (searchInput) {
    searchInput.addEventListener("input", e => {
      const q = e.target.value.toLowerCase().trim();
      const trs = $$("#invoicesTable tbody tr");
      let visible = 0;
      trs.forEach(tr => {
        const text = tr.innerText.toLowerCase();
        const match = !q || text.includes(q);
        tr.classList.toggle("hidden-row", !match);
        if (match) visible++;
      });
      const cnt = $("#invCount");
      if (cnt) cnt.textContent = visible;
    });
  }
}


async function openInvoiceModal(prefObjectId) {
  const compRes = await api("/api/companies/");
  const companies = (compRes.ok && Array.isArray(compRes.data)) ? compRes.data : [];
  if (!companies.length) {
    openCompanySettings("Сначала добавьте хотя бы одну организацию с реквизитами.");
    return;
  }

  const defaultComp = companies.find(x => x.is_default) || companies[0];

  if (typeof ensureCaches === "function") await ensureCaches();
  let objs = (typeof objectsCache !== "undefined" && objectsCache.length) ? objectsCache : [];
  if (!objs.length) {
    const rr = await api("/api/objects/");
    objs = rr.ok ? rr.data : [];
  }
  if (!objs.length) { notice("Сначала добавьте объект", "error"); return; }

  const defaultDue = addBusinessDays(todayISO(), 5);
  const defaultVat = defaultComp.vat_rate || 0;

  openModal(`
    <div class="modal-head"><div class="modal-title">Новый счёт</div><button class="modal-x" data-action="modal-close">×</button></div>
    <div class="grid2">
      <div class="field"><label>Организация (от кого счёт) *</label>
        <select class="inp" id="invCompany">
          ${companies.map(c => `<option value="${esc(c.id)}"${c.id === defaultComp.id ? " selected" : ""}>${esc(c.name)} (ИНН ${esc(c.inn)})${c.is_default ? " — [Основная]" : ""}</option>`).join("")}
        </select>
      </div>
      <div class="field"><label>Объект (плательщик) *</label>
        <select class="inp" id="invObject">${objs.map(o => `<option value="${esc(o.ID)}"${prefObjectId === o.ID ? " selected" : ""}>${esc(o.Name)} — ${esc(o.Address || "")}</option>`).join("")}</select>
      </div>
    </div>
    <div class="grid2">
      <div class="field"><label>Срок оплаты</label><input type="date" class="inp" id="invDue" value="${defaultDue}"><div class="sub">по умолчанию 5 банковских дней</div></div>
      <div class="field"><label>НДС</label>
        <select class="inp" id="invVat">
          <option value="0"${Number(defaultVat) === 0 ? " selected" : ""}>Без НДС</option>
          <option value="10"${Number(defaultVat) === 10 ? " selected" : ""}>НДС 10%</option>
          <option value="20"${Number(defaultVat) === 20 ? " selected" : ""}>НДС 20%</option>
        </select>
      </div>
    </div>
    <div class="field"><label><input type="checkbox" id="invAllDebt"> Включить весь долг объекта</label></div>
    <div class="field"><label>Позиции с долгом</label>
      <div id="invAssignments" style="max-height:260px;overflow:auto;border:1px solid var(--line);border-radius:10px;padding:10px;background:var(--bg-1)"></div>
    </div>
    <div class="field"><label>Примечание</label><textarea class="inp" id="invNotes" rows="2"></textarea></div>
    <div class="modal-foot">
      <button class="btn btn-ghost" data-action="modal-close">Отмена</button>
      <button class="btn btn-amber" data-action="inv-create">Сформировать счёт</button>
    </div>
  `);

  $("#invCompany").addEventListener("change", e => {
    const selectedC = companies.find(x => x.id === e.target.value);
    if (selectedC && $("#invVat")) {
      const v = Number(selectedC.vat_rate || 0);
      $("#invVat").value = String(v);
    }
  });

  $("#invObject").addEventListener("change", loadInvoiceAssignments);
  $("#invAllDebt").addEventListener("change", e => {
    $$("#invAssignments input[type=checkbox]").forEach(cb => { cb.disabled = e.target.checked; if (e.target.checked) cb.checked = true; });
  });

  loadInvoiceAssignments();
}

async function loadInvoiceAssignments() {
  const objId = $("#invObject") ? $("#invObject").value : "";
  const box = $("#invAssignments");
  if (!box) return;
  if (!objId) { box.innerHTML = '<div class="sub">Выберите объект</div>'; return; }

  box.innerHTML = '<div class="sub">Загрузка…</div>';
  const r = await api("/api/assignments/?object_id=" + encodeURIComponent(objId));
  const debts = (r.ok ? r.data : []).filter(a => (a.Debt || 0) > 0);

  if (!debts.length) {
    box.innerHTML = '<div class="sub" style="color:var(--moss)">Долгов нет — все назначения оплачены</div>';
    return;
  }

  box.innerHTML = debts.map(a => `
    <label style="display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--line);cursor:pointer">
      <input type="checkbox" value="${esc(a.ID)}" checked style="margin-top:3px">
      <span>
        <b>${esc(a.WorkName)}</b> <span class="sub">${esc(a.Frequency)}</span>
        <div class="sub">Долг: <b style="color:var(--ember)">${fmtMoney(a.Debt)}</b> · итого ${fmtMoney(a.TotalPrice)} · оплачено ${fmtMoney(a.PaidAmount || 0)}</div>
      </span>
    </label>`).join("");
}

async function saveInvoice() {
  const objectId = $("#invObject") ? $("#invObject").value : "";
  if (!objectId) { notice("Выберите объект", "error"); return; }

  const companyId = $("#invCompany") ? $("#invCompany").value : null;
  const includeAll = $("#invAllDebt") ? $("#invAllDebt").checked : false;
  const assignmentIds = includeAll ? [] : $$("#invAssignments input:checked").map(x => x.value);

  if (!includeAll && !assignmentIds.length) {
    notice("Выберите позиции или включите весь долг", "error");
    return;
  }

  const data = {
    ObjectId: objectId,
    CompanyId: companyId,
    IncludeAllDebt: includeAll,
    AssignmentIds: assignmentIds,
    DueDate: $("#invDue") ? ($("#invDue").value || null) : null,
    VatRate: parseFloat($("#invVat") ? $("#invVat").value : "0") || 0,
    Notes: $("#invNotes") ? $("#invNotes").value.trim() : ""
  };

  const r = await api("/api/invoices/", data);
  if (r.ok) {
    notice("Счёт " + r.data.Number + " создан");
    closeModal();
    if (typeof currentPage !== "undefined" && currentPage === "invoices") loadInvoices();
  } else {
    notice(r.detail || "Ошибка", "error");
    if (String(r.detail || "").toLowerCase().includes("реквизит")) openCompanySettings();
  }
}

// ===== УПРАВЛЕНИЕ НЕСКОЛЬКИМИ ОРГАНИЗАЦИЯМИ И РЕКВИЗИТАМИ =====
let companySettingsState = {
  list: [],
  selectedId: null,
  isNew: false
};

async function openCompanySettings(warn) {
  const r = await api("/api/companies/");
  const companies = (r.ok && Array.isArray(r.data)) ? r.data : [];
  companySettingsState.list = companies;
  companySettingsState.isNew = false;

  const def = companies.find(x => x.is_default) || companies[0];
  companySettingsState.selectedId = def ? def.id : null;

  renderCompanySettingsModal(warn);
}

function renderCompanySettingsModal(warn) {
  const { list, selectedId, isNew } = companySettingsState;
  const current = isNew ? {
    id: "",
    name: "",
    inn: "",
    kpp: "",
    ogrn: "",
    address: "",
    phone: "",
    email: "",
    bank: "",
    bik: "",
    account: "",
    corr_account: "",
    director: "",
    accountant: "",
    invoice_prefix: "СЧ",
    vat_rate: 0,
    is_default: list.length === 0
  } : (list.find(x => x.id === selectedId) || list[0] || {});

  const tabsHtml = `
    <div class="comp-tabs">
      ${list.map(c => `
        <button type="button" class="comp-tab-btn ${(!isNew && c.id === current.id) ? "active" : ""}" data-comp-select="${esc(c.id)}">
          🏛 ${esc(c.name || "Без названия")}
          ${c.is_default ? '<span class="comp-badge-def">Основная</span>' : ""}
        </button>
      `).join("")}
      <button type="button" class="comp-tab-btn ${isNew ? "active" : ""}" data-comp-action="new" style="border-style:dashed;color:var(--amber-2)">
        + Добавить организацию
      </button>
    </div>
  `;

  const actionsHtml = (!isNew && current.id) ? `
    <div class="comp-topbar">
      <div>
        <b>${esc(current.name)}</b>
        ${current.is_default ? '<span class="comp-badge-def" style="margin-left:8px">Основная организация для счетов</span>' : ""}
      </div>
      <div class="comp-card-actions">
        ${!current.is_default ? `<button type="button" class="btn btn-ghost btn-sm" data-comp-action="set-default" data-id="${esc(current.id)}">★ Сделать основной</button>` : ""}
        ${list.length > 1 ? `<button type="button" class="btn btn-danger btn-sm" data-comp-action="delete" data-id="${esc(current.id)}">🗑 Удалить</button>` : ""}
      </div>
    </div>
  ` : `<div class="comp-topbar"><b style="color:var(--amber-2)">Новая организация</b><span class="sub">Заполните реквизиты для выставления счетов</span></div>`;

  openModal(`
    <div class="modal-head"><div class="modal-title">Организации и реквизиты для счетов</div><button class="modal-x" data-action="modal-close">×</button></div>
    ${tabsHtml}
    ${actionsHtml}
    <input type="hidden" id="cs-id" value="${esc(current.id || "")}">
    <div class="grid2">
      <div class="field"><label>Название организации *</label><input class="inp" id="cs-name" placeholder="ООО «Пример»" value="${esc(current.name || "")}"></div>
      <div class="field"><label>ИНН *</label><input class="inp" id="cs-inn" placeholder="10 или 12 цифр" value="${esc(current.inn || "")}"></div>
    </div>
    <div class="grid2">
      <div class="field"><label>КПП</label><input class="inp" id="cs-kpp" placeholder="9 цифр (для юрлиц)" value="${esc(current.kpp || "")}"></div>
      <div class="field"><label>ОГРН / ОГРНИП</label><input class="inp" id="cs-ogrn" value="${esc(current.ogrn || "")}"></div>
    </div>
    <div class="field"><label>Юридический / фактический адрес</label><input class="inp" id="cs-address" value="${esc(current.address || "")}"></div>
    <div class="grid2">
      <div class="field"><label>Телефон</label><input class="inp" id="cs-phone" value="${esc(current.phone || "")}"></div>
      <div class="field"><label>Email</label><input class="inp" id="cs-email" value="${esc(current.email || "")}"></div>
    </div>
    <div class="field"><label>Банк</label><input class="inp" id="cs-bank" placeholder="ПАО СБЕРБАНК г. Москва" value="${esc(current.bank || "")}"></div>
    <div class="grid2">
      <div class="field"><label>БИК банка</label><input class="inp" id="cs-bik" placeholder="9 цифр" value="${esc(current.bik || "")}"></div>
      <div class="field"><label>Расчётный счёт</label><input class="inp" id="cs-account" placeholder="20 цифр (40702...)" value="${esc(current.account || "")}"></div>
    </div>
    <div class="field"><label>Корреспондентский счёт</label><input class="inp" id="cs-corr" placeholder="20 цифр (30101...)" value="${esc(current.corr_account || current.corrAccount || "")}"></div>
    <div class="grid2">
      <div class="field"><label>Руководитель (для подписи)</label><input class="inp" id="cs-director" placeholder="Иванов И.И." value="${esc(current.director || "")}"></div>
      <div class="field"><label>Бухгалтер</label><input class="inp" id="cs-accountant" placeholder="Петрова А.С." value="${esc(current.accountant || "")}"></div>
    </div>
    <div class="grid2">
      <div class="field"><label>Префикс счетов</label><input class="inp" id="cs-prefix" placeholder="СЧ" value="${esc(current.invoice_prefix || current.invoicePrefix || "СЧ")}"></div>
      <div class="field"><label>НДС по умолчанию, %</label><input type="number" class="inp" id="cs-vat" value="${current.vat_rate !== undefined ? current.vat_rate : (current.vatRate || 0)}"></div>
    </div>
    <div class="field"><label><input type="checkbox" id="cs-default" ${current.is_default ? "checked" : ""}> Использовать по умолчанию для новых счетов</label></div>
    <div class="modal-foot">
      <button class="btn btn-ghost" data-action="modal-close">Отмена</button>
      <button class="btn btn-amber" data-action="inv-save-company">${isNew ? "Создать организацию" : "Сохранить реквизиты"}</button>
    </div>
  `);

  $$("[data-comp-select]").forEach(b => {
    b.addEventListener("click", () => {
      companySettingsState.isNew = false;
      companySettingsState.selectedId = b.dataset.compSelect;
      renderCompanySettingsModal();
    });
  });

  const btnNew = $("[data-comp-action=new]");
  if (btnNew) {
    btnNew.addEventListener("click", () => {
      companySettingsState.isNew = true;
      renderCompanySettingsModal();
    });
  }

  const btnDef = $("[data-comp-action=set-default]");
  if (btnDef) {
    btnDef.addEventListener("click", async () => {
      const cid = btnDef.dataset.id;
      const res = await api("/api/companies/" + cid + "/set-default", {}, "POST");
      if (res.ok) {
        notice("Организация установлена по умолчанию");
        await openCompanySettings();
      } else {
        notice(res.detail || "Ошибка", "error");
      }
    });
  }

  const btnDel = $("[data-comp-action=delete]");
  if (btnDel) {
    btnDel.addEventListener("click", async () => {
      const cid = btnDel.dataset.id;
      actionModal({
        title: "Удаление организации",
        danger: true,
        body: "Вы уверены, что хотите удалить эту организацию из списка?",
        confirmText: "Удалить",
        onConfirm: async () => {
          const res = await api("/api/companies/" + cid, undefined, "DELETE");
          if (res.ok) {
            notice("Организация удалена");
            await openCompanySettings();
          } else {
            notice(res.detail || "Ошибка удаления", "error");
          }
        }
      });
    });
  }

  if (warn) notice(warn, "amber");
}

async function saveCompanySettings() {
  const cid = $("#cs-id") ? $("#cs-id").value.trim() : "";
  const isNew = companySettingsState.isNew || !cid;

  const data = {
    name: $("#cs-name").value.trim(),
    inn: $("#cs-inn").value.trim(),
    kpp: $("#cs-kpp").value.trim(),
    ogrn: $("#cs-ogrn").value.trim(),
    address: $("#cs-address").value.trim(),
    phone: $("#cs-phone").value.trim(),
    email: $("#cs-email").value.trim(),
    bank: $("#cs-bank").value.trim(),
    bik: $("#cs-bik").value.trim(),
    account: $("#cs-account").value.trim(),
    corr_account: $("#cs-corr").value.trim(),
    director: $("#cs-director").value.trim(),
    accountant: $("#cs-accountant").value.trim(),
    invoice_prefix: $("#cs-prefix").value.trim() || "СЧ",
    vat_rate: parseFloat($("#cs-vat").value) || 0,
    is_default: $("#cs-default") ? $("#cs-default").checked : false
  };

  if (!data.name || !data.inn) {
    notice("Заполните название организации и ИНН", "error");
    return;
  }

  let r;
  if (isNew) {
    r = await api("/api/companies/", data, "POST");
  } else {
    r = await api("/api/companies/" + cid, data, "PUT");
  }

  if (r.ok) {
    notice(isNew ? "Организация создана" : "Реквизиты сохранены");
    closeModal();
    if (typeof currentPage !== "undefined" && currentPage === "invoices") loadInvoices();
  } else {
    notice(r.detail || "Ошибка сохранения", "error");
  }
}

document.addEventListener("click", async ev => {
  const btn = ev.target.closest("[data-action]");
  if (!btn) return;
  const a = btn.dataset.action;
  if (!a.startsWith("inv-")) return;
  const id = btn.dataset.id;

  switch (a) {
    case "inv-new":
      openInvoiceModal(btn.dataset.object || "");
      break;

    case "inv-settings":
      openCompanySettings();
      break;

    case "inv-print":
      window.open("/api/invoices/" + id + "/print", "_blank");
      break;

    case "inv-act":
      window.open("/api/invoices/" + id + "/act", "_blank");
      break;

    case "inv-create":
      await saveInvoice();
      break;

    case "inv-save-company":
      await saveCompanySettings();
      break;

    case "inv-pay": {
      const debt = parseFloat(btn.dataset.debt || "0");
      actionModal({
        title: "Оплата счёта",
        body: "Счёт <b>" + esc(btn.dataset.number) + "</b><br>Остаток к оплате: <b>" + fmtMoney(debt) + "</b>",
        inputs: [
          { id: "amount", label: "Сумма оплаты", type: "number", value: debt },
          { id: "paidDate", label: "Дата оплаты", type: "date", value: todayISO() },
          { id: "ref", label: "Платёжный документ", type: "text", placeholder: "№ платёжки" }
        ],
        confirmText: "Провести оплату",
        onConfirm: async vals => {
          const amount = parseFloat(String(vals.amount || "").replace(",", "."));
          if (!amount || amount <= 0) { notice("Введите сумму", "error"); return; }
          const r = await api("/api/invoices/" + id + "/pay", { Amount: amount, PaidDate: vals.paidDate || null, PaymentRef: vals.ref || "" });
          if (r.ok) { notice("Оплата проведена"); closeModal(); loadInvoices(); }
          else notice(r.detail || "Ошибка", "error");
        }
      });
      break;
    }

    case "inv-cancel":
      actionModal({
        title: "Отмена счёта",
        danger: true,
        body: "Счёт будет помечен как отменённый. Отменить можно только счёт без оплат.",
        confirmText: "Отменить счёт",
        onConfirm: async () => {
          const r = await api("/api/invoices/" + id + "/cancel", {});
          if (r.ok) { notice("Счёт отменён"); closeModal(); loadInvoices(); }
          else notice(r.detail || "Ошибка", "error");
        }
      });
      break;

    case "inv-delete":
      actionModal({
        title: "Удаление счёта",
        danger: true,
        body: "Счёт и его позиции будут удалены. Удалить можно только счёт без оплат.",
        confirmText: "Удалить счёт",
        onConfirm: async () => {
          const r = await api("/api/invoices/" + id, undefined, "DELETE");
          if (r.ok) { notice("Счёт удалён"); closeModal(); loadInvoices(); }
          else notice(r.detail || "Ошибка", "error");
        }
      });
      break;
  }
});


// ===== КУРСЫ ВАЛЮТ (ЦБ РФ + Binance, всё в ₽) =====
const FX_CACHE_KEY = "fx_cache_v2";
const FX_PREV_KEY = "fx_prev_v2";
const FX_TTL = 2 * 60 * 60 * 1000; // 2 часа
const FX_META = {
  USD: { sym: "$", cls: "usd" },
  EUR: { sym: "€", cls: "eur" },
  CNY: { sym: "¥", cls: "cny" },
  BTC: { sym: "₿", cls: "btc" }
};

function fmtFx(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(2) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return n.toFixed(2);
}

function fmtDeltaRub(n) {
  const sign = n >= 0 ? "+" : "−";
  const a = Math.abs(n);
  const s = a >= 1000 ? new Intl.NumberFormat("ru-RU").format(Math.round(a)) : a.toFixed(2);
  return sign + s + " ₽";
}
function renderFx(rates, prev) {
  const host = document.getElementById("fxWidget");
  if (!host) return;
  if (!rates) { host.innerHTML = '<span class="fx-loading">курсы недоступны</span>'; return; }
  host.innerHTML = Object.keys(FX_META).filter(c => rates[c] != null).map((c, i) => {
    const meta = FX_META[c];
    const v = rates[c];
    const p = prev ? prev[c] : null;
    const diff = (p != null) ? (v - p) : null;
    const changed = diff != null && Math.abs(diff) > 0.0001;
    const dir = changed ? (diff > 0 ? "up" : "down") : "flat";
    const ar = dir === "up" ? "▲" : (dir === "down" ? "▼" : "•");
    let chip;
    if (!changed) {
      chip = '<span class="fx-chg flat"><span class="ar">•</span></span>';
    } else if (c === "BTC") {
      const pct = (diff / p) * 100;
      const sign = pct > 0 ? "+" : "−";
      chip = '<span class="fx-chg ' + dir + '" title="изменение: ' + fmtDeltaRub(diff) + '">' +
             '<span class="ar">' + ar + '</span>' + sign + Math.abs(pct).toFixed(2) + '%</span>';
    } else {
      const sign = diff > 0 ? "+" : "−";
      chip = '<span class="fx-chg ' + dir + '">' +
             '<span class="ar">' + ar + '</span>' + sign + Math.abs(diff).toFixed(2) + ' ₽</span>';
    }
    const cardTitle = (c === "BTC" && changed)
      ? ' title="BTC к рублю · изменение ' + fmtDeltaRub(diff) + '"'
      : ' title="' + c + ' к рублю"';
    return '<div class="fx-card ' + meta.cls + '" style="animation-delay:' + (i * 70) + 'ms"' + cardTitle + '>' +
      '<div class="fx-ico">' + meta.sym + '</div>' +
      '<div class="fx-body"><span class="fx-code">' + c + '</span><span class="fx-val">' + fmtFx(v) + ' ₽</span></div>' +
      chip + '</div>';
  }).join("");
}

function setFxStamp(ts) {
  const el = document.getElementById("fxUpdated");
  if (!el) return;
  const d = ts ? new Date(ts) : new Date();
  el.textContent = "обновлено " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
}

async function fetchBtcUsd() {
  // 1. Попытка через Binance
  try {
    const r = await fetch("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", { cache: "no-store" });
    const j = await r.json();
    if (j && j.price) return parseFloat(j.price);
  } catch (e) {}

  // 2. Попытка через Coinbase
  try {
    const r = await fetch("https://api.coinbase.com/v2/prices/BTC-USD/spot", { cache: "no-store" });
    const j = await r.json();
    if (j && j.data && j.data.amount) return parseFloat(j.data.amount);
  } catch (e) {}

  // 3. Попытка через KuCoin
  try {
    const r = await fetch("https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=BTC-USDT", { cache: "no-store" });
    const j = await r.json();
    if (j && j.data && j.data.price) return parseFloat(j.data.price);
  } catch (e) {}

  return null;
}

async function fetchFx() {
  const rates = {};
  try {
    const r = await fetch("https://www.cbr-xml-daily.ru/daily_json.js");
    const j = await r.json();
    if (j && j.Valute) {
      if (j.Valute.USD) rates.USD = j.Valute.USD.Value;
      if (j.Valute.EUR) rates.EUR = j.Valute.EUR.Value;
      if (j.Valute.CNY) rates.CNY = j.Valute.CNY.Value;
    }
  } catch (e) { /* ЦБ недоступен */ }

  try {
    const btcUsd = await fetchBtcUsd();
    if (btcUsd) {
      const usdRate = rates.USD || 90; // если курс доллара ещё не загрузился, используем ориентир
      rates.BTC = btcUsd * usdRate; // переводим в рубли
    }
  } catch (e) {}

  return Object.keys(rates).length ? rates : null;
}


async function loadFx(force) {
  let cache = null;
  try { cache = JSON.parse(localStorage.getItem(FX_CACHE_KEY)); } catch (e) {}

  if (cache && cache.rates && !force && (Date.now() - cache.ts < FX_TTL)) {
    let prev = null;
    try { prev = JSON.parse(localStorage.getItem(FX_PREV_KEY)); } catch (e) {}
    renderFx(cache.rates, prev);
    setFxStamp(cache.ts);
    return;
  }

  const rates = await fetchFx();
  if (rates) {
    let prev = null;
    try { prev = JSON.parse(localStorage.getItem(FX_PREV_KEY)); } catch (e) {}
    renderFx(rates, prev);
    localStorage.setItem(FX_PREV_KEY, JSON.stringify(cache ? cache.rates : rates));
    localStorage.setItem(FX_CACHE_KEY, JSON.stringify({ ts: Date.now(), rates: rates }));
    setFxStamp(null);
  } else if (cache && cache.rates) {
    renderFx(cache.rates, null);
    setFxStamp(cache.ts);
  } else {
    renderFx(null, null);
  }
}

loadFx(false);
setInterval(() => loadFx(true), FX_TTL);

document.addEventListener("click", ev => {
  const btn = ev.target.closest("[data-action='fx-refresh']");
  if (!btn) return;
  btn.classList.add("spin");
  setTimeout(() => btn.classList.remove("spin"), 650);
  loadFx(true);
});

// ===== ЖИВЫЕ СЧЁТЧИКИ НА КНОПКАХ НАВИГАЦИИ =====
async function loadNavBadges() {
  try {
    const s = await api("/api/dashboard/stats");
    if (s.ok && s.data) {
      const over = s.data.Overdue || 0;
      if (over > 0) {
        const calBadge = document.getElementById("nb-calendar");
        const jBadge = document.getElementById("nb-journal");
        if (calBadge) { calBadge.textContent = over; calBadge.classList.add("show"); }
        if (jBadge) { jBadge.textContent = over; jBadge.classList.add("show"); }
      }
    }
    const inv = await api("/api/invoices/");
    if (inv.ok && inv.data) {
      const unpaid = inv.data.filter(i => i.Status !== "Оплачен" && i.Status !== "Отменён" && (i.Debt || 0) > 0).length;
      const iBadge = document.getElementById("nb-invoices");
      if (unpaid > 0 && iBadge) { iBadge.textContent = unpaid; iBadge.classList.add("show", "amber"); }
    }
  } catch (e) {}
}
loadNavBadges();


// ===== НАВИГАЦИЯ: индикаторы горизонтального скролла =====
(function () {
  const sc = document.querySelector(".nx-navwrap");
  const nav = sc && sc.querySelector(".nx-nav");
  if (!sc || !nav) return;
  const upd = () => {
    sc.classList.toggle("can-left", nav.scrollLeft > 4);
    sc.classList.toggle("can-right", nav.scrollLeft < nav.scrollWidth - nav.clientWidth - 4);
  };
  nav.addEventListener("scroll", upd, { passive: true });
  window.addEventListener("resize", upd);
  // колесо мыши вниз/вверх -> горизонтальный скролл полосы
  nav.addEventListener("wheel", e => {
    if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
      nav.scrollLeft += e.deltaY;
      e.preventDefault();
    }
  }, { passive: false });
  upd();
  setTimeout(upd, 300);
})();



// ===== NX: дата в шапке (полные названия месяцев) =====
(function () {
  const d = new Date();
  const mf = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"];
  const wf = ["воскресенье","понедельник","вторник","среда","четверг","пятница","суббота"];
  const elx = document.getElementById("nx-date");
  if (!elx) return;
  elx.innerHTML =
    '<span class="nx-date-d"><span class="nx-dd">' + d.getDate() + '</span> ' + mf[d.getMonth()] + '</span>' +
    '<span class="nx-date-w">' + wf[d.getDay()] + ' · ' + d.getFullYear() + '</span>';
})();


// ===== ПОГОДА (Open-Meteo, без ключа, координаты из ссылки Ventusky) =====
const WX_LAT = 58.293, WX_LON = 57.883;
const WX_CACHE = "wx_cache_v1";
const WX_TTL = 2 * 60 * 60 * 1000; // 2 часа

function wxIcon(code) {
  const m = {
    0: ["☀", "Ясно"], 1: ["🌤", "Малооблачно"], 2: ["⛅", "Переменная облачность"], 3: ["☁", "Пасмурно"],
    45: ["🌫", "Туман"], 48: ["🌫", "Изморозь"],
    51: ["🌦", "Морось"], 53: ["🌦", "Морось"], 55: ["🌦", "Морось"], 56: ["🌧", "Ледяная морось"], 57: ["🌧", "Ледяная морось"],
    61: ["🌧", "Дождь"], 63: ["🌧", "Дождь"], 65: ["🌧", "Сильный дождь"], 66: ["🌧", "Ледяной дождь"], 67: ["🌧", "Ледяной дождь"],
    71: ["❄", "Снег"], 73: ["❄", "Снег"], 75: ["❄", "Сильный снег"], 77: ["❄", "Снежные зёрна"],
    80: ["🌧", "Ливень"], 81: ["🌧", "Ливень"], 82: ["🌧", "Сильный ливень"],
    85: ["🌨", "Снегопад"], 86: ["🌨", "Снегопад"],
    95: ["⛈", "Гроза"], 96: ["⛈", "Гроза с градом"], 99: ["⛈", "Сильная гроза"]
  };
  return m[code] || ["🌡", "—"];
}
function fmtT(n) { const v = Math.round(n); return (v > 0 ? "+" : "") + v + "°"; }

function renderWx(c) {
  const host = document.getElementById("wxWidget");
  if (!host) return;
  if (!c) { host.innerHTML = '<span class="fx-loading">нет данных о погоде</span>'; return; }
  const ic = wxIcon(c.weather_code);
  host.innerHTML =
    '<div class="wx-main"><div class="wx-ico">' + ic[0] + '</div><div><div class="wx-temp">' + fmtT(c.temperature_2m) + '</div><div class="wx-desc">' + ic[1] + '</div></div></div>' +
    '<div class="wx-row"><span>Ощущается</span><b>' + fmtT(c.apparent_temperature) + '</b></div>' +
    '<div class="wx-row"><span>💨 Ветер</span><b>' + Math.round(c.wind_speed_10m) + ' м/с</b></div>' +
    '<div class="wx-row"><span>💧 Осадки</span><b>' + (c.precipitation || 0) + ' мм</b></div>' +
    '<div class="wx-geo">58.29°N · 57.88°E</div>';
}

async function fetchWx() {
  try {
    const r = await fetch("https://api.open-meteo.com/v1/forecast?latitude=" + WX_LAT + "&longitude=" + WX_LON + "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,precipitation&wind_speed_unit=ms&timezone=auto");
    const j = await r.json();
    return (j && j.current) ? j.current : null;
  } catch (e) { return null; }
}

async function loadWx(force) {
  let cache = null;
  try { cache = JSON.parse(localStorage.getItem(WX_CACHE)); } catch (e) {}
  if (cache && cache.c && !force && (Date.now() - cache.ts < WX_TTL)) { renderWx(cache.c); return; }
  const c = await fetchWx();
  if (c) { renderWx(c); localStorage.setItem(WX_CACHE, JSON.stringify({ ts: Date.now(), c: c })); }
  else if (cache && cache.c) { renderWx(cache.c); }
  else renderWx(null);
}

loadWx(false);
setInterval(() => loadWx(true), WX_TTL);

document.addEventListener("click", ev => {
  const b = ev.target.closest("[data-action='wx-refresh']");
  if (!b) return;
  b.classList.add("spin");
  setTimeout(() => b.classList.remove("spin"), 650);
  loadWx(true);
});


// ===== nav-scroll handler (стрелки прокрутки меню в шапке) =====
document.addEventListener("click", ev => {
  const b = ev.target.closest("[data-action='nav-scroll']");
  if (!b) return;
  const nav = document.querySelector(".nx-nav");
  if (!nav) return;
  const step = Math.round(nav.clientWidth * 0.8);
  nav.scrollBy({ left: b.dataset.dir === "left" ? -step : step, behavior: "smooth" });
});


// ===== КОЛОКОЛЬЧИК: НАПОМИНАНИЯ ЗА 7 ДНЕЙ С МЯГКИМ ЗВУКОМ И СКРЫТИЕМ ПРОЧИТАННЫХ =====
let bellSoundEnabled = localStorage.getItem("bell_sound_enabled") !== "false";
let lastNotifiedIds = new Set();
try {
  const stored = JSON.parse(sessionStorage.getItem("bell_seen_ids") || "[]");
  lastNotifiedIds = new Set(stored);
} catch (e) {}

// Список скрытых пользователем ID напоминаний
let bellDismissedIds = new Set();
try {
  const storedDismissed = JSON.parse(localStorage.getItem("bell_dismissed_ids") || "[]");
  bellDismissedIds = new Set(storedDismissed);
} catch (e) {}

function dismissBellReminder(id) {
  if (!id) return;
  bellDismissedIds.add(id);
  localStorage.setItem("bell_dismissed_ids", JSON.stringify(Array.from(bellDismissedIds)));
  loadReminders();
}

function dismissAllBellReminders(ids) {
  if (!ids || !ids.length) return;
  ids.forEach(id => bellDismissedIds.add(id));
  localStorage.setItem("bell_dismissed_ids", JSON.stringify(Array.from(bellDismissedIds)));
  loadReminders();
}

function playSoftChime() {
  if (!bellSoundEnabled) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
      if (ctx.state === "suspended") return; // Браузер требует взаимодействия пользователя для воспроизведения
    }

    const now = ctx.currentTime;
    // Мягкий гармоничный двухтональный колокольчик (E5 -> B5, 659.25Hz и 987.77Hz)
    const tones = [
      { freq: 659.25, time: 0.0, dur: 0.8 },
      { freq: 987.77, time: 0.12, dur: 1.1 }
    ];

    tones.forEach(t => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(t.freq, now + t.time);

      gain.gain.setValueAtTime(0.0001, now + t.time);
      gain.gain.exponentialRampToValueAtTime(0.15, now + t.time + 0.04);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + t.time + t.dur);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now + t.time);
      osc.stop(now + t.time + t.dur);
    });
  } catch (err) {
    // AudioContext недоступен
  }
}

let lastActiveBellItems = [];

async function loadReminders() {
  try {
    const res = await api("/api/dashboard/reminders");
    if (!res.ok) return;
    const rawItems = res.data || [];

    // Фильтруем те, которые пользователь уже скрыл/просмотрел
    const items = rawItems.filter(item => !bellDismissedIds.has(item.ID));
    lastActiveBellItems = items;

    const badge = document.getElementById("bellBadge");
    const list = document.getElementById("bellList");
    const markAllBtn = document.getElementById("bellMarkAllReadBtn");

    if (badge) {
      if (items.length > 0) {
        badge.textContent = items.length;
        badge.classList.add("show");
      } else {
        badge.textContent = "";
        badge.classList.remove("show");
      }
    }

    if (markAllBtn) {
      markAllBtn.style.display = items.length > 0 ? "inline-block" : "none";
    }

    if (list) {
      if (!items.length) {
        list.innerHTML = '<div class="empty" style="padding:16px 8px;font-size:12px;">✅ Все напоминания просмотрены</div>';
      } else {
        list.innerHTML = items.map(item => `
          <div class="bell-item" data-action="bell-open" data-id="${esc(item.ID)}" data-date="${esc(item.PlannedDate)}">
            <div class="bell-item-head">
              <span class="bell-item-obj">${esc(item.ObjectName)}</span>
              <div class="bell-item-actions">
                <span class="bell-item-tag">${item.DaysLeft === 0 ? "СЕГОДНЯ" : "через " + item.DaysLeft + " дн."}</span>
                <button type="button" class="bell-item-dismiss" data-action="bell-dismiss" data-id="${esc(item.ID)}" title="Скрыть это напоминание">✕</button>
              </div>
            </div>
            <div class="bell-item-work">${esc(item.WorkCode)} · ${esc(item.WorkName)}</div>
            <div class="bell-item-date">
              <span>📅 План: <b>${fmtDate(item.PlannedDate)}</b></span>
              <span>🔔 Напоминание с ${fmtDate(item.RemindDate)}</span>
            </div>
          </div>
        `).join("");
      }
    }

    // Проверка новых напоминаний для воспроизведения мягкого звука
    const currentIds = items.map(x => x.ID);
    const hasNew = currentIds.some(id => !lastNotifiedIds.has(id));
    if (hasNew && items.length > 0) {
      playSoftChime();
      currentIds.forEach(id => lastNotifiedIds.add(id));
      sessionStorage.setItem("bell_seen_ids", JSON.stringify(Array.from(lastNotifiedIds)));
    }
  } catch (e) {}
}

document.addEventListener("click", ev => {
  // Нажатие на само напоминание: скрываем его и открываем карточку даты выполнения
  const bellItem = ev.target.closest("[data-action='bell-open']");
  if (bellItem && !ev.target.closest("[data-action='bell-dismiss']")) {
    const id = bellItem.dataset.id;
    const pDate = bellItem.dataset.date;
    if (id) dismissBellReminder(id);
    const dd = document.getElementById("bellDropdown");
    if (dd) dd.classList.add("hidden");
    if (pDate) openDay(pDate.slice(0, 10));
    return;
  }

  // Нажатие кнопки "Скрыть напоминание" (крестик на отдельном напоминании)
  const dismissBtn = ev.target.closest("[data-action='bell-dismiss']");
  if (dismissBtn) {
    ev.stopPropagation();
    const id = dismissBtn.dataset.id;
    dismissBellReminder(id);
    return;
  }

  // Нажатие кнопки "Прочитано всё"
  const markAllBtn = ev.target.closest("#bellMarkAllReadBtn");
  if (markAllBtn) {
    ev.stopPropagation();
    dismissAllBellReminders(lastActiveBellItems.map(x => x.ID));
    return;
  }

  const bellBtn = ev.target.closest("#bellBtn");
  const dd = document.getElementById("bellDropdown");
  if (bellBtn && dd) {
    dd.classList.toggle("hidden");
    loadReminders();
    return;
  }

  const soundBtn = ev.target.closest("#soundToggleBtn");
  if (soundBtn) {
    bellSoundEnabled = !bellSoundEnabled;
    localStorage.setItem("bell_sound_enabled", String(bellSoundEnabled));
    soundBtn.textContent = bellSoundEnabled ? "🔊" : "🔇";
    soundBtn.title = bellSoundEnabled ? "Звук включен" : "Звук выключен";
    if (bellSoundEnabled) playSoftChime();
    notice(bellSoundEnabled ? "Звук напоминаний включён" : "Звук напоминаний выключен");
    return;
  }

  // Закрытие при клике вне колокольчика
  if (dd && !dd.classList.contains("hidden") && !ev.target.closest(".nx-bell-wrap")) {
    dd.classList.add("hidden");
  }
});

// Инициализация звуковой кнопки
const sndBtn = document.getElementById("soundToggleBtn");
if (sndBtn) {
  sndBtn.textContent = bellSoundEnabled ? "🔊" : "🔇";
  sndBtn.title = bellSoundEnabled ? "Звук включен" : "Звук выключен";
}

loadReminders();
setInterval(loadReminders, 60000); // Проверка каждую минуту

// ===== ПЕРЕКЛЮЧЕНИЕ БОКОВОЙ ПАНЕЛИ ПО КЛИКУ НА ДАТУ =====
(function initSideToggle() {
  const brandBtn = document.getElementById("nxBrandToggle");
  const body = document.querySelector(".nx-body");
  if (!brandBtn || !body) return;

  // По умолчанию панель свёрнута (false только если пользователь явно её открыл и сохранил 'false')
  const isCollapsed = localStorage.getItem("side_panel_collapsed") !== "false";
  body.classList.toggle("side-collapsed", isCollapsed);
  brandBtn.classList.toggle("collapsed", isCollapsed);

  brandBtn.addEventListener("click", () => {
    const collapsed = body.classList.toggle("side-collapsed");
    brandBtn.classList.toggle("collapsed", collapsed);
    localStorage.setItem("side_panel_collapsed", String(collapsed));
  });


  brandBtn.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      brandBtn.click();
    }
  });
})();

// ===== ИНДИКАЦИЯ СТАТУСА ИИ (ПРОВЕРКА API, РЕАЛЬНОЕ ПОДКЛЮЧЕНИЕ, 123-ФЗ) =====
let aiStatusCache = { enabled: true, is_online: false, has_api_key: false, status: "expert_offline", mode: "123-ФЗ" };

async function checkAndUpdateAiStatus() {
  try {
    const rc = await api("/api/ai/config");
    if (rc.ok) {
      aiStatusCache = rc;
    }
  } catch (e) {
    aiStatusCache = { enabled: false, is_online: false, status: "disabled", mode: "Недоступен" };
  }

  const btn = document.getElementById("btnOpenAiAdvisor");
  if (!btn) return;

  btn.classList.remove("state-online", "state-expert", "state-disabled", "state-error");

  const pName = esc(aiStatusCache.display_name || "123-ФЗ");
  const provider = esc(aiStatusCache.provider_display || "AI");

  if (!aiStatusCache.enabled) {
    // 🟡 ИИ ВЫКЛЮЧЕН В msg.cfg
    btn.classList.add("state-disabled");
    btn.innerHTML = '<span class="ai-dot"></span>✍️ <span>ИИ: Выключен</span> <span class="ai-status-pill">ВРУЧНУЮ</span>';
    btn.title = "ИИ отключен в msg.cfg (enabled=false). Все поля заполняются полностью вручную.";
  } else if (aiStatusCache.status === "error") {
    // 🔴 ОШИБКА API (неверный ключ, ошибка авторизации 401/403 или сеть)
    btn.classList.add("state-error");
    btn.innerHTML = `<span class="ai-dot"></span>⚠️ <span>Ошибка API: ${provider}</span> <span class="ai-status-pill">ОШИБКА КЛЮЧА</span>`;
    btn.title = `Внимание! API нейросети не отвечает или указан неверный ключ: ${aiStatusCache.error_detail || 'Ошибка'}. Включен резерв: 123-ФЗ.`;
  } else if (aiStatusCache.is_online && aiStatusCache.status === "online_llm") {
    // 🟢 РЕАЛЬНО ОНЛАЙН: Проверенное подключение к внешней нейросети
    btn.classList.add("state-online");
    btn.innerHTML = `<span class="ai-dot"></span>🤖 <span>${pName}</span> <span class="ai-status-pill">ОНЛАЙН</span>`;
    btn.title = `ИИ подключен и проверен (${provider}, модель ${aiStatusCache.model}). Доступен нейросетевой анализ.`;
  } else {
    // 🟡 БЕЗ ВНЕШНЕГО API: Встроенная база 123-ФЗ
    btn.classList.add("state-disabled");
    btn.innerHTML = '<span class="ai-dot"></span>✍️ <span>База норм 123-ФЗ</span> <span class="ai-status-pill">БЕЗ API</span>';
    btn.title = "API-ключ не указан в msg.cfg. Работает экспертная система норм пожарной безопасности 123-ФЗ.";
  }
}

// ===== МОДУЛЬ ИИ-ПОМОЩНИКА (123-ФЗ И СПЕЦИФИКАЦИИ РЕГЛАМЕНТОВ) =====
async function openAiAdvisorModal(targetObjectId) {
  let objects = [];
  try {
    const ro = await api("/api/objects/");
    if (ro.ok) objects = ro.data;
  } catch (e) {}

  let cfg = aiStatusCache;
  try {
    const rc = await api("/api/ai/config");
    if (rc.ok) { cfg = rc; aiStatusCache = rc; }
  } catch (e) {}

  const objOptions = objects.map(o =>
    `<option value="${esc(o.ID)}"${targetObjectId === o.ID ? " selected" : ""}>${esc(o.Name)} (${esc(o.FunctionalHazard || "Ф3.1")}, ${o.TotalArea || 0} м²)</option>`
  ).join("");

  // Формируем баннер статуса в зависимости от реального подключения
  let bannerHtml = "";
  if (!cfg.enabled) {
    bannerHtml = '<div class="ai-banner" style="background:rgba(245,165,36,0.12);border:1.5px solid rgba(245,165,36,0.55);">' +
      '<div class="ai-banner-ico" style="font-size:28px;">✍️</div>' +
      '<div class="ai-banner-text">' +
        '<div style="font-size:14px;font-weight:700;color:var(--amber-2);margin-bottom:4px;">⚠️ ИИ ОТКЛЮЧЕН В MSG.CFG (РЕЖИМ РУЧНОГО ВВОДА)</div>' +
        '<div style="color:var(--text);font-size:12.5px;line-height:1.4;">Автоматический аудит и рекомендации отключены. Заполнение объектов производится <b>полностью вручную</b>.</div>' +
      '</div>' +
    '</div>';
  } else if (cfg.status === "error") {
    bannerHtml = '<div class="ai-banner" style="background:rgba(239,68,68,0.1);border:1.5px solid rgba(239,68,68,0.5);">' +
      '<div class="ai-banner-ico" style="font-size:26px;">⚠️</div>' +
      '<div class="ai-banner-text">' +
        '<div style="font-size:13.5px;font-weight:700;color:#f87171;margin-bottom:2px;">🔴 ОШИБКА API НЕЙРОСЕТИ (' + esc(cfg.provider_display || "API") + ')</div>' +
        '<div style="color:var(--text);font-size:12px;">' + esc(cfg.description || "Ключ API недействителен или сервер недоступен.") + ' Автоматически задействована <b>встроенная база норм 123-ФЗ</b>.</div>' +
      '</div>' +
    '</div>';
  } else if (cfg.is_online && cfg.status === "online_llm") {
    bannerHtml = '<div class="ai-banner" style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.4);">' +
      '<div class="ai-banner-ico" style="font-size:26px;">🤖</div>' +
      '<div class="ai-banner-text">' +
        '<div style="font-size:13.5px;font-weight:700;color:#4ade80;margin-bottom:2px;">🟢 ' + esc(cfg.display_name || "ИИ ОНЛАЙН") + ' (' + esc(cfg.model || "LLM") + ')</div>' +
        '<div style="color:var(--text);font-size:12px;">Подключение к API успешно проверено. Доступен автоматический нейросетевой анализ объектов и расчет регламентов.</div>' +
      '</div>' +
    '</div>';
  } else {
    bannerHtml = '<div class="ai-banner" style="background:rgba(245,165,36,0.1);border:1.5px solid rgba(245,165,36,0.5);">' +
      '<div class="ai-banner-ico" style="font-size:26px;">✍️</div>' +
      '<div class="ai-banner-text">' +
        '<div style="font-size:13.5px;font-weight:700;color:var(--amber-2);margin-bottom:2px;">🟡 БЕЗ ВНЕШНЕГО API: ВСТРОЕННАЯ ЭКСПЕРТНАЯ БАЗА 123-ФЗ</div>' +
        '<div style="color:var(--text);font-size:12px;">API-ключ не указан в msg.cfg. Система работает автономно по нормам 123-ФЗ, СП 484, СП 486 и ППР 1479.</div>' +
      '</div>' +
    '</div>';
  }

  openModal(
    '<div class="modal-head">' +
      '<div class="modal-title">🤖 Помощник по регламентам пожарной безопасности (Нормы ПБ)</div>' +
      '<button class="modal-x" data-action="modal-close">×</button>' +
    '</div>' +
    '<div class="ai-tabs">' +
      '<button class="ai-tab-btn active" id="tabAiAudit" type="button">Анализ объекта и рекомендации</button>' +
      '<button class="ai-tab-btn" id="tabAiNew" type="button">Конструктор нового объекта</button>' +
    '</div>' +
    bannerHtml +

    // Вкладка 1: Аудит существующего объекта
    '<div id="viewAiAudit">' +
      '<div class="grid2" style="align-items:flex-end;margin-bottom:14px;">' +
        '<div class="field" style="margin-bottom:0;"><label>Выберите объект для анализа</label>' +
          '<select class="inp" id="aiSelectObject">' +
            (objOptions ? objOptions : '<option value="">Нет активных объектов</option>') +
          '</select>' +
        '</div>' +
        '<div>' +
          '<button class="btn btn-amber" id="btnRunAiAudit" style="width:100%;">🔍 Запустить аудит норм ПБ</button>' +
        '</div>' +
      '</div>' +
      '<div id="aiAuditResult" style="min-height:160px;">' +
        '<div class="empty" style="padding:24px 0;"><span class="big">🤖</span>Выберите объект и нажмите «Запустить аудит норм ПБ»</div>' +
      '</div>' +
    '</div>' +

    // Вкладка 2: Создание нового объекта через ИИ
    '<div id="viewAiNew" style="display:none;">' +
      '<div class="field"><label>Тип или наименование объекта (для автоматической классификации)</label>' +
        '<div style="display:flex;gap:8px;">' +
          '<input class="inp" id="aiNewTypeInp" placeholder="Например: Складской комплекс или Офисный центр">' +
          '<button class="btn btn-ghost" id="btnAiClassify" style="white-space:nowrap;color:var(--amber-2);border-color:rgba(245,165,36,0.3);">✨ Подобрать нормы</button>' +
        '</div>' +
      '</div>' +
      '<div class="grid2">' +
        '<div class="field"><label>Название объекта *</label><input class="inp" id="aiNewName" placeholder="БЦ «Меркурий»"></div>' +
        '<div class="field"><label>Адрес *</label><input class="inp" id="aiNewAddr"></div>' +
      '</div>' +
      '<div class="grid2">' +
        '<div class="field"><label>Класс ФПО</label><input class="inp" id="aiNewFpo" value="Ф4.3"></div>' +
        '<div class="field"><label>Категория взрывопожароопасности</label><input class="inp" id="aiNewCat" value="В"></div>' +
      '</div>' +
      '<div class="grid2">' +
        '<div class="field"><label>Общая площадь (м²)</label><input class="inp" type="number" id="aiNewArea" value="1200"></div>' +
        '<div class="field"><label>Этажность</label><input class="inp" type="number" id="aiNewFloors" value="2"></div>' +
      '</div>' +
      '<div class="field"><label>Примечание инженера</label><textarea class="inp" id="aiNewNotes" rows="2"></textarea></div>' +
      '<div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px;">' +
        '<button class="btn btn-amber" id="btnCreateObjViaAi">+ Завести объект и перейти к регламентам</button>' +
      '</div>' +
    '</div>' +

    '<div class="modal-foot">' +
      '<button class="btn btn-ghost" data-action="modal-close">Закрыть</button>' +
    '</div>'
  );

  // Обработчики вкладок
  const tabAudit = $("#tabAiAudit");
  const tabNew = $("#tabAiNew");
  const viewAudit = $("#viewAiAudit");
  const viewNew = $("#viewAiNew");

  if (tabAudit && tabNew) {
    tabAudit.addEventListener("click", () => {
      tabAudit.classList.add("active");
      tabNew.classList.remove("active");
      viewAudit.style.display = "block";
      viewNew.style.display = "none";
    });
    tabNew.addEventListener("click", () => {
      tabNew.classList.add("active");
      tabAudit.classList.remove("active");
      viewNew.style.display = "block";
      viewAudit.style.display = "none";
    });
  }

  // Аудит выбранного объекта
  async function runAuditForObject(oid) {
    const resBox = $("#aiAuditResult");
    if (!resBox) return;
    if (!oid) {
      resBox.innerHTML = '<div class="empty">Выберите объект для проверки</div>';
      return;
    }
    resBox.innerHTML = '<div class="empty"><span class="big">⌛</span>ИИ сопоставляет характеристики объекта с регламентами и нормами ПБ…</div>';
    
    const r = await api("/api/ai/analyze", { objectId: oid });
    if (!r.ok || !r.data) {
      resBox.innerHTML = '<div class="empty" style="color:var(--ember)">Ошибка анализа: ' + esc(r.detail || "нет данных") + '</div>';
      return;
    }

    const data = r.data;
    const recs = data.recommendations || [];
    const unassigned = recs.filter(x => !x.is_assigned);

    let html = '';
    html += '<div style="background:var(--panel-2);border-radius:10px;padding:12px 16px;margin-bottom:14px;border:1px solid var(--line);">';
    html += '<div style="font-weight:600;font-size:14px;color:var(--amber-2);margin-bottom:4px;">📋 Экспертное заключение</div>';
    html += '<div style="font-size:13px;line-height:1.5;color:var(--text);">' + esc(data.summary) + '</div>';
    if (data.regulations && data.regulations.length) {
      html += '<div class="ai-chips">' + data.regulations.map(reg => '<span class="ai-chip">📜 ' + esc(reg) + '</span>').join("") + '</div>';
    }
    html += '</div>';

    if (unassigned.length > 0) {
      html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">';
      html += '<div style="font-weight:600;font-size:13px;color:var(--text);">Необходимо назначить (' + unassigned.length + ' работ):</div>';
      html += '<button class="btn btn-amber btn-sm" id="btnApplyAiRecs" data-obj="' + esc(oid) + '">⚡ Назначить все рекомендованные в 1 клик</button>';
      html += '</div>';
    } else {
      html += '<div style="color:var(--moss);font-size:13px;font-weight:600;margin-bottom:12px;">✅ Все обязательные регламенты ПБ уже включены в план обслуживания!</div>';
    }

    html += '<div class="ai-rec-list">';
    recs.forEach(rec => {
      const isUn = !rec.is_assigned;
      html += '<div class="ai-rec-card ' + (isUn ? "unassigned" : "assigned") + '">';
      html += '<div class="ai-rec-left">';
      if (isUn) {
        html += '<input type="checkbox" class="ai-rec-check" data-code="' + esc(rec.work_code) + '" checked>';
      } else {
        html += '<span style="color:var(--moss);font-size:16px;margin-top:2px;">✓</span>';
      }
      html += '<div>';
      html += '<div class="ai-rec-title">[' + esc(rec.work_code) + '] ' + esc(rec.work_name) + '</div>';
      html += '<div class="ai-rec-meta">Периодичность: ' + esc(rec.frequency) + ' · Статус: ' + (isUn ? '<span style="color:var(--amber-2)">Требуется назначить</span>' : '<span style="color:var(--moss)">Назначено</span>') + '</div>';
      html += '<div class="ai-rec-reason">' + esc(rec.reason) + '</div>';
      if (rec.law_ref) {
        html += '<div class="ai-rec-law">Основание: ' + esc(rec.law_ref) + '</div>';
      }
      html += '</div></div>';
      html += '<div class="ai-rec-right">';
      html += '<div class="ai-rec-price">' + fmtMoney(rec.price || 0) + '</div>';
      html += '<div class="ai-rec-freq">' + esc(rec.frequency) + '</div>';
      html += '</div>';
      html += '</div>';
    });
    html += '</div>';

    resBox.innerHTML = html;

    // Кнопка пакетного применения
    const btnApply = $("#btnApplyAiRecs");
    if (btnApply) {
      btnApply.addEventListener("click", async () => {
        const checkedBoxes = $$(".ai-rec-check:checked");
        const codes = Array.from(checkedBoxes).map(cb => cb.dataset.code);
        if (!codes.length) {
          toast("Выберите хотя бы один пункт для назначения", "error");
          return;
        }
        btnApply.disabled = true;
        btnApply.textContent = "Назначение…";
        const ra = await api("/api/ai/apply", { objectId: oid, workCodes: codes });
        if (ra.ok) {
          notice("Успешно создано " + ra.created_assignments_count + " назначений и " + ra.created_executions_count + " событий в Календаре!");
          runAuditForObject(oid);
          if (currentPage === "assignments") loadAssignments();
          if (currentPage === "calendar") loadCalendar();
          if (currentPage === "dashboard") loadDashboard();
        } else {
          toast(ra.detail || "Ошибка назначения", "error");
          btnApply.disabled = false;
          btnApply.textContent = "⚡ Назначить выбранные в 1 клик";
        }
      });
    }
  }

  // Кнопка ручного запуска
  const btnRun = $("#btnRunAiAudit");
  const selObj = $("#aiSelectObject");
  if (btnRun && selObj) {
    btnRun.addEventListener("click", () => {
      runAuditForObject(selObj.value);
    });
  }

  // Автозапуск аудита, если передан targetObjectId
  if (targetObjectId) {
    runAuditForObject(targetObjectId);
  }

  // Классификация во вкладке "Конструктор"
  const btnClassify = $("#btnAiClassify");
  if (btnClassify) {
    btnClassify.addEventListener("click", async () => {
      const q = $("#aiNewTypeInp").value.trim();
      if (!q) { toast("Введите тип объекта", "error"); return; }
      const r = await api("/api/ai/preset", { query: q });
      if (r.ok && r.preset) {
        $("#aiNewFpo").value = r.preset.functional_hazard || "Ф3.1";
        $("#aiNewCat").value = r.preset.fire_hazard_category || "В";
        if (r.preset.notes) $("#aiNewNotes").value = r.preset.notes;
        notice("Классифицировано по нормам ПБ: " + r.preset.functional_hazard);
      }
    });
  }

  // Создание объекта через ИИ-конструктор
  const btnCreateObj = $("#btnCreateObjViaAi");
  if (btnCreateObj) {
    btnCreateObj.addEventListener("click", async () => {
      const name = $("#aiNewName").value.trim();
      const addr = $("#aiNewAddr").value.trim();
      if (!name || !addr) {
        toast("Укажите название и адрес объекта", "error");
        return;
      }
      const data = {
        Name: name,
        Address: addr,
        Category: $("#aiNewTypeInp").value.trim() || "Здание",
        FunctionalHazard: $("#aiNewFpo").value.trim() || "Ф3.1",
        FireHazardCategory: $("#aiNewCat").value.trim() || "В",
        ConstructionHazard: "С0",
        TotalArea: parseFloat($("#aiNewArea").value) || 0.0,
        Floors: parseInt($("#aiNewFloors").value) || 1,
        Notes: $("#aiNewNotes").value.trim(),
      };
      btnCreateObj.disabled = true;
      const ro = await api("/api/objects/", data);
      if (ro.ok && ro.data) {
        notice("Объект «" + name + "» успешно создан!");
        loadObjects();
        // Переключаем на вкладку аудита с созданным объектом
        closeModal();
        openAiAdvisorModal(ro.data.ID);
      } else {
        toast(ro.detail || "Ошибка при создании объекта", "error");
        btnCreateObj.disabled = false;
      }
    });
  }
}



