/* ============================================================
   КАЛЕНДАРЬ ТО — Модуль ИИ-Ассистента и Импорта (ai.js)
   ============================================================ */
// ===== ИНДИКАЦИЯ СТАТУСА ИИ (ПРОВЕРКА API, РЕАЛЬНОЕ ПОДКЛЮЧЕНИЕ, 123-ФЗ) =====

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

  const svgYandex = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" style="vertical-align:middle"><circle cx="12" cy="12" r="11" fill="#FC3F1D"/><path d="M13.8 6h2.1l-3.3 5.4 3.7 6.6h-2.2l-2.7-4.9-1.3 2.1v2.8H8V6h2.1v6.3l3.7-6.3z" fill="#FFF"/></svg>`;
  const svgSber = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" style="vertical-align:middle"><circle cx="12" cy="12" r="11" fill="#21A038"/><path d="M6 12.2l3.8 3.8L18 7.8" stroke="#FFF" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const svgShield = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`;

  let activeLogo = svgShield;
  const provNameLower = (aiStatusCache.provider || "").toLowerCase();
  const dispNameLower = (aiStatusCache.provider_display || "").toLowerCase();

  if (provNameLower.includes("gigachat") || dispNameLower.includes("gigachat")) {
    activeLogo = svgSber;
  } else if (provNameLower.includes("yandex") || dispNameLower.includes("yandex")) {
    activeLogo = svgYandex;
  }

  if (!aiStatusCache.enabled) {
    btn.classList.add("state-disabled");
    btn.innerHTML = `<span class="ai-badge-logo">${svgShield}</span> <span>ИИ: Выключен</span> <span class="ai-status-pill">ВРУЧНУЮ</span>`;
    btn.title = "ИИ отключен в msg.cfg (enabled=false). Все поля заполняются полностью вручную.";
  } else if (aiStatusCache.status === "error") {
    btn.classList.add("state-error");
    btn.innerHTML = `<span class="ai-badge-logo">${activeLogo}</span> <span>${provider}</span> <span class="ai-status-pill pill-error">ОШИБКА API</span>`;
    btn.title = `Внимание! API нейросети не отвечает или указан неверный ключ: ${aiStatusCache.error_detail || 'Ошибка'}. Включен резерв: 123-ФЗ.`;
  } else if (aiStatusCache.is_online && aiStatusCache.status === "online_llm") {
    btn.classList.add("state-online");
    btn.innerHTML = `<span class="ai-badge-logo">${activeLogo}</span> <span class="ai-badge-name">${provider}</span> <span class="ai-status-pill pill-active">АКТИВЕН</span>`;
    btn.title = `ИИ подключен и проверен (${provider}, модель ${aiStatusCache.model}). Доступен нейросетевой анализ.`;
  } else {
    btn.classList.add("state-disabled");
    btn.innerHTML = `<span class="ai-badge-logo">${svgShield}</span> <span>База 123-ФЗ</span> <span class="ai-status-pill">БЕЗ API</span>`;
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
      '<div class="modal-title ai-modal-title">🤖 Помощник по регламентам пожарной безопасности (Нормы ПБ)</div>' +
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
    '</div>',
    "ai-modal-box"
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
      html += '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:12px;background:rgba(255,255,255,0.03);padding:10px 14px;border-radius:10px;border:1px solid var(--line);">';
      html += '<div style="display:flex;align-items:center;gap:12px;">';
      html += '<label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-weight:600;font-size:13px;color:var(--text);">';
      html += '<input type="checkbox" id="aiRecCheckAll" checked style="width:16px;height:16px;accent-color:var(--amber-2);cursor:pointer;"> Выбрать все';
      html += '</label>';
      html += '<span style="font-size:12px;color:var(--text-3);" id="aiSelectedCount">Выбрано: ' + unassigned.length + ' из ' + unassigned.length + '</span>';
      html += '</div>';
      html += '<div style="display:inline-flex;gap:8px;flex-wrap:wrap;">';
      html += '<button class="btn btn-amber btn-sm" id="btnApplySelectedRecs" data-obj="' + esc(oid) + '">✓ Назначить выбранные</button>';
      html += '<button class="btn btn-ghost btn-sm" id="btnApplyAllRecs" data-obj="' + esc(oid) + '" style="color:var(--amber-2);border-color:rgba(245,165,36,0.35);">⚡ Назначить все (' + unassigned.length + ')</button>';
      html += '</div>';
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

    // Обновление счетчика выбранных чекбоксов
    const updateCheckState = () => {
      const allCbs = $$(".ai-rec-check");
      const checkedCbs = $$(".ai-rec-check:checked");
      const cntEl = $("#aiSelectedCount");
      if (cntEl) cntEl.textContent = 'Выбрано: ' + checkedCbs.length + ' из ' + allCbs.length;
      const btnSel = $("#btnApplySelectedRecs");
      if (btnSel) {
        btnSel.disabled = checkedCbs.length === 0;
        btnSel.textContent = '✓ Назначить выбранные (' + checkedCbs.length + ')';
      }
      const chkAll = $("#aiRecCheckAll");
      if (chkAll) {
        chkAll.checked = allCbs.length > 0 && checkedCbs.length === allCbs.length;
        chkAll.indeterminate = checkedCbs.length > 0 && checkedCbs.length < allCbs.length;
      }
    };

    const chkAllEl = $("#aiRecCheckAll");
    if (chkAllEl) {
      chkAllEl.addEventListener("change", (e) => {
        $$(".ai-rec-check").forEach(cb => cb.checked = e.target.checked);
        updateCheckState();
      });
    }

    $$(".ai-rec-check").forEach(cb => {
      cb.addEventListener("change", updateCheckState);
    });

    // Функция отправки кодов на бэкенд
    const applyCodes = async (codes, triggerBtn, originalText) => {
      if (!codes.length) {
        toast("Выберите хотя бы один пункт для назначения", "error");
        return;
      }
      triggerBtn.disabled = true;
      triggerBtn.textContent = "Назначение…";
      const ra = await api("/api/ai/apply", { objectId: oid, workCodes: codes });
      if (ra.ok) {
        notice("Успешно создано " + ra.created_assignments_count + " назначений и " + ra.created_executions_count + " событий в Календаре!");
        runAuditForObject(oid);
        if (currentPage === "assignments") loadAssignments();
        if (currentPage === "calendar") loadCalendar();
        if (currentPage === "dashboard") loadDashboard();
      } else {
        toast(ra.detail || "Ошибка назначения", "error");
        triggerBtn.disabled = false;
        triggerBtn.textContent = originalText;
      }
    };

    // Кнопка 1: Назначить только выбранные чекбоксами
    const btnApplySelected = $("#btnApplySelectedRecs");
    if (btnApplySelected) {
      btnApplySelected.addEventListener("click", () => {
        const codes = $$(".ai-rec-check:checked").map(cb => cb.dataset.code);
        applyCodes(codes, btnApplySelected, "✓ Назначить выбранные");
      });
    }

    // Кнопка 2: Назначить все рекомендации
    const btnApplyAll = $("#btnApplyAllRecs");
    if (btnApplyAll) {
      btnApplyAll.addEventListener("click", () => {
        const codes = $$(".ai-rec-check").map(cb => cb.dataset.code);
        applyCodes(codes, btnApplyAll, "⚡ Назначить все (" + unassigned.length + ")");
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

// -------------------------------------------------------------
// МОДАЛЬНОЕ ОКНО ПОМОЩИ, ЛОГИКИ РАБОТЫ И ИИ-КОНСУЛЬТАНТА
// -------------------------------------------------------------
function openHelpModal(initialTab = "steps") {
  const c = $("#modalBox");
  c.className = "modal help-guide-modal";

  c.innerHTML = `
    <div class="modal-header">
      <div>
        <div class="modal-title" style="display:flex;align-items:center;gap:8px;">
          <span>💡</span> Логика работы и интерактивный помощник
        </div>
        <div style="font-size:12px;color:var(--text-3);margin-top:2px;">
          Пошаговый регламент ведения технического обслуживания систем ПБ
        </div>
      </div>
      <button class="btn-close" id="btnHelpClose" title="Закрыть">✕</button>
    </div>

    <div class="modal-body" style="padding-top:14px;">
      <div class="help-tabs">
        <button class="help-tab-btn ${initialTab === 'steps' ? 'active' : ''}" id="tabBtnSteps">📋 5 шагов работы</button>
        <button class="help-tab-btn ${initialTab === 'features' ? 'active' : ''}" id="tabBtnFeatures">✨ Все функции и перенос</button>
        <button class="help-tab-btn ${initialTab === 'ai' ? 'active' : ''}" id="tabBtnAi">🤖 ИИ-консультант</button>
        <button class="help-tab-btn ${initialTab === 'colors' ? 'active' : ''}" id="tabBtnColors">🎨 Цвета и статусы</button>
      </div>

      <!-- ВКЛАДКА 1: 5 ШАГОВ -->
      <div id="helpTabSteps" class="${initialTab === 'steps' ? '' : 'hidden'}">
        <div class="help-guide-summary">
          <div>
            <div class="help-guide-summary-title">🚀 Маршрут работы с интерфейсом за 5 простых шагов</div>
            <div class="help-guide-summary-sub">От заведения первого объекта до выставления счёта и закрытия акта выполненных работ</div>
          </div>
          <div class="help-steps-indicator" title="5 ключевых этапов">
            <span class="help-indicator-dot done">1</span>
            <span style="color:var(--text-3);font-size:11px;">→</span>
            <span class="help-indicator-dot done">2</span>
            <span style="color:var(--text-3);font-size:11px;">→</span>
            <span class="help-indicator-dot done">3</span>
            <span style="color:var(--text-3);font-size:11px;">→</span>
            <span class="help-indicator-dot done">4</span>
            <span style="color:var(--text-3);font-size:11px;">→</span>
            <span class="help-indicator-dot done">5</span>
          </div>
        </div>

        <div class="flow-steps">
          
          <!-- ШАГ 1 -->
          <div class="flow-step-card">
            <div class="flow-step-num">1</div>
            <div class="flow-step-body">
              <div class="flow-step-title">
                <span>Шаг 1: Добавьте объекты защиты</span>
                <span class="tag tag-fpo">Ф1–Ф5 по 123-ФЗ</span>
              </div>
              <div class="flow-step-desc">
                Перейдите во вкладку <b>«Объекты»</b> и нажмите кнопку <b>«+ Новый объект»</b>. Заполните наименование, фактический адрес, этажность и класс пожарной опасности (ФПО).
              </div>
              <div class="flow-step-points">
                <div class="flow-step-point"><span class="point-ico">✦</span> ИИ-конструктор: назовите объект (например «Школа №5») и ИИ сам определит класс Ф1.2.</div>
                <div class="flow-step-point"><span class="point-ico">✦</span> Карточка объекта хранит контакты ответственных лиц и историю всех систем.</div>
              </div>
            </div>
            <button class="btn btn-amber btn-sm flow-step-btn" data-action="go-page" data-target="objects">1. К Объектам →</button>
          </div>

          <!-- ШАГ 2 -->
          <div class="flow-step-card">
            <div class="flow-step-num">2</div>
            <div class="flow-step-body">
              <div class="flow-step-title">
                <span>Шаг 2: Настройте справочник «Виды работ»</span>
                <span class="tag" style="background:rgba(59,130,246,0.15);color:var(--blue);border:1px solid rgba(59,130,246,0.3);">СП 484 / СП 486</span>
              </div>
              <div class="flow-step-desc">
                В разделе <b>«Виды работ»</b> собраны все нормативные регламенты: АПС, СОУЭ, АУПТ, ВПВ, дымоудаление и огнетушители с кодами ПБ-XX.YY.
              </div>
              <div class="flow-step-points">
                <div class="flow-step-point"><span class="point-ico">✦</span> Базовые работы уже предзаполнены по нормам МЧС РФ и ГОСТ.</div>
                <div class="flow-step-point"><span class="point-ico">✦</span> Можно задавать регламентную периодичность (ежемесячно, ежеквартально, ежегодно) и стоимость.</div>
              </div>
            </div>
            <button class="btn btn-ghost btn-sm flow-step-btn" data-action="go-page" data-target="works">2. Виды работ →</button>
          </div>

          <!-- ШАГ 3 -->
          <div class="flow-step-card">
            <div class="flow-step-num">3</div>
            <div class="flow-step-body">
              <div class="flow-step-title">
                <span>Шаг 3: Закрепите Назначения и сформируйте график</span>
                <span class="tag" style="background:rgba(34,197,94,0.15);color:var(--green);border:1px solid rgba(34,197,94,0.3);">Автопланирование</span>
              </div>
              <div class="flow-step-desc">
                В разделе <b>«Назначения»</b> свяжите Объект с конкретными Видами работ. Система автоматически рассчитает даты всех выездов на год вперёд без накладок.
              </div>
              <div class="flow-step-points">
                <div class="flow-step-point"><span class="point-ico">✦</span> Кнопка «Сформировать график» создаёт календарную сетку в один клик.</div>
                <div class="flow-step-point"><span class="point-ico">✦</span> Возможность указать закреплённого мастера/инженера и интервал ТО.</div>
              </div>
            </div>
            <button class="btn btn-ghost btn-sm flow-step-btn" data-action="go-page" data-target="assignments">3. Назначения →</button>
          </div>

          <!-- ШАГ 4 -->
          <div class="flow-step-card">
            <div class="flow-step-num">4</div>
            <div class="flow-step-body">
              <div class="flow-step-title">
                <span>Шаг 4: Контролируйте Календарь и Журнал выездов</span>
                <span class="tag" style="background:rgba(245,165,36,0.15);color:var(--amber-2);border:1px solid rgba(245,165,36,0.3);">План vs Факт</span>
              </div>
              <div class="flow-step-desc">
                В <b>«Календаре»</b> наглядно видны даты выездов по цветам (синий — план, зелёный — факт, красный — просрочено). Кликните по событию, чтобы закрыть его или перенести.
              </div>
              <div class="flow-step-points">
                <div class="flow-step-point"><span class="point-ico">✦</span> В <b>«Журнале»</b> доступно пакетное закрытие всех работ за выбранный месяц.</div>
                <div class="flow-step-point"><span class="point-ico">✦</span> Звуковые и визуальные напоминания (колокольчик в шапке) предупредят о сроках.</div>
              </div>
            </div>
            <button class="btn btn-ghost btn-sm flow-step-btn" data-action="go-page" data-target="calendar">4. В Календарь →</button>
          </div>

          <!-- ШАГ 5 -->
          <div class="flow-step-card">
            <div class="flow-step-num">5</div>
            <div class="flow-step-body">
              <div class="flow-step-title">
                <span>Шаг 5: Выставляйте Счета и печатайте Акты</span>
                <span class="tag" style="background:rgba(168,85,247,0.15);color:#c084fc;border:1px solid rgba(168,85,247,0.3);">Документооборот</span>
              </div>
              <div class="flow-step-desc">
                В разделе <b>«Счета»</b> нажмите «+ Выставить счёт». Выберите организацию-исполнителя, объект и период — система автоматически подтянет выполненные работы и рассчитает сумму.
              </div>
              <div class="flow-step-points">
                <div class="flow-step-point"><span class="point-ico">✦</span> Готовые печатные формы счёта и двустороннего Акта сдачи-приёмки (А4 / PDF).</div>
                <div class="flow-step-point"><span class="point-ico">✦</span> Автоматическая нумерация с префиксами и отслеживание статуса оплаты.</div>
              </div>
            </div>
            <button class="btn btn-ghost btn-sm flow-step-btn" data-action="go-page" data-target="invoices">5. Счета и Акты →</button>
          </div>

        </div>
      </div>

      <!-- ВКЛАДКА 2: ИИ-КОНСУЛЬТАНТ -->
      <div id="helpTabAi" class="${initialTab === 'ai' ? '' : 'hidden'}">
        <div class="ai-consultant-box">
          <div style="font-size:13px;color:var(--text-2);">
            Задайте любой вопрос по нормам пожарной безопасности (123-ФЗ, СП 484/486/3/10) или по работе системы:
          </div>

          <div class="ai-quick-chips">
            <span class="ai-quick-chip" data-ask="С чего начать работу в системе?">С чего начать?</span>
            <span class="ai-quick-chip" data-ask="Какая периодичность ТО для системы АПС по СП 484?">Периодичность ТО АПС</span>
            <span class="ai-quick-chip" data-ask="Как выставить счёт и распечатать Акт?">Выставить счёт и Акт</span>
            <span class="ai-quick-chip" data-ask="Что означают классы ФПО (Ф3.1, Ф4.3)?">Классы ФПО (ст. 32 123-ФЗ)</span>
            <span class="ai-quick-chip" data-ask="Как работает ИИ без интернета?">Работа ИИ без интернета</span>
          </div>

          <div class="ai-ask-row">
            <input type="text" class="inp ai-ask-input" id="helpAiInput" placeholder="Напишите ваш вопрос (например: Как запланировать ТО дымоудаления?)...">
            <button class="btn btn-amber" id="btnHelpAiAsk" style="white-space:nowrap;">Спросить 🤖</button>
          </div>

          <div id="helpAiResponseHost"></div>
        </div>
      </div>

      <!-- ВКЛАДКА 3: ЦВЕТА И СТАТУСЫ -->
      <div id="helpTabColors" class="${initialTab === 'colors' ? '' : 'hidden'}">
        <div style="display:flex;flex-direction:column;gap:10px;padding:6px 0;">
          <div class="flow-step-card" style="border-left:4px solid var(--blue);">
            <div>
              <div style="font-weight:700;color:var(--blue);font-size:14px;margin-bottom:4px;">🔵 Синий — Запланировано (Planned)</div>
              <div style="font-size:12.5px;color:var(--text-2);">Регламентная работа зафиксирована в графике, срок выезда ещё не наступил.</div>
            </div>
          </div>
          <div class="flow-step-card" style="border-left:4px solid var(--green);">
            <div>
              <div style="font-weight:700;color:var(--green);font-size:14px;margin-bottom:4px;">🟢 Зелёный — Выполнено (Done)</div>
              <div style="font-size:12.5px;color:var(--text-2);">ТО проведено специалистом, запись внесена в журнал выполненных работ.</div>
            </div>
          </div>
          <div class="flow-step-card" style="border-left:4px solid var(--amber-2);">
            <div>
              <div style="font-weight:700;color:var(--amber-2);font-size:14px;margin-bottom:4px;">🟡 Жёлтый / Янтарный — Перенесено (Postponed)</div>
              <div style="font-size:12.5px;color:var(--text-2);">Выезд перенесен на другую согласованную дату по заявке заказчика или техническим причинам.</div>
            </div>
          </div>
          <div class="flow-step-card" style="border-left:4px solid var(--red);">
            <div>
              <div style="font-weight:700;color:var(--red);font-size:14px;margin-bottom:4px;">🔴 Красный — Просрочено (Overdue)</div>
              <div style="font-size:12.5px;color:var(--text-2);">Дата регламентного ТО наступила в прошлом, но факт выполнения не зафиксирован. Требует немедленного внимания диспетчера!</div>
            </div>
          </div>
        </div>
      </div>

      <!-- ВКЛАДКА 4: ВСЕ ВОЗМОЖНОСТИ И ПЕРЕНОС НА СЕРВЕР -->
      <div id="helpTabFeatures" class="${initialTab === 'features' ? '' : 'hidden'}">
        <div style="display:flex;flex-direction:column;gap:12px;padding:4px 0;">
          
          <div class="flow-step-card">
            <div class="flow-step-num" style="background:rgba(111,183,232,0.15);color:var(--moon);border-color:var(--moon);">📊</div>
            <div class="flow-step-body">
              <div class="flow-step-title"><span>Финансовый контроль и KPI в разделе «Счета»</span></div>
              <div class="flow-step-desc">
                План/Факт по выручке текущего месяца, показатель соблюдения сроков регламентов (SLA), контроль общей дебиторской задолженности с детализацией по контрагентам и выставление счетов в 1 клик.
              </div>
            </div>
          </div>

          <div class="flow-step-card">
            <div class="flow-step-num" style="background:rgba(245,165,36,0.15);color:var(--amber-2);border-color:var(--amber);">📑</div>
            <div class="flow-step-body">
              <div class="flow-step-title"><span>Журнал по ППР РФ № 1479 и Акты освидетельствования</span></div>
              <div class="flow-step-desc">
                В разделе «Журнал ТО» доступна мгновенная выгрузка официального Журнала эксплуатации систем противопожарной защиты (постановление Правительства РФ № 1479) в печатную форму А4 и в Excel, а также формирование двусторонних Актов проверки работоспособности (АПС, СОУЭ, ВПВ).
              </div>
            </div>
          </div>

          <div class="flow-step-card">
            <div class="flow-step-num" style="background:rgba(92,201,138,0.15);color:var(--moss);border-color:var(--moss);">🔔</div>
            <div class="flow-step-body">
              <div class="flow-step-title"><span>Колокольчик и уведомления</span></div>
              <div class="flow-step-desc">
                Уведомления за 7 дней до плановых выездов с мягким звуковым сигналом, отметкой «Прочитано всё» и ограничением по времени суток (с 08:00 до 18:00).
              </div>
            </div>
          </div>

          <div class="flow-step-card">
            <div class="flow-step-num" style="background:rgba(168,85,247,0.15);color:#c084fc;border-color:#c084fc;">🌐</div>
            <div class="flow-step-body">
              <div class="flow-step-title"><span>Перенос на рабочий сервер (Linux / Windows VPS)</span></div>
              <div class="flow-step-desc">
                1. <b>Клонирование</b>: <code>git clone &lt;repo-url&gt;</code><br>
                2. <b>Окружение</b>: <code>python -m venv venv &amp;&amp; source venv/bin/activate</code> (или <code>venv\\Scripts\\activate</code>)<br>
                3. <b>Зависимости</b>: <code>pip install -r requirements.txt</code><br>
                4. <b>Запуск</b>: <code>python run.py</code> (сервер стартует на порту 9000, автоматически поднимает SQLite базу <code>data/app.db</code> и фоновые планировщики).
              </div>
            </div>
          </div>

        </div>
      </div>

    </div>

    <div class="modal-footer" style="display:flex;justify-content:space-between;align-items:center;">
      <div style="font-size:11.5px;color:var(--text-3);">
        * Вся нормативная база соответствует ГОСТ, СП и требованиям МЧС России
      </div>
      <button class="btn btn-ghost" id="btnHelpFooterClose">Понятно</button>
    </div>
  `;

  openModal();

  // Навешивание событий
  const btnClose = $("#btnHelpClose");
  const btnFooterClose = $("#btnHelpFooterClose");
  if (btnClose) btnClose.onclick = closeModal;
  if (btnFooterClose) btnFooterClose.onclick = closeModal;

  // Переключение вкладок
  const tabSteps = $("#helpTabSteps");
  const tabFeatures = $("#helpTabFeatures");
  const tabAi = $("#helpTabAi");
  const tabColors = $("#helpTabColors");
  const btnTSteps = $("#tabBtnSteps");
  const btnTFeatures = $("#tabBtnFeatures");
  const btnTAi = $("#tabBtnAi");
  const btnTColors = $("#tabBtnColors");

  function switchTab(target) {
    [tabSteps, tabFeatures, tabAi, tabColors].forEach(el => el && el.classList.add("hidden"));
    [btnTSteps, btnTFeatures, btnTAi, btnTColors].forEach(b => b && b.classList.remove("active"));
    if (target === "steps") {
      tabSteps.classList.remove("hidden");
      btnTSteps.classList.add("active");
    } else if (target === "features") {
      tabFeatures.classList.remove("hidden");
      btnTFeatures.classList.add("active");
    } else if (target === "ai") {
      tabAi.classList.remove("hidden");
      btnTAi.classList.add("active");
    } else if (target === "colors") {
      tabColors.classList.remove("hidden");
      btnTColors.classList.add("active");
    }
  }

  if (btnTSteps) btnTSteps.onclick = () => switchTab("steps");
  if (btnTFeatures) btnTFeatures.onclick = () => switchTab("features");
  if (btnTAi) btnTAi.onclick = () => switchTab("ai");
  if (btnTColors) btnTColors.onclick = () => switchTab("colors");

  // Переходы по разделам
  c.querySelectorAll('[data-action="go-page"]').forEach(btn => {
    btn.onclick = () => {
      const page = btn.dataset.target;
      closeModal();
      showPage(page);
    };
  });

  // Логика вопросов ИИ-консультанту
  const inputAi = $("#helpAiInput");
  const btnAsk = $("#btnHelpAiAsk");
  const hostAi = $("#helpAiResponseHost");

  async function askHelp(q) {
    if (!q || !q.trim()) return;
    if (inputAi) inputAi.value = q;
    if (hostAi) {
      hostAi.innerHTML = `
        <div class="ai-answer-card" style="display:flex;align-items:center;gap:10px;">
          <span class="spin">↻</span> ИИ-помощник формирует ответ по нормам ПБ...
        </div>
      `;
    }
    if (btnAsk) btnAsk.disabled = true;

    try {
      const r = await api("/api/ai/ask", {
        question: q.trim(),
        contextPage: currentPage || "dashboard"
      });
      if (r.ok && r.answer) {
        if (hostAi) {
          hostAi.innerHTML = `
            <div class="ai-answer-card">
              <div class="ai-answer-head">
                <span>🤖 Ответ ассистента</span>
                <span>${esc(r.source || "Экспертная база ПБ")}</span>
              </div>
              <div style="line-height:1.6;">${r.answer.replace(/\n/g, '<br>')}</div>
            </div>
          `;
        }
      } else {
        if (hostAi) {
          hostAi.innerHTML = `<div class="ai-answer-card" style="color:var(--red);">Не удалось получить ответ: ${esc(r.detail || "Ошибка сервиса")}</div>`;
        }
      }
    } catch (err) {
      if (hostAi) {
        hostAi.innerHTML = `<div class="ai-answer-card" style="color:var(--red);">Ошибка сети при обращении к ИИ</div>`;
      }
    } finally {
      if (btnAsk) btnAsk.disabled = false;
    }
  }

  if (btnAsk) {
    btnAsk.onclick = () => askHelp(inputAi ? inputAi.value : "");
  }
  if (inputAi) {
    inputAi.onkeydown = (e) => {
      if (e.key === "Enter") askHelp(inputAi.value);
    };
  }
  c.querySelectorAll(".ai-quick-chip").forEach(chip => {
    chip.onclick = () => askHelp(chip.dataset.ask);
  });
}

// -------------------------------------------------------------
// МОДАЛЬНОЕ ОКНО ИИ-ИМПОРТА ОРГАНИЗАЦИЙ И ДОКУМЕНТОВ
// -------------------------------------------------------------
let importModalState = {
  target: "objects", // "objects" или "companies"
  tab: "text", // "text" или "file"
  parsedItems: [],
  source: "",
  isLoading: false,
};

function openImportModal(initialTarget = "objects") {
  importModalState.target = initialTarget;
  importModalState.tab = "text";
  importModalState.parsedItems = [];
  importModalState.source = "";
  importModalState.isLoading = false;

  renderImportModal();
}

function renderImportModal() {
  const c = $("#modalBox");
  c.className = "modal import-modal";

  const isObj = importModalState.target === "objects";
  const hasResults = importModalState.parsedItems.length > 0;

  const modalTitle = isObj
    ? "📥 Импорт объектов обслуживания и контрагентов (Клиенты)"
    : "🏛 Импорт организаций-исполнителей и реквизитов (Счета)";
  const modalSub = isObj
    ? "Загрузите список обслуживаемых площадок, зданий или контрагентов — ИИ определит адреса, площади, этажность и классы пожарной опасности (123-ФЗ)"
    : "Загрузите карточку или список ваших юридических лиц / ИП — система извлечет банковские реквизиты (БИК, р/с, к/с), ИНН, КПП, ОГРН, адреса и ФИО руководства";

  const placeholderText = isObj
    ? `Пример:
1. ООО «СтройТех», ИНН 7701234567, г. Москва, ул. Ленина, д. 5, оф. 10 (Офисный центр, Ф4.3)
2. ТЦ «Галерея», г. Пермь, Комсомольский пр-кт, 15, площадь 4500 м2, 3 этажа
3. ИП Сидоров А.В. (Склад запчастей, Категория В, Ф5.2)...`
    : `Вставьте реквизиты организации:
ООО «Компания»
ИНН: 5921029563, КПП: 592101001, ОГРН: 1125921000886
Юр. адрес: г. Пермь, ул. Ленина, 10
Банк: ПАО Сбербанк, БИК: 042202603, Р/с: 40702810749230090494
Генеральный директор: Иванов И.И.`;

  c.innerHTML = `
    <div class="modal-header">
      <div>
        <div class="modal-title" style="display:flex;align-items:center;gap:8px;">
          <span>${isObj ? '⌂' : '🏛'}</span> ${modalTitle}
        </div>
        <div style="font-size:12px;color:var(--text-3);margin-top:2px;">
          ${modalSub}
        </div>
      </div>
      <button class="btn-close" id="btnImportClose" title="Закрыть">✕</button>
    </div>

    <div class="modal-body" style="padding-top:14px;">
      <!-- ВЫБОР ЦЕЛЕВОГО РЕЕСТРА -->
      <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;background:var(--panel-2);padding:10px 14px;border-radius:10px;border:1px solid var(--line);margin-bottom:14px;">
        <div style="font-size:13px;font-weight:600;color:var(--text);">Целевой раздел:</div>
        <div style="display:flex;gap:8px;">
          <button type="button" class="btn btn-sm ${isObj ? 'btn-amber' : 'btn-ghost'}" id="btnTargetObjects">
            ⌂ В раздел «Объекты» (клиенты)
          </button>
          <button type="button" class="btn btn-sm ${!isObj ? 'btn-amber' : 'btn-ghost'}" id="btnTargetCompanies">
            🏛 В раздел «Счета» (наши предприятия)
          </button>
        </div>
      </div>

      <!-- ВКЛАДКИ ИСТОЧНИКА: ТЕКСТ / ФАЙЛ -->
      <div class="help-tabs" style="margin-bottom:14px;">
        <button class="help-tab-btn ${importModalState.tab === 'text' ? 'active' : ''}" id="tabImportText">
          📝 Вставка списком / реквизитами (текст)
        </button>
        <button class="help-tab-btn ${importModalState.tab === 'file' ? 'active' : ''}" id="tabImportFile">
          📎 Загрузить файл (Word / Excel / PDF)
        </button>
      </div>

      <!-- ФОРМА: ТЕКСТ -->
      <div id="importTabText" class="${importModalState.tab === 'text' ? '' : 'hidden'}">
        <div class="field">
          <label style="display:flex;justify-content:space-between;">
            <span>${isObj ? 'Вставьте список объектов или контрагентов:' : 'Вставьте карточку сведений или реквизиты предприятия:'}</span>
            <span class="sub" style="font-weight:normal;">${isObj ? 'ИИ сам рассчитает пожарную опасность (123-ФЗ)' : 'ИИ извлечет банковские счета, БИК, ИНН и КПП'}</span>
          </label>
          <textarea class="inp" id="importRawText" rows="6" placeholder="${esc(placeholderText)}"></textarea>
        </div>
        <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:10px;">
          <button class="btn btn-ghost" id="btnImportClearText">Очистить</button>
          <button class="btn btn-amber btn-action-primary" id="btnRunParseText" style="min-height:38px;padding:8px 20px;">
            <span>🤖 Распознать через ИИ</span>
          </button>
        </div>
      </div>

      <!-- ФОРМА: ФАЙЛ -->
      <div id="importTabFile" class="${importModalState.tab === 'file' ? '' : 'hidden'}">
        <input type="file" id="importFileInput" accept=".docx,.doc,.xlsx,.xls,.pdf,.txt,.csv" style="display:none;">
        <div class="import-dropzone ${importModalState.isLoading ? 'loading' : ''}" id="importDropzone">
          ${importModalState.isLoading ? `
            <div class="dropzone-loader-overlay">
              <div class="dropzone-spinner"></div>
              <div class="dropzone-loader-title">🤖 ИИ извлекает данные и классифицирует документ...</div>
              <div class="dropzone-loader-sub">Идёт чтение таблиц, поиск реквизитов (ИНН/КПП/ОГРН/адрес), расчет пожарной опасности (123-ФЗ) и сортировка организаций по алфавиту</div>
            </div>
          ` : `
            <div class="import-dropzone-ico">📄</div>
            <div class="import-dropzone-title">Перетащите сюда документ или кликните для выбора</div>
            <div class="import-dropzone-sub">Поддерживаются форматы: Word (.docx, .doc), Excel (.xlsx, .xls), Adobe PDF (.pdf), TXT, CSV</div>
            <button type="button" class="btn btn-ghost btn-sm" style="margin-top:6px;">Выбрать файл на диске</button>
          `}
        </div>
        <div id="importSelectedFileInfo" class="${importModalState.isLoading ? 'hidden' : 'hidden'}" style="margin-top:12px;display:flex;align-items:center;justify-content:space-between;background:var(--panel-2);padding:10px 16px;border-radius:10px;border:1px solid var(--amber);">
          <div style="display:flex;align-items:center;gap:12px;">
            <span style="font-size:22px;">📎</span>
            <div>
              <b id="importFileName" style="color:var(--text);font-size:13.5px;"></b>
              <div id="importFileSize" class="sub" style="font-size:11.5px;"></div>
            </div>
          </div>
          <button class="btn btn-amber btn-action-primary" id="btnRunParseFile" style="min-height:38px;padding:8px 20px;">
            <span>🤖 Распознать и отсортировать через ИИ</span>
          </button>
        </div>
      </div>

      <!-- БЛОК ЗАГРУЗКИ ТЕКСТА (если активна вкладка Текст) -->
      <div id="importLoadingHost" class="${importModalState.isLoading && importModalState.tab === 'text' ? '' : 'hidden'}" style="margin:20px 0;text-align:center;padding:24px;background:var(--panel-2);border-radius:12px;border:1px solid var(--line);">
        <div class="dropzone-spinner" style="margin:0 auto 12px;"></div>
        <div style="font-weight:700;color:var(--amber-2);font-size:14px;">ИИ анализирует текст и классифицирует организации...</div>
        <div style="font-size:12px;color:var(--text-3);margin-top:4px;">Извлечение реквизитов, определение классов пожарной опасности (123-ФЗ) и сортировка по алфавиту</div>
      </div>

      <!-- РЕЗУЛЬТАТЫ РАСПОЗНАВАНИЯ -->
      <div id="importResultsHost" class="${hasResults ? '' : 'hidden'}">
        <div class="import-stats-bar">
          <div>
            <span style="color:var(--moss);font-weight:700;">✓ Распознано организаций: ${importModalState.parsedItems.length}</span>
            <span style="color:var(--text-3);margin-left:8px;">(Источник: ${esc(importModalState.source)})</span>
          </div>
          <div style="font-size:12px;color:var(--amber-2);">
            🔤 Автоматически отсортировано по организациям (А-Я)
          </div>
        </div>

        <div class="import-preview-table-wrap">
          <table class="import-preview-table" id="importPreviewTable">
            <thead>
              <tr>
                <th style="width:36px;"><input type="checkbox" id="importCheckAll" checked title="Выбрать все"></th>
                <th>№</th>
                <th>${isObj ? 'Организация / Объект' : 'Организация-исполнитель'}</th>
                <th>ИНН / КПП</th>
                <th>${isObj ? 'Адрес' : 'Банк и реквизиты'}</th>
                <th>${isObj ? 'ФПО / Кат.' : 'ОГРН'}</th>
                <th>${isObj ? 'Площадь / Эт.' : 'Руководство / Контакты'}</th>
              </tr>
            </thead>
            <tbody>
              ${importModalState.parsedItems.map((item, idx) => `
                <tr>
                  <td><input type="checkbox" class="import-row-check" data-idx="${idx}" checked></td>
                  <td class="mono" style="color:var(--text-3);">${idx + 1}</td>
                  <td>
                    <b>${esc(item.name)}</b>
                    ${isObj && item.category ? `<div class="sub">${esc(item.category)}</div>` : ''}
                    ${!isObj && item.address ? `<div class="sub" style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(item.address)}">📍 ${esc(item.address)}</div>` : ''}
                  </td>
                  <td class="mono">
                    <div>${esc(item.inn || "—")}</div>
                    ${item.kpp ? `<div class="sub" style="font-size:11px;">КПП ${esc(item.kpp)}</div>` : ''}
                  </td>
                  <td>
                    ${isObj ? `
                      <div style="max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${esc(item.address)}">${esc(item.address || "—")}</div>
                    ` : `
                      <div style="max-width:260px;font-size:12px;">
                        ${item.bank ? `<div><b>${esc(item.bank)}</b></div>` : ''}
                        ${item.account ? `<div class="mono sub" style="font-size:11px;">р/с ${esc(item.account)}</div>` : ''}
                        ${item.bik ? `<div class="mono sub" style="font-size:11px;">БИК ${esc(item.bik)}</div>` : ''}
                        ${!item.bank && !item.account ? `<span style="color:var(--text-3);">—</span>` : ''}
                      </div>
                    `}
                  </td>
                  <td>
                    ${isObj ? `
                      <span class="tag tag-fpo" style="font-size:11px;">${esc(item.functional_hazard || "Ф3.1")}</span>
                      <span class="tag tag-fire-cat" style="font-size:11px;margin-left:4px;">${esc(item.fire_hazard_category || "В")}</span>
                    ` : `
                      <span class="mono" style="font-size:11px;">${esc(item.ogrn || "—")}</span>
                    `}
                  </td>
                  <td>
                    ${isObj ? `
                      <span class="mono" style="font-size:11px;">${item.total_area ? item.total_area + ' м²' : '—'} ${item.floors ? '· ' + item.floors + ' эт.' : ''}</span>
                    ` : `
                      <div style="font-size:11.5px;">
                        ${item.contact_person ? `<div>👤 ${esc(item.contact_person)}</div>` : ''}
                        ${item.phone ? `<div class="sub">📞 ${esc(item.phone)}</div>` : ''}
                        ${item.email ? `<div class="sub">✉ ${esc(item.email)}</div>` : ''}
                        ${!item.contact_person && !item.phone && !item.email ? '<span class="sub">—</span>' : ''}
                      </div>
                    `}
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="modal-footer" style="display:flex;justify-content:space-between;align-items:center;">
      <button class="btn btn-ghost" id="btnImportCancel">Отмена</button>
      <div style="display:flex;gap:12px;align-items:center;">
        <span id="importSelectedCount" style="font-size:12px;color:var(--text-2);">
          ${hasResults ? `Выбрано: ${importModalState.parsedItems.length} из ${importModalState.parsedItems.length}` : ''}
        </span>
        <button class="btn btn-amber btn-action-primary" id="btnSaveBatchImport" ${hasResults ? '' : 'disabled'} style="min-height:38px;padding:8px 20px;">
          📥 Добавить выбранные в ${isObj ? 'Объекты' : 'Организации'}
        </button>
      </div>
    </div>
  `;

  openModal();

  // Навешивание событий
  const btnClose = $("#btnImportClose");
  const btnCancel = $("#btnImportCancel");
  if (btnClose) btnClose.onclick = closeModal;
  if (btnCancel) btnCancel.onclick = closeModal;

  // Переключение целевого реестра
  const btnTObj = $("#btnTargetObjects");
  const btnTComp = $("#btnTargetCompanies");
  if (btnTObj) {
    btnTObj.onclick = () => {
      importModalState.target = "objects";
      renderImportModal();
    };
  }
  if (btnTComp) {
    btnTComp.onclick = () => {
      importModalState.target = "companies";
      renderImportModal();
    };
  }

  // Переключение вкладок Текст / Файл
  const tabText = $("#tabImportText");
  const tabFile = $("#tabImportFile");
  if (tabText) {
    tabText.onclick = () => {
      importModalState.tab = "text";
      renderImportModal();
    };
  }
  if (tabFile) {
    tabFile.onclick = () => {
      importModalState.tab = "file";
      renderImportModal();
    };
  }

  // Очистка текста
  const btnClear = $("#btnImportClearText");
  if (btnClear) {
    btnClear.onclick = () => {
      const ta = $("#importRawText");
      if (ta) ta.value = "";
    };
  }

  // Запуск распознавания текста
  const btnRunText = $("#btnRunParseText");
  if (btnRunText) {
    btnRunText.onclick = async () => {
      const textVal = $("#importRawText") ? $("#importRawText").value.trim() : "";
      if (!textVal) {
        toast("Вставьте текст или список для распознавания", "error");
        return;
      }
      importModalState.isLoading = true;
      renderImportModal();

      try {
        const res = await api("/api/ai/import/parse-text", { text: textVal });
        importModalState.isLoading = false;
        if (res.ok && Array.isArray(res.items)) {
          importModalState.parsedItems = res.items;
          importModalState.source = res.source || "ИИ";
          notice(`Распознано и отсортировано ${res.items.length} организаций`);
        } else {
          toast(res.detail || "Не удалось распознать данные", "error");
        }
      } catch (err) {
        importModalState.isLoading = false;
        toast("Ошибка обращения к сервису распознавания", "error");
      }
      renderImportModal();
    };
  }

  // Drag & drop и выбор файла
  const dropzone = $("#importDropzone");
  const fileInput = $("#importFileInput");
  let currentFile = null;

  if (dropzone && fileInput) {
    dropzone.onclick = () => fileInput.click();

    ["dragenter", "dragover"].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
      }, false);
    });

    ["dragleave", "drop"].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
      }, false);
    });

    dropzone.addEventListener("drop", (e) => {
      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length > 0) {
        handleFileSelected(dt.files[0]);
      }
    });

    fileInput.onchange = (e) => {
      if (e.target.files && e.target.files.length > 0) {
        handleFileSelected(e.target.files[0]);
      }
    };
  }

  function handleFileSelected(file) {
    currentFile = file;
    const infoBox = $("#importSelectedFileInfo");
    const nameEl = $("#importFileName");
    const sizeEl = $("#importFileSize");
    if (infoBox && nameEl && sizeEl) {
      infoBox.classList.remove("hidden");
      nameEl.textContent = file.name;
      const szKb = (file.size / 1024).toFixed(1);
      sizeEl.textContent = `${szKb} КБ · Нажмите кнопку для распознавания`;
    }
  }

  // Запуск распознавания файла
  const btnRunFile = $("#btnRunParseFile");
  if (btnRunFile) {
    btnRunFile.onclick = async () => {
      if (!currentFile) {
        toast("Выберите файл", "error");
        return;
      }
      importModalState.isLoading = true;
      renderImportModal();

      try {
        const formData = new FormData();
        formData.append("file", currentFile);

        const resp = await fetch("/api/ai/import/parse-file", {
          method: "POST",
          body: formData,
        });
        const res = await resp.json();
        importModalState.isLoading = false;

        if (resp.ok && res.ok && Array.isArray(res.items)) {
          importModalState.parsedItems = res.items;
          importModalState.source = `${res.filename} (${res.source || 'ИИ'})`;
          notice(`Распознано из файла: ${res.items.length} организаций`);
        } else {
          toast(res.detail || "Не удалось извлечь данные из файла", "error");
        }
      } catch (err) {
        importModalState.isLoading = false;
        toast("Ошибка загрузки файла", "error");
      }
      renderImportModal();
    };
  }

  // Чекбоксы выбора
  const checkAll = $("#importCheckAll");
  if (checkAll) {
    checkAll.onchange = (e) => {
      $$(".import-row-check").forEach(cb => cb.checked = e.target.checked);
      updateSelectedCount();
    };
  }

  c.querySelectorAll(".import-row-check").forEach(cb => {
    cb.onchange = updateSelectedCount;
  });

  function updateSelectedCount() {
    const checked = $$(".import-row-check:checked").length;
    const total = importModalState.parsedItems.length;
    const countEl = $("#importSelectedCount");
    if (countEl) countEl.textContent = `Выбрано: ${checked} из ${total}`;
    const btnSave = $("#btnSaveBatchImport");
    if (btnSave) btnSave.disabled = (checked === 0);
  }

  // Сохранение выбранных
  const btnSaveBatch = $("#btnSaveBatchImport");
  if (btnSaveBatch) {
    btnSaveBatch.onclick = async () => {
      const selectedIndices = $$(".import-row-check:checked").map(cb => parseInt(cb.dataset.idx, 10));
      if (!selectedIndices.length) {
        toast("Выберите хотя бы одну организацию для добавления", "error");
        return;
      }

      const itemsToSave = selectedIndices.map(idx => importModalState.parsedItems[idx]);
      btnSaveBatch.disabled = true;
      btnSaveBatch.textContent = "Сохранение...";

      try {
        const res = await api("/api/ai/import/save-batch", {
          items: itemsToSave,
          importAs: importModalState.target,
        });

        if (res.ok) {
          notice(`Успешно добавлено ${res.created_count} организаций!`);
          closeModal();
          // Обновляем текущую страницу
          if (importModalState.target === "objects") {
            showPage("objects");
          } else {
            showPage("invoices");
          }
        } else {
          toast(res.detail || "Ошибка при сохранении организаций", "error");
          btnSaveBatch.disabled = false;
          btnSaveBatch.textContent = "Добавить выбранные";
        }
      } catch (err) {
        toast("Ошибка сети при сохранении", "error");
        btnSaveBatch.disabled = false;
        btnSaveBatch.textContent = "Добавить выбранные";
      }
    };
  }
}
