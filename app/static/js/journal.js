/* ============================================================
   КАЛЕНДАРЬ ТО — Модуль Журнала ТО (journal.js)
   ============================================================ */
let jStatus = "", jObj = "", jDateFrom = "", jDateTo = "";
async function loadJournal() {
  await ensureCaches();
  let url = "/api/executions/?";
  const params = [];
  if (jDateFrom) params.push("date_from=" + encodeURIComponent(jDateFrom));
  if (jDateTo) params.push("date_to=" + encodeURIComponent(jDateTo));
  if (!jDateFrom && !jDateTo) params.push("year=" + new Date().getFullYear());
  if (jStatus) params.push("status=" + encodeURIComponent(jStatus));
  if (jObj) params.push("object_id=" + encodeURIComponent(jObj));
  url += params.join("&");

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

  const countText = r.ok && r.data ? `Найдено записей: ${r.data.length}` : "";

  $("#page-journal").innerHTML =
    '<div class="toolbar">' +
      selectHtml("jFStatus", ["Запланировано", "Выполнено", "Перенесено", "Отменено"].map(s => ({ value: s, label: s })), jStatus, "Все статусы") +
      '<div id="jFObjBox" style="min-width:260px;"></div>' +
      '<div class="toolbar-date-group">' +
        '<label>Период:</label>' +
        '<input type="date" class="inp" id="jFDateFrom" value="' + esc(jDateFrom) + '" title="С даты">' +
        '<span style="color:var(--text-3);">—</span>' +
        '<input type="date" class="inp" id="jFDateTo" value="' + esc(jDateTo) + '" title="По дату">' +
      '</div>' +
      '<button class="toolbar-quick-btn" id="jQuickToday" title="За сегодня">Сегодня</button>' +
      '<button class="toolbar-quick-btn" id="jQuickMonth" title="За текущий месяц">Этот месяц</button>' +
      '<button class="toolbar-quick-btn" id="jQuickYear" title="За текущий год">Этот год</button>' +
      (jDateFrom || jDateTo || jStatus || jObj ? '<button class="toolbar-quick-btn" id="jQuickReset" title="Сбросить все фильтры" style="color:var(--ember);border-color:rgba(242,112,138,0.3);">✕ Сброс</button>' : '') +
      '<div style="display:inline-flex;gap:6px;margin-left:auto;align-items:center;">' +
        '<button class="btn btn-amber btn-sm" id="jBtnPprPrint" title="Сформировать официальный журнал ППР 1479 в формате для печати А4">📑 Журнал ППР 1479</button>' +
        '<button class="btn btn-ghost btn-sm" id="jBtnPprExcel" title="Выгрузить журнал ППР 1479 в Excel файл">📊 Excel</button>' +
        '<button class="btn btn-ghost btn-sm" id="jBtnActPrint" title="Сформировать официальный Акт технического освидетельствования / проверки работоспособности">📄 Акт проверки</button>' +
      '</div>' +
      '<span class="toolbar-hint">' + esc(countText) + ' · Клик по строке — открыть</span>' +
    "</div>" +
    '<div class="panel table-panel"><table><thead><tr><th>План</th><th>Объект</th><th>Работа</th><th>Периодичность</th><th>Статус</th><th>Факт</th><th>Исполнитель</th></tr></thead><tbody>' +
    (rows || '<tr><td colspan="7"><div class="empty"><span class="big">≡</span>Записей за указанный период нет</div></td></tr>') +
    "</tbody></table></div>";

  $("#jFStatus").addEventListener("change", e => { jStatus = e.target.value; loadJournal(); });

  setupSearchableCombobox("#jFObjBox", {
    items: objectsCache.map(o => ({
      value: o.ID,
      label: o.Name,
      sub: o.Address ? o.Address.slice(0, 32) : ""
    })),
    selectedValue: jObj,
    allLabel: "Все объекты",
    placeholder: "Поиск объекта...",
    onSelect: (val) => {
      jObj = val;
      loadJournal();
    }
  });

  $("#jFDateFrom").addEventListener("change", e => { jDateFrom = e.target.value; loadJournal(); });
  $("#jFDateTo").addEventListener("change", e => { jDateTo = e.target.value; loadJournal(); });

  const btnToday = $("#jQuickToday");
  if (btnToday) {
    btnToday.onclick = () => {
      const td = todayISO();
      jDateFrom = td;
      jDateTo = td;
      loadJournal();
    };
  }

  const btnMonth = $("#jQuickMonth");
  if (btnMonth) {
    btnMonth.onclick = () => {
      const n = new Date();
      const y = n.getFullYear();
      const m = String(n.getMonth() + 1).padStart(2, "0");
      const lastDay = new Date(y, n.getMonth() + 1, 0).getDate();
      jDateFrom = `${y}-${m}-01`;
      jDateTo = `${y}-${m}-${String(lastDay).padStart(2, "0")}`;
      loadJournal();
    };
  }

  const btnYear = $("#jQuickYear");
  if (btnYear) {
    btnYear.onclick = () => {
      const y = new Date().getFullYear();
      jDateFrom = `${y}-01-01`;
      jDateTo = `${y}-12-31`;
      loadJournal();
    };
  }

  const btnReset = $("#jQuickReset");
  if (btnReset) {
    btnReset.onclick = () => {
      jStatus = "";
      jObj = "";
      jDateFrom = "";
      jDateTo = "";
      loadJournal();
    };
  }

  const buildReportQuery = () => {
    const q = [];
    if (jObj) q.push("object_id=" + encodeURIComponent(jObj));
    if (jDateFrom) q.push("date_from=" + encodeURIComponent(jDateFrom));
    if (jDateTo) q.push("date_to=" + encodeURIComponent(jDateTo));
    if (jStatus) q.push("status=" + encodeURIComponent(jStatus));
    return q.length ? "?" + q.join("&") : "";
  };

  const btnPprPrint = $("#jBtnPprPrint");
  if (btnPprPrint) {
    btnPprPrint.onclick = () => {
      window.open("/api/reports/journal-ppr/html" + buildReportQuery(), "_blank");
    };
  }
  const btnPprExcel = $("#jBtnPprExcel");
  if (btnPprExcel) {
    btnPprExcel.onclick = () => {
      window.open("/api/reports/journal-ppr/excel" + buildReportQuery(), "_blank");
    };
  }
  const btnActPrint = $("#jBtnActPrint");
  if (btnActPrint) {
    btnActPrint.onclick = () => {
      window.open("/api/reports/act-inspection/html" + buildReportQuery(), "_blank");
    };
  }
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

