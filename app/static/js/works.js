/* ============================================================
   КАЛЕНДАРЬ ТО — Модуль Видов Работ (works.js)
   ============================================================ */
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
