/* ============================================================
   КАЛЕНДАРЬ ТО — Главный модуль / Диспетчер (main.js)
   ============================================================ */
/* ---------- навигация ---------- */
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
    case "exec-move": {
      const curDate = btn.dataset.date || todayISO();
      const objName = btn.dataset.obj || "";
      const workName = btn.dataset.work || "";
      const infoHtml = objName
        ? '<div style="margin-bottom:10px;"><b>' + esc(objName) + '</b><br><span style="color:var(--text-3);">' + esc(workName) + '</span></div>'
        : '';
      actionModal({
        title: "Перенос регламентной работы",
        body: infoHtml + "Выберите новую плановую дату выполнения работы:",
        inputs: [
          { id: "new_date", label: "Новая дата выполнения", type: "date", required: true, value: curDate }
        ],
        confirmText: "Перенести",
        onConfirm: async (vals) => {
          const nd = vals.new_date;
          if (!nd) { notice("Укажите новую дату", "error"); return; }
          const r = await api("/api/executions/" + id + "/reschedule", { NewDate: nd });
          if (r.ok) {
            notice("Работа перенесена на " + fmtDate(nd), "amber");
            closeModal();
            PAGES[currentPage].load();
          } else {
            notice(r.detail || "Ошибка переноса", "error");
          }
        }
      });
      break;
    }
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
    case "report-obj-ppr": window.open("/api/objects/" + encodeURIComponent(btn.dataset.id) + "/journal-ppr/html", "_blank"); break;
    case "report-obj-act": window.open("/api/objects/" + encodeURIComponent(btn.dataset.id) + "/act-inspection/html", "_blank"); break;
    case "open-help": openHelpModal(); break;
    case "open-import": openImportModal(btn.dataset.target || "objects"); break;


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



