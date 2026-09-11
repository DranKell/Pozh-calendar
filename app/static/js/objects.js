/* ============================================================
   КАЛЕНДАРЬ ТО — Модуль Объектов (objects.js)
   ============================================================ */
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
      '<button class="btn btn-ghost" data-action="open-import" data-target="objects" title="Импорт объектов и организаций из текста или файлов DOC, Excel, PDF">📥 Импорт через ИИ</button>' +
      aiToolbarBtn +
      '<div class="search-box"><input type="text" class="inp" id="objSearch" placeholder="Поиск объектов…"></div>' +
      '<span class="toolbar-hint">Всего: <span id="objCount">' + r.data.length + '</span></span>' +
    '</div>' +
    '<div class="panel table-panel"><table id="objectsTable"><thead><tr><th>Объект</th><th>Класс ФПО / Кат.</th><th>Площадь/Этажи</th><th>Назначений</th><th>Выполнено</th><th>Просрочено</th><th></th></tr></thead><tbody>' +
    (rows || '<tr><td colspan="7"><div class="empty"><span class="big">⌂</span>Объектов пока нет — добавьте первый или импортируйте через ИИ</div></td></tr>') +
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
    '<div class="modal-foot" style="justify-content:space-between;flex-wrap:wrap;gap:10px;">' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;">' +
        '<button class="btn btn-amber" data-action="assign-new" data-object="' + esc(o.ID) + '">+ Назначить работу</button>' +
        '<button class="btn btn-ghost" data-action="ai-audit-obj" data-id="' + esc(o.ID) + '" style="color:var(--amber-2);border-color:rgba(245,165,36,0.4)">🤖 ИИ-Аудит регламентов</button>' +
        '<button class="btn btn-ghost" data-action="report-obj-ppr" data-id="' + esc(o.ID) + '" title="Журнал эксплуатации систем ППЗ по ППР РФ № 1479">📑 Журнал ППР 1479</button>' +
        '<button class="btn btn-ghost" data-action="report-obj-act" data-id="' + esc(o.ID) + '" title="Акт проверки работоспособности систем ППЗ">📄 Акт проверки</button>' +
      '</div>' +
      '<div style="display:flex;gap:8px;">' +
        '<button class="btn btn-ghost" data-action="inv-new" data-object="' + esc(o.ID) + '">💸 Счёт</button>' +
        '<button class="btn btn-ghost" data-action="modal-close">Закрыть</button>' +
      '</div>' +
    "</div>"
  );
}

/* ---------- виды работ ---------- */
