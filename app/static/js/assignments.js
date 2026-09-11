/* ============================================================
   КАЛЕНДАРЬ ТО — Модуль Назначений (assignments.js)
   ============================================================ */
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
