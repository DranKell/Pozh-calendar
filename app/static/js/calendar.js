/* ============================================================
   КАЛЕНДАРЬ ТО — Модуль Календаря (calendar.js)
   ============================================================ */
/* ---------- календарь ---------- */

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
          '<button class="btn btn-ghost btn-sm" data-action="exec-move" data-id="' + esc(e.ID) + '" data-date="' + iso + '" data-obj="' + esc(e.ObjectName) + '" data-work="' + esc(e.WorkName) + '" title="Перенести на другую дату">↻ Перенести</button>' +
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
    body = batchBarHtml + '<div class="day-modal-wrap"><table class="day-modal-table"><thead><tr><th style="width:24px"></th><th>Объект</th><th>Работа</th><th>Периодичность</th><th>Статус</th><th>Факт</th><th style="white-space:nowrap;">Действия</th></tr></thead><tbody>' + rows + "</tbody></table></div>";
  }
  openModal(
    '<div class="modal-head"><div class="modal-title">📅 ' + title + '</div><button class="modal-x" data-action="modal-close">×</button></div>' +
    body +
    '<div class="modal-foot" style="justify-content:space-between">' +
      '<button class="btn btn-ghost" data-action="assign-new" data-date="' + iso + '">+ Назначить на эту дату</button>' +
      '<button class="btn btn-ghost" data-action="modal-close">Закрыть</button>' +
    "</div>",
    "modal-wide"
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


