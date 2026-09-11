/* ============================================================
   КАЛЕНДАРЬ ТО — Модуль Дашборда и KPI (dashboard.js)
   ============================================================ */
/* ---------- кеши ---------- */
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
    '<td class="mono col-date">' + fmtDate(e.PlannedDate) + "</td>" +
    '<td class="col-obj"><b>' + esc(e.ObjectName) + "</b></td>" +
    '<td class="col-work">' + esc(e.WorkName) + "</td>" +
    '<td class="col-status">' + statusBadge(e.Status, isOver || e.IsOverdue) + "</td></tr>";
}
function listTable(rows) {
  return '<table><thead><tr><th class="col-date">Дата</th><th class="col-obj">Объект</th><th class="col-work">Работа</th><th class="col-status" style="text-align:right">Статус</th></tr></thead><tbody>' + rows + "</tbody></table>";
}

async function loadDashboard() {
  const host = $("#page-dashboard");
  host.innerHTML = '<div class="empty"><span class="big">🦉</span>Считаем показатели…</div>';
  const [stats, up, over, debtorsRes] = await Promise.all([
    api("/api/dashboard/stats"),
    api("/api/dashboard/upcoming"),
    api("/api/dashboard/overdue"),
    api("/api/dashboard/debtors?limit=5"),
  ]);
  if (!stats.ok) { host.innerHTML = '<div class="empty"><span class="big">⚠️</span>Не удалось загрузить данные</div>'; return; }
  const s = stats.data;
  const upRows = (up.data || []).map(e => execTr(e)).join("");
  const overRows = (over.data || []).map(e => execTr(e, true)).join("");
  const debtorsList = debtorsRes.ok ? debtorsRes.data : [];

  // Таблица дебиторов
  let debtorsTableHtml = "";
  if (debtorsList.length > 0) {
    debtorsTableHtml =
      '<table><thead><tr><th>Объект</th><th>Неоплачено</th><th>Долг</th><th></th></tr></thead><tbody>' +
      debtorsList.map(d =>
        '<tr class="clickable" data-action="debtor-open" data-objid="' + esc(d.ObjectId) + '">' +
          '<td><b>' + esc(d.ObjectName) + '</b><div class="sub">' + esc(d.ObjectAddress || d.ObjectInn || "") + '</div></td>' +
          '<td><span class="badge b-over">' + d.UnpaidInvoicesCount + ' сч.</span></td>' +
          '<td class="mono" style="color:var(--ember);font-weight:700;">' + fmtMoney(d.TotalDebt) + '</td>' +
          '<td style="text-align:right"><button class="btn btn-ghost btn-sm" data-action="nav-invoices-filter" data-objid="' + esc(d.ObjectId) + '" title="Открыть неоплаченные счета">Счета ↗</button></td>' +
        '</tr>'
      ).join("") +
      '</tbody></table>';
  } else {
    debtorsTableHtml = '<div class="empty"><span class="big">🎉</span>Дебиторской задолженности нет. Все счета оплачены!</div>';
  }
  host.innerHTML =
    '<div class="stats">' +
      statCard("Объектов", s.ObjectsCount, "на обслуживании", "") +
      statCard("Видов работ", s.WorksCount, "регламенты ПБ", "moon") +
      statCard("Назначений", s.AssignmentsCount, "активных договоров", "moon") +
      statCard("В этом месяце", s.MonthDone + " / " + s.MonthTotal, "выполнено работ", "") +
      statCard("Просрочено", s.Overdue, s.Overdue > 0 ? "требуют внимания" : "всё по графику", s.Overdue > 0 ? "danger" : "ok") +
    "</div>" +

    '<div class="dash-cols dash-cols-3">' +
      '<div class="panel panel-dash-table"><h3>Ближайшие работы</h3>' +
        (upRows ? listTable(upRows) : '<div class="empty">Пока ничего не запланировано</div>') +
      "</div>" +
      '<div class="panel panel-dash-table"><h3>Просроченные</h3>' +
        (overRows ? listTable(overRows) : '<div class="empty"><span class="big">✅</span>Просрочек нет</div>') +
      "</div>" +
      '<div class="panel panel-debtors panel-dash-table"><h3>Контроль дебиторской задолженности</h3>' +
        debtorsTableHtml +
      "</div>" +
    "</div>";

  // Обработчики кликов на должников для мгновенного перехода в счета
  $$("#page-dashboard [data-action='nav-invoices-filter']").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      const objId = btn.dataset.objid;
      showPage("invoices");
      setTimeout(() => {
        const objSelect = $("#invFObj");
        if (objSelect) {
          objSelect.value = objId;
          objSelect.dispatchEvent(new Event("change"));
        }
      }, 100);
    });
  });
}

