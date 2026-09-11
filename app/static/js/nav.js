/* ============================================================
   КАЛЕНДАРЬ ТО — Навигация, Виджеты, Колокольчик (nav.js)
   ============================================================ */
// ===== КУРСЫ ВАЛЮТ (ЦБ РФ + Binance, всё в ₽) =====
const FX_CACHE_KEY = "fx_cache_v2";
const FX_PREV_KEY = "fx_prev_v2";
const FX_TTL = 2 * 60 * 60 * 1000; // 2 часа
const FX_META = {
  USD: { sym: "$", cls: "usd" },
  EUR: { sym: "€", cls: "eur" },
  CNY: { sym: "¥", cls: "cny" },
  BTC: { sym: "₿", cls: "btc" }
};

function fmtFx(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(2) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return n.toFixed(2);
}

function fmtDeltaRub(n) {
  const sign = n >= 0 ? "+" : "−";
  const a = Math.abs(n);
  const s = a >= 1000 ? new Intl.NumberFormat("ru-RU").format(Math.round(a)) : a.toFixed(2);
  return sign + s + " ₽";
}
function renderFx(rates, prev) {
  const host = document.getElementById("fxWidget");
  if (!host) return;
  if (!rates) { host.innerHTML = '<span class="fx-loading">курсы недоступны</span>'; return; }
  host.innerHTML = Object.keys(FX_META).filter(c => rates[c] != null).map((c, i) => {
    const meta = FX_META[c];
    const v = rates[c];
    const p = prev ? prev[c] : null;
    const diff = (p != null) ? (v - p) : null;
    const changed = diff != null && Math.abs(diff) > 0.0001;
    const dir = changed ? (diff > 0 ? "up" : "down") : "flat";
    const ar = dir === "up" ? "▲" : (dir === "down" ? "▼" : "•");
    let chip;
    if (!changed) {
      chip = '<span class="fx-chg flat"><span class="ar">•</span></span>';
    } else if (c === "BTC") {
      const pct = (diff / p) * 100;
      const sign = pct > 0 ? "+" : "−";
      chip = '<span class="fx-chg ' + dir + '" title="изменение: ' + fmtDeltaRub(diff) + '">' +
             '<span class="ar">' + ar + '</span>' + sign + Math.abs(pct).toFixed(2) + '%</span>';
    } else {
      const sign = diff > 0 ? "+" : "−";
      chip = '<span class="fx-chg ' + dir + '">' +
             '<span class="ar">' + ar + '</span>' + sign + Math.abs(diff).toFixed(2) + ' ₽</span>';
    }
    const cardTitle = (c === "BTC" && changed)
      ? ' title="BTC к рублю · изменение ' + fmtDeltaRub(diff) + '"'
      : ' title="' + c + ' к рублю"';
    return '<div class="fx-card ' + meta.cls + '" style="animation-delay:' + (i * 70) + 'ms"' + cardTitle + '>' +
      '<div class="fx-ico">' + meta.sym + '</div>' +
      '<div class="fx-body"><span class="fx-code">' + c + '</span><span class="fx-val">' + fmtFx(v) + ' ₽</span></div>' +
      chip + '</div>';
  }).join("");
}

function setFxStamp(ts) {
  const el = document.getElementById("fxUpdated");
  if (!el) return;
  const d = ts ? new Date(ts) : new Date();
  el.textContent = "обновлено " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
}

async function fetchBtcUsd() {
  // 1. Попытка через Binance
  try {
    const r = await fetch("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", { cache: "no-store" });
    const j = await r.json();
    if (j && j.price) return parseFloat(j.price);
  } catch (e) {}

  // 2. Попытка через Coinbase
  try {
    const r = await fetch("https://api.coinbase.com/v2/prices/BTC-USD/spot", { cache: "no-store" });
    const j = await r.json();
    if (j && j.data && j.data.amount) return parseFloat(j.data.amount);
  } catch (e) {}

  // 3. Попытка через KuCoin
  try {
    const r = await fetch("https://api.kucoin.com/api/v1/market/orderbook/level1?symbol=BTC-USDT", { cache: "no-store" });
    const j = await r.json();
    if (j && j.data && j.data.price) return parseFloat(j.data.price);
  } catch (e) {}

  return null;
}

async function fetchFx() {
  const rates = {};
  try {
    const r = await fetch("https://www.cbr-xml-daily.ru/daily_json.js");
    const j = await r.json();
    if (j && j.Valute) {
      if (j.Valute.USD) rates.USD = j.Valute.USD.Value;
      if (j.Valute.EUR) rates.EUR = j.Valute.EUR.Value;
      if (j.Valute.CNY) rates.CNY = j.Valute.CNY.Value;
    }
  } catch (e) { /* ЦБ недоступен */ }

  try {
    const btcUsd = await fetchBtcUsd();
    if (btcUsd) {
      const usdRate = rates.USD || 90; // если курс доллара ещё не загрузился, используем ориентир
      rates.BTC = btcUsd * usdRate; // переводим в рубли
    }
  } catch (e) {}

  return Object.keys(rates).length ? rates : null;
}


async function loadFx(force) {
  let cache = null;
  try { cache = JSON.parse(localStorage.getItem(FX_CACHE_KEY)); } catch (e) {}

  if (cache && cache.rates && !force && (Date.now() - cache.ts < FX_TTL)) {
    let prev = null;
    try { prev = JSON.parse(localStorage.getItem(FX_PREV_KEY)); } catch (e) {}
    renderFx(cache.rates, prev);
    setFxStamp(cache.ts);
    return;
  }

  const rates = await fetchFx();
  if (rates) {
    let prev = null;
    try { prev = JSON.parse(localStorage.getItem(FX_PREV_KEY)); } catch (e) {}
    renderFx(rates, prev);
    localStorage.setItem(FX_PREV_KEY, JSON.stringify(cache ? cache.rates : rates));
    localStorage.setItem(FX_CACHE_KEY, JSON.stringify({ ts: Date.now(), rates: rates }));
    setFxStamp(null);
  } else if (cache && cache.rates) {
    renderFx(cache.rates, null);
    setFxStamp(cache.ts);
  } else {
    renderFx(null, null);
  }
}

loadFx(false);
setInterval(() => loadFx(true), FX_TTL);

document.addEventListener("click", ev => {
  const btn = ev.target.closest("[data-action='fx-refresh']");
  if (!btn) return;
  btn.classList.add("spin");
  setTimeout(() => btn.classList.remove("spin"), 650);
  loadFx(true);
});

// ===== ЖИВЫЕ СЧЁТЧИКИ НА КНОПКАХ НАВИГАЦИИ =====
async function loadNavBadges() {
  try {
    const s = await api("/api/dashboard/stats");
    if (s.ok && s.data) {
      const over = s.data.Overdue || 0;
      if (over > 0) {
        const calBadge = document.getElementById("nb-calendar");
        const jBadge = document.getElementById("nb-journal");
        if (calBadge) { calBadge.textContent = over; calBadge.classList.add("show"); }
        if (jBadge) { jBadge.textContent = over; jBadge.classList.add("show"); }
      }
    }
    const inv = await api("/api/invoices/");
    if (inv.ok && inv.data) {
      const unpaid = inv.data.filter(i => i.Status !== "Оплачен" && i.Status !== "Отменён" && (i.Debt || 0) > 0).length;
      const iBadge = document.getElementById("nb-invoices");
      if (unpaid > 0 && iBadge) { iBadge.textContent = unpaid; iBadge.classList.add("show", "amber"); }
    }
  } catch (e) {}
}
loadNavBadges();


// ===== НАВИГАЦИЯ: индикаторы горизонтального скролла =====
(function () {
  const sc = document.querySelector(".nx-navwrap");
  const nav = sc && sc.querySelector(".nx-nav");
  if (!sc || !nav) return;
  const upd = () => {
    sc.classList.toggle("can-left", nav.scrollLeft > 4);
    sc.classList.toggle("can-right", nav.scrollLeft < nav.scrollWidth - nav.clientWidth - 4);
  };
  nav.addEventListener("scroll", upd, { passive: true });
  window.addEventListener("resize", upd);
  // колесо мыши вниз/вверх -> горизонтальный скролл полосы
  nav.addEventListener("wheel", e => {
    if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
      nav.scrollLeft += e.deltaY;
      e.preventDefault();
    }
  }, { passive: false });
  upd();
  setTimeout(upd, 300);
})();



// ===== NX: дата в шапке (полные названия месяцев) =====
(function () {
  const d = new Date();
  const mf = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"];
  const wf = ["воскресенье","понедельник","вторник","среда","четверг","пятница","суббота"];
  const elx = document.getElementById("nx-date");
  if (!elx) return;
  elx.innerHTML =
    '<span class="nx-date-d"><span class="nx-dd">' + d.getDate() + '</span> ' + mf[d.getMonth()] + '</span>' +
    '<span class="nx-date-w">' + wf[d.getDay()] + ' · ' + d.getFullYear() + '</span>';
})();


// ===== ПОГОДА (Open-Meteo, без ключа, координаты из ссылки Ventusky) =====
const WX_LAT = 58.293, WX_LON = 57.883;
const WX_CACHE = "wx_cache_v1";
const WX_TTL = 2 * 60 * 60 * 1000; // 2 часа

function wxIcon(code) {
  const m = {
    0: ["☀", "Ясно"], 1: ["🌤", "Малооблачно"], 2: ["⛅", "Переменная облачность"], 3: ["☁", "Пасмурно"],
    45: ["🌫", "Туман"], 48: ["🌫", "Изморозь"],
    51: ["🌦", "Морось"], 53: ["🌦", "Морось"], 55: ["🌦", "Морось"], 56: ["🌧", "Ледяная морось"], 57: ["🌧", "Ледяная морось"],
    61: ["🌧", "Дождь"], 63: ["🌧", "Дождь"], 65: ["🌧", "Сильный дождь"], 66: ["🌧", "Ледяной дождь"], 67: ["🌧", "Ледяной дождь"],
    71: ["❄", "Снег"], 73: ["❄", "Снег"], 75: ["❄", "Сильный снег"], 77: ["❄", "Снежные зёрна"],
    80: ["🌧", "Ливень"], 81: ["🌧", "Ливень"], 82: ["🌧", "Сильный ливень"],
    85: ["🌨", "Снегопад"], 86: ["🌨", "Снегопад"],
    95: ["⛈", "Гроза"], 96: ["⛈", "Гроза с градом"], 99: ["⛈", "Сильная гроза"]
  };
  return m[code] || ["🌡", "—"];
}
function fmtT(n) { const v = Math.round(n); return (v > 0 ? "+" : "") + v + "°"; }

function renderWx(c) {
  const host = document.getElementById("wxWidget");
  if (!host) return;
  if (!c) { host.innerHTML = '<span class="fx-loading">нет данных о погоде</span>'; return; }
  const ic = wxIcon(c.weather_code);
  host.innerHTML =
    '<div class="wx-main"><div class="wx-ico">' + ic[0] + '</div><div><div class="wx-temp">' + fmtT(c.temperature_2m) + '</div><div class="wx-desc">' + ic[1] + '</div></div></div>' +
    '<div class="wx-row"><span>Ощущается</span><b>' + fmtT(c.apparent_temperature) + '</b></div>' +
    '<div class="wx-row"><span>💨 Ветер</span><b>' + Math.round(c.wind_speed_10m) + ' м/с</b></div>' +
    '<div class="wx-row"><span>💧 Осадки</span><b>' + (c.precipitation || 0) + ' мм</b></div>' +
    '<div class="wx-geo">58.29°N · 57.88°E</div>';
}

async function fetchWx() {
  try {
    const r = await fetch("https://api.open-meteo.com/v1/forecast?latitude=" + WX_LAT + "&longitude=" + WX_LON + "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,precipitation&wind_speed_unit=ms&timezone=auto");
    const j = await r.json();
    return (j && j.current) ? j.current : null;
  } catch (e) { return null; }
}

async function loadWx(force) {
  let cache = null;
  try { cache = JSON.parse(localStorage.getItem(WX_CACHE)); } catch (e) {}
  if (cache && cache.c && !force && (Date.now() - cache.ts < WX_TTL)) { renderWx(cache.c); return; }
  const c = await fetchWx();
  if (c) { renderWx(c); localStorage.setItem(WX_CACHE, JSON.stringify({ ts: Date.now(), c: c })); }
  else if (cache && cache.c) { renderWx(cache.c); }
  else renderWx(null);
}

loadWx(false);
setInterval(() => loadWx(true), WX_TTL);

document.addEventListener("click", ev => {
  const b = ev.target.closest("[data-action='wx-refresh']");
  if (!b) return;
  b.classList.add("spin");
  setTimeout(() => b.classList.remove("spin"), 650);
  loadWx(true);
});


// ===== nav-scroll handler (стрелки прокрутки меню в шапке) =====
document.addEventListener("click", ev => {
  const b = ev.target.closest("[data-action='nav-scroll']");
  if (!b) return;
  const nav = document.querySelector(".nx-nav");
  if (!nav) return;
  const step = Math.round(nav.clientWidth * 0.8);
  nav.scrollBy({ left: b.dataset.dir === "left" ? -step : step, behavior: "smooth" });
});


// ===== КОЛОКОЛЬЧИК: НАПОМИНАНИЯ ЗА 7 ДНЕЙ С МЯГКИМ ЗВУКОМ И СКРЫТИЕМ ПРОЧИТАННЫХ =====
let bellSoundEnabled = localStorage.getItem("bell_sound_enabled") !== "false";
let lastNotifiedIds = new Set();
try {
  const stored = JSON.parse(sessionStorage.getItem("bell_seen_ids") || "[]");
  lastNotifiedIds = new Set(stored);
} catch (e) {}

// Список скрытых пользователем ID напоминаний
let bellDismissedIds = new Set();
try {
  const storedDismissed = JSON.parse(localStorage.getItem("bell_dismissed_ids") || "[]");
  bellDismissedIds = new Set(storedDismissed);
} catch (e) {}

function dismissBellReminder(id) {
  if (!id) return;
  bellDismissedIds.add(id);
  localStorage.setItem("bell_dismissed_ids", JSON.stringify(Array.from(bellDismissedIds)));
  loadReminders();
}

function dismissAllBellReminders(ids) {
  if (!ids || !ids.length) return;
  ids.forEach(id => bellDismissedIds.add(id));
  localStorage.setItem("bell_dismissed_ids", JSON.stringify(Array.from(bellDismissedIds)));
  loadReminders();
}

function playSoftChime() {
  if (!bellSoundEnabled) return;
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
      if (ctx.state === "suspended") return; // Браузер требует взаимодействия пользователя для воспроизведения
    }

    const now = ctx.currentTime;
    // Мягкий гармоничный двухтональный колокольчик (E5 -> B5, 659.25Hz и 987.77Hz)
    const tones = [
      { freq: 659.25, time: 0.0, dur: 0.8 },
      { freq: 987.77, time: 0.12, dur: 1.1 }
    ];

    tones.forEach(t => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(t.freq, now + t.time);

      gain.gain.setValueAtTime(0.0001, now + t.time);
      gain.gain.exponentialRampToValueAtTime(0.15, now + t.time + 0.04);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + t.time + t.dur);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now + t.time);
      osc.stop(now + t.time + t.dur);
    });
  } catch (err) {
    // AudioContext недоступен
  }
}

let lastActiveBellItems = [];

async function loadReminders() {
  try {
    const res = await api("/api/dashboard/reminders");
    if (!res.ok) return;
    const rawItems = res.data || [];

    // Фильтруем те, которые пользователь уже скрыл/просмотрел
    const items = rawItems.filter(item => !bellDismissedIds.has(item.ID));
    lastActiveBellItems = items;

    const badge = document.getElementById("bellBadge");
    const list = document.getElementById("bellList");
    const markAllBtn = document.getElementById("bellMarkAllReadBtn");

    if (badge) {
      if (items.length > 0) {
        badge.textContent = items.length;
        badge.classList.add("show");
      } else {
        badge.textContent = "";
        badge.classList.remove("show");
      }
    }

    if (markAllBtn) {
      markAllBtn.style.display = items.length > 0 ? "inline-block" : "none";
    }

    if (list) {
      if (!items.length) {
        list.innerHTML = '<div class="empty" style="padding:16px 8px;font-size:12px;">✅ Все напоминания просмотрены</div>';
      } else {
        list.innerHTML = items.map(item => `
          <div class="bell-item" data-action="bell-open" data-id="${esc(item.ID)}" data-date="${esc(item.PlannedDate)}">
            <div class="bell-item-head">
              <span class="bell-item-obj">${esc(item.ObjectName)}</span>
              <div class="bell-item-actions">
                <span class="bell-item-tag">${item.DaysLeft === 0 ? "СЕГОДНЯ" : "через " + item.DaysLeft + " дн."}</span>
                <button type="button" class="bell-item-dismiss" data-action="bell-dismiss" data-id="${esc(item.ID)}" title="Скрыть это напоминание">✕</button>
              </div>
            </div>
            <div class="bell-item-work">${esc(item.WorkCode)} · ${esc(item.WorkName)}</div>
            ${item.InspectorMessage ? `<div class="bell-item-inspector">🛡️ <i>${esc(item.InspectorMessage)}</i></div>` : ""}
            <div class="bell-item-date">
              <span>📅 План: <b>${fmtDate(item.PlannedDate)}</b></span>
              <span>🔔 С ${fmtDate(item.RemindDate)}</span>
            </div>
          </div>
        `).join("");
      }
    }

    // Проверка новых напоминаний для воспроизведения мягкого звука
    const currentIds = items.map(x => x.ID);
    const hasNew = currentIds.some(id => !lastNotifiedIds.has(id));
    if (hasNew && items.length > 0) {
      playSoftChime();
      currentIds.forEach(id => lastNotifiedIds.add(id));
      sessionStorage.setItem("bell_seen_ids", JSON.stringify(Array.from(lastNotifiedIds)));
    }
  } catch (e) {}
}

document.addEventListener("click", ev => {
  // Нажатие на само напоминание: скрываем его и открываем карточку даты выполнения
  const bellItem = ev.target.closest("[data-action='bell-open']");
  if (bellItem && !ev.target.closest("[data-action='bell-dismiss']")) {
    const id = bellItem.dataset.id;
    const pDate = bellItem.dataset.date;
    if (id) dismissBellReminder(id);
    const dd = document.getElementById("bellDropdown");
    if (dd) dd.classList.add("hidden");
    if (pDate) openDay(pDate.slice(0, 10));
    return;
  }

  // Нажатие кнопки "Скрыть напоминание" (крестик на отдельном напоминании)
  const dismissBtn = ev.target.closest("[data-action='bell-dismiss']");
  if (dismissBtn) {
    ev.stopPropagation();
    const id = dismissBtn.dataset.id;
    dismissBellReminder(id);
    return;
  }

  // Нажатие кнопки "Прочитано всё"
  const markAllBtn = ev.target.closest("#bellMarkAllReadBtn");
  if (markAllBtn) {
    ev.stopPropagation();
    dismissAllBellReminders(lastActiveBellItems.map(x => x.ID));
    return;
  }

  const bellBtn = ev.target.closest("#bellBtn");
  const dd = document.getElementById("bellDropdown");
  if (bellBtn && dd) {
    dd.classList.toggle("hidden");
    loadReminders();
    return;
  }

  const soundBtn = ev.target.closest("#soundToggleBtn");
  if (soundBtn) {
    bellSoundEnabled = !bellSoundEnabled;
    localStorage.setItem("bell_sound_enabled", String(bellSoundEnabled));
    soundBtn.textContent = bellSoundEnabled ? "🔊" : "🔇";
    soundBtn.title = bellSoundEnabled ? "Звук включен" : "Звук выключен";
    if (bellSoundEnabled) playSoftChime();
    notice(bellSoundEnabled ? "Звук напоминаний включён" : "Звук напоминаний выключен");
    return;
  }

  // Закрытие при клике вне колокольчика
  if (dd && !dd.classList.contains("hidden") && !ev.target.closest(".nx-bell-wrap")) {
    dd.classList.add("hidden");
  }
});

// Инициализация звуковой кнопки
const sndBtn = document.getElementById("soundToggleBtn");
if (sndBtn) {
  sndBtn.textContent = bellSoundEnabled ? "🔊" : "🔇";
  sndBtn.title = bellSoundEnabled ? "Звук включен" : "Звук выключен";
}

loadReminders();
setInterval(loadReminders, 60000); // Проверка каждую минуту

// ===== ПЕРЕКЛЮЧЕНИЕ БОКОВОЙ ПАНЕЛИ ПО КЛИКУ НА ДАТУ =====
(function initSideToggle() {
  const brandBtn = document.getElementById("nxBrandToggle");
  const body = document.querySelector(".nx-body");
  if (!brandBtn || !body) return;

  // По умолчанию панель свёрнута (false только если пользователь явно её открыл и сохранил 'false')
  const isCollapsed = localStorage.getItem("side_panel_collapsed") !== "false";
  body.classList.toggle("side-collapsed", isCollapsed);
  brandBtn.classList.toggle("collapsed", isCollapsed);

  brandBtn.addEventListener("click", () => {
    const collapsed = body.classList.toggle("side-collapsed");
    brandBtn.classList.toggle("collapsed", collapsed);
    localStorage.setItem("side_panel_collapsed", String(collapsed));
  });


  brandBtn.addEventListener("keydown", e => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      brandBtn.click();
    }
  });
})();

