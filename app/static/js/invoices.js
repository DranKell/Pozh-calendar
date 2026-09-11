/* ============================================================
   КАЛЕНДАРЬ ТО — Модуль Счетов и Организаций (invoices.js)
   ============================================================ */
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
  const [r, statsRes] = await Promise.all([
    api("/api/invoices/"),
    api("/api/dashboard/stats")
  ]);
  if (!r.ok) { host.innerHTML = '<div class="empty">Не удалось загрузить счета</div>'; return; }

  const s = (statsRes && statsRes.ok) ? statsRes.data : {};

  // Выручка за месяц (План / Факт)
  const revPct = s.RevenuePercent || 0;
  const revActualFormatted = fmtMoney(s.RevenueActual || 0);
  const revPlannedFormatted = fmtMoney(s.RevenuePlanned || 0);

  // SLA соблюдения регламентов
  const slaPct = s.SlaPercent || 0;
  let slaTone = "ok";
  if (slaPct < 75) slaTone = "danger";
  else if (slaPct < 90) slaTone = "amber";

  // Дебиторская задолженность
  const debtTotalFormatted = fmtMoney(s.TotalDebt || 0);
  const debtorsCount = s.DebtorsCount || 0;
  const debtTone = (s.TotalDebt || 0) > 0 ? "danger" : "ok";

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
    <div class="stats stats-kpi">
      <div class="stat stat-featured moon">
        <div class="stat-label">💰 Выручка за месяц (План / Факт)</div>
        <div class="stat-value rev-val">${revActualFormatted} <span class="stat-subval">/ ${revPlannedFormatted}</span></div>
        <div class="kpi-progress-wrap">
          <div class="kpi-progress-bar" style="width:${Math.min(100, Math.max(0, revPct))}%"></div>
        </div>
        <div class="stat-note">Выполнение финансового плана: <b>${revPct}%</b></div>
      </div>

      <div class="stat ${slaTone}">
        <div class="stat-label">⏳ SLA соблюдения регламентов</div>
        <div class="stat-value" style="color:${slaPct >= 90 ? 'var(--moss)' : (slaPct >= 75 ? 'var(--amber-2)' : 'var(--ember)')}">
          ${slaPct}% <span class="stat-subval">(${s.DoneOnTime || 0} вовремя)</span>
        </div>
        <div class="stat-note">${slaPct >= 90 ? 'Высокая дисциплина ТО' : 'Есть срывы плановых сроков'}</div>
      </div>

      <div class="stat ${debtTone}">
        <div class="stat-label">🔴 Дебиторская задолженность</div>
        <div class="stat-value" style="color:${(s.TotalDebt || 0) > 0 ? 'var(--ember)' : 'var(--moss)'}">${debtTotalFormatted}</div>
        <div class="stat-note">${debtorsCount > 0 ? (debtorsCount + ' объектов с задолженностью') : 'Задолженности нет'}</div>
      </div>
    </div>

    <div class="toolbar">
      <button class="btn btn-amber" data-action="inv-new">+ Новый счёт</button>
      <div class="search-box"><input type="text" class="inp" id="invSearch" placeholder="Поиск счетов…"></div>
      <button class="btn btn-ghost" data-action="inv-settings">🏛 Организации и реквизиты</button>
      <button class="btn btn-ghost" data-action="open-import" data-target="companies" title="Импорт организаций и реквизитов из текста или файлов DOC, Excel, PDF">📥 Импорт организаций</button>
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


