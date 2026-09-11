/* ============================================================
   КАЛЕНДАРЬ ТО — Модуль Ядра и Утилит (core.js)
   ============================================================ */
// Общие глобальные переменные состояния
var objectsCache = [], worksCache = [];
var calY = new Date().getFullYear();
var calM = new Date().getMonth() + 1;
var calObj = "", calWork = "", calStatus = "";
var currentPage = "dashboard";
var aiStatusCache = { enabled: true, is_online: false, has_api_key: false, status: "expert_offline", mode: "123-ФЗ" };

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


function openModal(html, modalClass = "") {
  const box = $("#modalBox");
  box.className = "modal" + (modalClass ? " " + modalClass : "");
  if (html !== undefined) {
    box.innerHTML = html;
  }
  $("#modalOverlay").classList.remove("hidden");
}
function closeModal() {
  $("#modalOverlay").classList.add("hidden");
  const box = $("#modalBox");
  if (box) box.className = "modal";
}

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

/**
 * Инициализация интерактивного выпадающего списка с живым автоподбором и вводом текста.
 */
function setupSearchableCombobox(containerId, options) {
  const container = typeof containerId === "string" ? $(containerId) : containerId;
  if (!container) return;

  const { items, selectedValue, allLabel, placeholder, onSelect } = options;
  const selectedItem = items.find(it => String(it.value) === String(selectedValue));
  const initialText = selectedItem ? selectedItem.label : "";

  container.classList.add("searchable-combobox");
  container.innerHTML =
    '<div class="combobox-input-wrap">' +
      '<input type="text" class="inp combobox-input" placeholder="' + esc(placeholder || allLabel || "Все объекты") + '" value="' + esc(initialText) + '" autocomplete="off" spellcheck="false">' +
      '<div class="combobox-actions">' +
        (initialText ? '<button type="button" class="combobox-clear" title="Очистить (Все объекты)">✕</button>' : '') +
        '<span class="combobox-caret">▼</span>' +
      '</div>' +
    '</div>' +
    '<div class="combobox-dropdown"></div>';

  const input = container.querySelector(".combobox-input");
  const dropdown = container.querySelector(".combobox-dropdown");
  let clearBtn = container.querySelector(".combobox-clear");

  function renderList(query = "") {
    const q = query.trim().toLowerCase();
    const filtered = items.filter(it => !q || it.label.toLowerCase().includes(q) || (it.sub && it.sub.toLowerCase().includes(q)));

    let html = '<div class="combobox-item' + (!selectedValue ? ' selected' : '') + '" data-val="">' +
      '<span><b>' + esc(allLabel || "Все объекты") + '</b></span>' +
      '</div>';

    if (filtered.length) {
      html += filtered.map(it => {
        const isSel = String(it.value) === String(selectedValue);
        const subHtml = it.sub ? '<span class="item-sub">' + esc(it.sub) + '</span>' : '';
        return '<div class="combobox-item' + (isSel ? ' selected' : '') + '" data-val="' + esc(it.value) + '" data-label="' + esc(it.label) + '">' +
          '<span>' + esc(it.label) + '</span>' + subHtml +
          '</div>';
      }).join("");
    } else {
      html += '<div class="combobox-item-empty">Ничего не найдено</div>';
    }

    dropdown.innerHTML = html;
  }

  function openDropdown() {
    renderList(input.value === initialText ? "" : input.value);
    container.classList.add("open");
  }

  function closeDropdown() {
    container.classList.remove("open");
  }

  input.addEventListener("focus", () => {
    openDropdown();
    input.select();
  });

  input.addEventListener("input", e => {
    container.classList.add("open");
    renderList(e.target.value);
    updateClearBtn();
  });

  input.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      closeDropdown();
      input.blur();
    } else if (e.key === "Enter") {
      const firstItem = dropdown.querySelector(".combobox-item");
      if (firstItem) {
        firstItem.click();
      }
    }
  });

  function updateClearBtn() {
    const actions = container.querySelector(".combobox-actions");
    if (input.value.trim() && !clearBtn) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "combobox-clear";
      btn.title = "Очистить (Все объекты)";
      btn.textContent = "✕";
      btn.onclick = (ev) => {
        ev.stopPropagation();
        input.value = "";
        closeDropdown();
        onSelect("", allLabel || "Все объекты");
      };
      actions.insertBefore(btn, actions.firstChild);
      clearBtn = btn;
    } else if (!input.value.trim() && clearBtn) {
      clearBtn.remove();
      clearBtn = null;
    }
  }

  dropdown.addEventListener("click", e => {
    const item = e.target.closest(".combobox-item");
    if (!item) return;
    const val = item.dataset.val || "";
    const label = item.dataset.label || (allLabel || "Все объекты");
    input.value = val ? label : "";
    closeDropdown();
    updateClearBtn();
    onSelect(val, label);
  });

  // Закрытие по клику вне
  document.addEventListener("click", ev => {
    if (!container.contains(ev.target)) {
      closeDropdown();
      if (!selectedValue) {
        input.value = "";
      } else {
        const cur = items.find(it => String(it.value) === String(selectedValue));
        input.value = cur ? cur.label : "";
      }
      updateClearBtn();
    }
  });
}

/* ---------- модалка действия (вместо confirm/prompt) ---------- */
function actionModal(opts) {
  const danger = opts.danger ? "btn-danger" : "btn-amber";
  const inputs = (opts.inputs || []).map(f =>
    '<div class="field"><label>' + esc(f.label) + (f.required ? " *" : "") + '</label>' +
    (f.type === "textarea"
      ? '<textarea class="inp" id="am-' + f.id + '" rows="3" placeholder="' + esc(f.placeholder || "") + '">' + esc(f.value || "") + '</textarea>'
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

