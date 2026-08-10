/* ==========================================================================
   Live Video Streamer — front-end logic
   Talks to Python exclusively through window.pywebview.api (WebView API).
   ========================================================================== */

const INITIAL_URL = __INITIAL_URL__;

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------- element references */

const urlInput = $("url");
const playBtn = $("playBtn");
const stopBtn = $("stopBtn");
const stopBtn2 = $("stopBtn2");
const pauseBtn = $("pauseBtn");
const iconPlay = $("iconPlay");
const iconPause = $("iconPause");
const langSwitch = $("langSwitch");

const player = $("player");
const video = $("video");
const placeholder = $("placeholder");
const vlcCard = $("vlcCard");

const statusChip = $("statusChip");
const statusDot = $("statusDot");
const statusText = $("statusText");
const metricsChip = $("metricsChip");
const speedLabel = $("speedLabel");
const downloadLabel = $("downloadLabel");

const controlBar = $("controlBar");
const seekTrack = $("seekTrack");
const seekBuffer = $("seekBuffer");
const seekPlayed = $("seekPlayed");
const seekThumb = $("seekThumb");
const seekTooltip = $("seekTooltip");
const timeLabel = $("timeLabel");
const cbStatus = $("cbStatus");

const volumeWrap = $("volumeWrap");
const volTrack = $("volTrack");
const volFill = $("volFill");
const volThumb = $("volThumb");
const muteBtn = $("muteBtn");
const iconVol = $("iconVol");
const iconMute = $("iconMute");

const fsBtn = $("fsBtn");
const iconFs = $("iconFs");
const iconFsx = $("iconFsx");

const logPanel = $("logPanel");
const clearLogBtn = $("clearLogBtn");
const toggleLogBtn = $("toggleLogBtn");
const logCard = $("logCard");

const titlebar = $("titlebar");
const minBtn = $("minBtn");
const maxBtn = $("maxBtn");
const closeBtn = $("closeBtn");
const iconMax = $("iconMax");
const iconRestore = $("iconRestore");

/* ------------------------------------------------------ pywebview api bridge */

let api = null;
let apiReady = false;
const apiWaiters = [];

function resolveApi() {
  const pv = window.pywebview;
  api = (pv && pv.api) || null;
  if (api && !apiReady) {
    apiReady = true;
    apiWaiters.splice(0).forEach((waiter) => waiter(api));
  }
  return api;
}

function whenApiReady(timeoutMs) {
  return new Promise((resolve) => {
    if (apiReady) return resolve(api);
    const timer = setTimeout(() => {
      const i = apiWaiters.indexOf(resolve);
      if (i >= 0) apiWaiters.splice(i, 1);
      resolve(resolveApi());
    }, timeoutMs || 10000);
    apiWaiters.push((a) => {
      clearTimeout(timer);
      resolve(a);
    });
  });
}

window.addEventListener("pywebviewready", () => {
  resolveApi();
  if (api) api.set_language(currentLang);
});
resolveApi();

/* ---------------------------------------------------------------- i18n */

const I18N = {
  en: {
    "app.name": "Live Video Streamer",
    "app.title": "Live Video Streamer",
    "app.subtitle": "Stream without downloading the whole file",
    "url.placeholder": "Enter a direct video link (http / https)...",
    "btn.play": "Play",
    "btn.stop": "Stop",
    "placeholder.title": "Ready to play",
    "placeholder.sub": "Enter a direct link and press Play",
    "vlc.title": "Playing in a separate VLC window",
    "vlc.sub": "This format is not supported by the browser; the picture opens in a separate window",
    "tb.minimize": "Minimize",
    "tb.maximize": "Maximize",
    "tb.restore": "Restore",
    "tb.close": "Close",
    "cb.pause": "Play / Pause (Space)",
    "cb.stop": "Stop",
    "cb.mute": "Mute (M)",
    "cb.fullscreen": "Fullscreen (F)",
    "log.title": "Events",
    "log.clear": "Clear",
    "log.toggleTitle": "Show / Hide",
    status: {
      idle: "Ready",
      probing: "Checking link",
      connecting: "Connecting",
      buffering: "Buffering",
      playing: "Playing",
      paused: "Paused",
      stopped: "Playback stopped",
      error: "Error",
    },
    statusShort: {
      idle: "Ready",
      probing: "Connecting...",
      connecting: "Connecting",
      buffering: "Buffering",
      playing: "Playing",
      paused: "Paused",
      stopped: "Stopped",
      error: "Error",
    },
    msg: {
      enterLink: "Please enter a video link.",
      noApi: "WebView API is not available; please restart the app.",
      streamReady: "Stream ready",
      failedToStart: "Could not start playback.",
      clickToPlay: "Click the play button to start.",
      vlcStart: "Playing in a separate VLC window.",
      vlcFallback: "Format not supported by the browser; trying VLC...",
      vlcHanded: "Playback handed over to a separate VLC window.",
      vlcErr: "Failed to hand playback to VLC",
      bridgeErr: "Backend communication error",
      stopped: "Playback stopped.",
    },
  },
  fa: {
    "app.name": "پخش آنلاین ویدیو",
    "app.title": "استریم زنده ویدیو",
    "app.subtitle": "پخش آنلاین بدون دانلود کامل فایل",
    "url.placeholder": "لینک مستقیم ویدیو (http / https) را وارد کنید...",
    "btn.play": "پخش",
    "btn.stop": "توقف",
    "placeholder.title": "آماده پخش",
    "placeholder.sub": "لینک مستقیم را وارد کنید و «پخش» را بزنید",
    "vlc.title": "پخش در پنجره VLC",
    "vlc.sub": "فرمت توسط مرورگر پشتیبانی نمی‌شود؛ تصویر در پنجره جداگانه نمایش داده می‌شود",
    "tb.minimize": "کوچک‌کردن",
    "tb.maximize": "بزرگ‌نمایی",
    "tb.restore": "بازگردانی",
    "tb.close": "بستن",
    "cb.pause": "پخش / مکث (Space)",
    "cb.stop": "توقف",
    "cb.mute": "بی‌صدا (M)",
    "cb.fullscreen": "تمام‌صفحه (F)",
    "log.title": "رویدادها",
    "log.clear": "پاک‌کردن",
    "log.toggleTitle": "نمایش / مخفی‌کردن",
    status: {
      idle: "آماده",
      probing: "در حال بررسی لینک",
      connecting: "در حال اتصال",
      buffering: "در حال بافرینگ",
      playing: "در حال پخش",
      paused: "مکث",
      stopped: "پخش متوقف شد",
      error: "خطا",
    },
    statusShort: {
      idle: "آماده",
      probing: "اتصال...",
      connecting: "اتصال",
      buffering: "بافرینگ",
      playing: "در حال پخش",
      paused: "مکث",
      stopped: "متوقف",
      error: "خطا",
    },
    msg: {
      enterLink: "لطفا لینک ویدیو را وارد کنید.",
      noApi: "WebView API در دسترس نیست؛ برنامه را دوباره اجرا کنید.",
      streamReady: "جریان آماده شد",
      failedToStart: "شروع پخش ممکن نشد.",
      clickToPlay: "برای شروع پخش روی دکمه پخش کلیک کنید.",
      vlcStart: "پخش در پنجره جداگانه VLC آغاز می‌شود.",
      vlcFallback: "فرمت توسط مرورگر پشتیبانی نشد؛ تلاش با VLC...",
      vlcHanded: "پخش به پنجره جداگانه VLC منتقل شد.",
      vlcErr: "خطا در واگذاری به VLC",
      bridgeErr: "خطای ارتباط با Backend",
      stopped: "پخش متوقف شد.",
    },
  },
};

let currentLang = "en";
try {
  currentLang = localStorage.getItem("lang") || "en";
} catch (e) { /* storage unavailable */ }
if (!I18N[currentLang]) currentLang = "en";

function t(key) {
  const dict = I18N[currentLang] || I18N.en;
  return dict[key] !== undefined ? dict[key] : (I18N.en[key] !== undefined ? I18N.en[key] : key);
}

let STATUS_LABELS = I18N.en.status;
let STATUS_SHORT = I18N.en.statusShort;

function applyLanguage() {
  const dict = I18N[currentLang] || I18N.en;
  document.documentElement.lang = currentLang;
  document.documentElement.dir = currentLang === "fa" ? "rtl" : "ltr";
  langSwitch.dataset.lang = currentLang;

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = dict[el.dataset.i18n] || el.textContent;
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.title = dict[el.dataset.i18nTitle] || el.title;
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = dict[el.dataset.i18nPlaceholder] || el.placeholder;
  });

  STATUS_LABELS = dict.status || I18N.en.status;
  STATUS_SHORT = dict.statusShort || I18N.en.statusShort;
  maxBtn.title = snapshotMaximized ? t("tb.restore") : t("tb.maximize");

  if (lastStatus) setStatus(lastStatus);
}

function setLanguage(lang) {
  const next = lang === "fa" ? "fa" : "en";
  if (next === currentLang) return;
  currentLang = next;
  try {
    localStorage.setItem("lang", currentLang);
  } catch (e) { /* ignore */ }
  applyLanguage();
  logPanel.innerHTML = "";
  if (api) api.set_language(currentLang);
}

/* -------------------------------------------------------------------- state */

let mode = null; // "html5" | "vlc"
let active = false;
let seeking = false;
let seekDrag = false;
let lastStatus = null;
let snapshotMaximized = false;
let pendingRatio = null;
let durationMs = 0;
let posMs = 0;
let playing = false;
let volumeLevel = 100;
let fsOptimistic = false;
let lastWinFs = false;
let lastSnap = null;

/* ------------------------------------------------------------------ helpers */

function fmtBytes(size) {
  size = Math.max(0, Number(size) || 0);
  if (size < 1024) return size + " B";
  const units = ["KiB", "MiB", "GiB", "TiB"];
  let v = size;
  for (const u of units) {
    v /= 1024;
    if (v < 1024) return v.toFixed(1) + " " + u;
  }
  return v.toFixed(1) + " PiB";
}

function fmtSpeed(bps) {
  bps = Math.max(0, Number(bps) || 0);
  if (bps < 1024) return bps.toFixed(0) + " B/s";
  const units = ["KB/s", "MB/s", "GB/s"];
  let v = bps;
  for (const u of units) {
    v /= 1024;
    if (v < 1024) return v.toFixed(1) + " " + u;
  }
  return v.toFixed(1) + " TB/s";
}

function fmtTime(ms) {
  ms = Math.max(0, Number(ms) || 0);
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h ? h + ":" + String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0")
           : m + ":" + String(s).padStart(2, "0");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function log(level, message) {
  const line = document.createElement("div");
  line.className = "log-line " + (level || "info");
  const now = new Date();
  const ts = [now.getHours(), now.getMinutes(), now.getSeconds()]
    .map((n) => String(n).padStart(2, "0"))
    .join(":");
  const icon = level === "error" ? "✕" : level === "warning" ? "!" : "·";
  line.innerHTML =
    '<span class="log-ts">' + ts + '</span><span class="log-ic">' + icon +
    '</span><span class="log-msg">' + escapeHtml(message) + "</span>";
  logPanel.appendChild(line);
  while (logPanel.childElementCount > 300) logPanel.removeChild(logPanel.firstChild);
  logPanel.scrollTop = logPanel.scrollHeight;
}

/* --------------------------------------------------------------- status UI */

function setStatus(status) {
  lastStatus = status;
  statusDot.className = "dot " + (status || "idle");
  statusText.textContent = STATUS_LABELS[status] || status;
  cbStatus.textContent = STATUS_SHORT[status] || status;
  cbStatus.className = "cb-status st-" + (status || "idle");
  updateChips();

  if (status === "playing") playing = true;
  else if (status === "paused" || status === "stopped" || status === "idle") playing = false;
  updatePlayPauseIcon();

  pauseBtn.disabled = !(active && mode);
  if (active && status === "stopped") {
    resetUI();
  }
}

// The on-video chips follow the controls: in fullscreen they disappear with
// the controls (nothing on the picture); in windowed mode they stay visible.
function updateChips() {
  const status = lastStatus || "idle";
  const visible = active && !(isFullscreen() && player.classList.contains("controls-hidden"));
  statusChip.classList.toggle("chip-show", visible && status !== "idle" && status !== "stopped");
  metricsChip.classList.toggle("chip-show", visible);
}

function updatePlayPauseIcon() {
  const showPause = playing && active;
  iconPlay.classList.toggle("hidden-svg", showPause);
  iconPause.classList.toggle("hidden-svg", !showPause);
}

function setActive(state) {
  active = state;
  playBtn.disabled = state;
  stopBtn.disabled = !state;
  stopBtn2.disabled = !state;
  if (!state) {
    mode = null;
    playing = false;
    updatePlayPauseIcon();
    pauseBtn.disabled = true;
    setStatus("idle");
    resetSeekUI();
    player.classList.remove("controls-hidden");
    document.body.classList.remove("cursor-hidden");
    document.body.classList.remove("chrome-hidden");
  }
}

function resetSeekUI() {
  durationMs = 0;
  posMs = 0;
  setSeekRatio(0);
  timeLabel.textContent = "0:00 / 0:00";
  seekTrack.style.setProperty("--buf", 0);
  seekBuffer.style.setProperty("--buf", 0);
}

function resetUI() {
  placeholder.classList.remove("hidden");
  vlcCard.classList.add("hidden");
  video.classList.remove("visible");
  if (mode === "html5") {
    video.pause();
    video.removeAttribute("src");
    video.load();
  }
  mode = null;
  setActive(false);
}

/* ------------------------------------------------------------- video modes */

function showHtml5() {
  placeholder.classList.add("hidden");
  vlcCard.classList.add("hidden");
  video.classList.add("visible");
}

function showVlc() {
  placeholder.classList.add("hidden");
  video.classList.remove("visible");
  video.removeAttribute("src");
  video.load();
  vlcCard.classList.remove("hidden");
}

/* ------------------------------------------------------------ video events */

video.addEventListener("playing", () => {
  playing = true;
  updatePlayPauseIcon();
  setStatus("playing");
  if (api) api.report_status("playing");
  syncFsVisibility();
});
video.addEventListener("waiting", () => {
  setStatus("buffering");
  if (api) api.report_status("buffering");
  showControls();
});
video.addEventListener("pause", () => {
  setStatus("paused");
  if (api) api.report_status("paused");
  showControls();
});
video.addEventListener("ended", () => {
  if (api) api.report_status("ended");
  stop();
});
video.addEventListener("error", async () => {
  log("error", t("msg.vlcFallback"));

  try {
    const res = await api.play_with_vlc();
    if (res && res.ok) {
      mode = "vlc";
      showVlc();
      setStatus("connecting");
      log("info", t("msg.vlcHanded"));
    } else {
      setStatus("error");
    }
  } catch (err) {
    setStatus("error");
    log("error", t("msg.vlcErr") + ": " + err);
  }
});
video.addEventListener("durationchange", () => {
  const d = video.duration;
  if (d && isFinite(d)) durationMs = d * 1000;
});
video.addEventListener("progress", updateBuffered);

function updateBuffered() {
  if (mode !== "html5" || !video.buffered || !video.buffered.length) return;
  const d = video.duration;
  if (!d || !isFinite(d)) return;
  const end = video.buffered.end(video.buffered.length - 1);
  seekBuffer.style.setProperty("--buf", Math.max(0, Math.min(1, end / d)));
}

/* ------------------------------------------------------------- seek bar UI */

function setSeekRatio(ratio) {
  ratio = Math.max(0, Math.min(1, ratio || 0));
  seekPlayed.style.setProperty("--played", ratio);
  seekThumb.style.left = ratio * 100 + "%";
}

function updateSeekUI(ratio) {
  ratio = Math.max(0, Math.min(1, ratio || 0));
  setSeekRatio(ratio);
  timeLabel.textContent = fmtTime(ratio * durationMs) + " / " + fmtTime(durationMs);
}

function ratioFromEvent(e) {
  const rect = seekTrack.getBoundingClientRect();
  const r = (e.clientX - rect.left) / rect.width;
  return Math.max(0, Math.min(1, r));
}

function showTooltip(e, ratio) {
  const rect = seekTrack.getBoundingClientRect();
  const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
  seekTooltip.textContent = fmtTime(ratio * durationMs);
  seekTooltip.style.left = x + "px";
  seekTrack.classList.add("tooltip-on");
}

function hideTooltip() {
  seekTrack.classList.remove("tooltip-on");
}

seekTrack.addEventListener("pointerdown", (e) => {
  if (!active) return;
  seeking = true;
  seekDrag = true;
  seekTrack.classList.add("dragging");
  try { seekTrack.setPointerCapture(e.pointerId); } catch (err) { /* synthetic/edge */ }
  const ratio = ratioFromEvent(e);
  pendingRatio = ratio;
  updateSeekUI(ratio);
  showTooltip(e, ratio);
  showControls();
});
seekTrack.addEventListener("pointermove", (e) => {
  if (!seekDrag) return;
  const ratio = ratioFromEvent(e);
  pendingRatio = ratio;
  updateSeekUI(ratio);
  showTooltip(e, ratio);
});
seekTrack.addEventListener("pointerup", (e) => {
  if (!seekDrag) return;
  seekDrag = false;
  seeking = false;
  seekTrack.classList.remove("dragging");
  hideTooltip();
  commitSeek();
  showControls();
});
seekTrack.addEventListener("pointerleave", hideTooltip);

function commitSeek() {
  if (pendingRatio == null) return;
  const ratio = pendingRatio;
  pendingRatio = null;
  if (mode === "html5") {
    const d = video.duration;
    if (d && isFinite(d)) video.currentTime = ratio * d;
  } else if (api) {
    api.seek(ratio);
  }
}

/* ---------------------------------------------------------------- volume UI */

function setVolume(level) {
  volumeLevel = Math.max(0, Math.min(100, Math.round(level)));
  volFill.style.setProperty("--vol", volumeLevel / 100);
  volThumb.style.left = volumeLevel + "%";
  iconVol.classList.toggle("hidden-svg", volumeLevel === 0);
  iconMute.classList.toggle("hidden-svg", volumeLevel !== 0);
  if (mode === "html5") video.volume = volumeLevel / 100;
  else if (api) api.set_volume(volumeLevel);
}

volTrack.addEventListener("pointerdown", (e) => {
  volumeWrap.classList.add("dragging");
  try { volTrack.setPointerCapture(e.pointerId); } catch (err) { /* synthetic/edge */ }
  setVolumeFromEvent(e);
});
volTrack.addEventListener("pointermove", (e) => {
  if (volumeWrap.classList.contains("dragging")) setVolumeFromEvent(e);
});
volTrack.addEventListener("pointerup", (e) => {
  setVolumeFromEvent(e);
  volumeWrap.classList.remove("dragging");
});

function setVolumeFromEvent(e) {
  const rect = volTrack.getBoundingClientRect();
  const r = (e.clientX - rect.left) / rect.width;
  setVolume(Math.max(0, Math.min(1, r)) * 100);
}

/* -------------------------------------------------------------- fullscreen */

function isFullscreen() {
  return fsOptimistic;
}

function toggleFullscreen() {
  fsOptimistic = !fsOptimistic;
  applyFsState(fsOptimistic);
  if (api) {
    api.window_toggle_fullscreen().catch(() => {
      fsOptimistic = !fsOptimistic;
      applyFsState(fsOptimistic);
    });
  }
}

function applyFsState(fs) {
  document.body.classList.toggle("fs-os", fs);
  updateFsIcon();
  syncFsVisibility();
  resetCursorTimer();
}

function updateFsIcon() {
  const fs = isFullscreen();
  iconFs.classList.toggle("hidden-svg", fs);
  iconFsx.classList.toggle("hidden-svg", !fs);
}

/* ------------------------------------------------------ controls visibility */

const AUTO_HIDE_MS = 5000; // windowed: hide after this much inactivity while playing
const FS_ZONE = 110; // fullscreen: bottom strip (px) that reveals the controls
const CURSOR_HIDE_MS = 5000; // cursor hides after this much inactivity (fullscreen)
let hideTimer = null;

function canAutoHide() {
  return active && playing && !seekDrag && !volumeWrap.classList.contains("dragging");
}

function showControls() {
  if (!active) return;
  player.classList.remove("controls-hidden");
  document.body.classList.remove("chrome-hidden");
  updateChips();
}

function hideControls() {
  if (!active) return;
  player.classList.add("controls-hidden");
  if (isFullscreen()) {
    document.body.classList.add("chrome-hidden");
  }
  updateChips();
}

// Windowed mode: reveal on any move, auto-hide after 5s of inactivity.
function scheduleHide() {
  if (!active || isFullscreen()) return;
  showControls();
  clearTimeout(hideTimer);
  hideTimer = setTimeout(() => {
    if (canAutoHide()) hideControls();
  }, AUTO_HIDE_MS);
}

function isInFsZone(e) {
  const rect = player.getBoundingClientRect();
  const fromBottom = rect.bottom - e.clientY;
  return fromBottom >= 0 && fromBottom <= FS_ZONE;
}

function syncFsVisibility() {
  // entering fullscreen: reveal briefly, then hover-only rules take over
  if (isFullscreen()) {
    showControls();
  } else {
    scheduleHide();
  }
}

function onPlayerMove(e) {
  if (!active) return;
  if (isFullscreen()) {
    // cinematic fullscreen: controls stay hidden unless the cursor is over
    // the bottom control strip; leaving hides them at once
    const overControls = isInFsZone(e);
    const dragging = seekDrag || volumeWrap.classList.contains("dragging");
    if (overControls || dragging) {
      showControls();
    } else {
      hideControls();
    }
  } else {
    scheduleHide();
  }
}

player.addEventListener("mousemove", onPlayerMove);
player.addEventListener("click", (e) => {
  if (e.target.closest(".control-bar") || e.target.closest(".chip")) return;
  if (isFullscreen()) {
    showControls();
  } else {
    scheduleHide();
  }
});
player.addEventListener("mouseleave", () => {
  if (!active) return;
  if (isFullscreen()) {
    const dragging = seekDrag || volumeWrap.classList.contains("dragging");
    if (!dragging) hideControls();
  } else if (canAutoHide()) {
    hideControls();
  }
});
titlebar.addEventListener("pointerenter", () => {
  if (!isFullscreen()) return;
  showControls();
});
titlebar.addEventListener("pointerleave", () => {
  if (!isFullscreen()) return;
  hideControls();
});

// The cursor is independent from the controls: it stays visible while the
// mouse moves and hides after 5s of inactivity (fullscreen only).
let cursorTimer = null;

function resetCursorTimer() {
  document.body.classList.remove("cursor-hidden");
  clearTimeout(cursorTimer);
  cursorTimer = setTimeout(() => {
    if (isFullscreen()) {
      document.body.classList.add("cursor-hidden");
    }
  }, CURSOR_HIDE_MS);
}

document.addEventListener("mousemove", resetCursorTimer);
document.addEventListener("pointermove", resetCursorTimer);
document.addEventListener("touchstart", resetCursorTimer, { passive: true });

/* ------------------------------------------------------------------ ripple */

document.addEventListener("pointerdown", (e) => {
  const btn = e.target.closest(".btn, .cb-btn, .btn-mini, .tb-btn, .lang-opt");
  if (!btn || btn.disabled) return;
  const rect = btn.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height) * 2.2;
  const ripple = document.createElement("span");
  ripple.className = "ripple";
  ripple.style.width = ripple.style.height = size + "px";
  ripple.style.left = e.clientX - rect.left - size / 2 + "px";
  ripple.style.top = e.clientY - rect.top - size / 2 + "px";
  btn.appendChild(ripple);
  ripple.addEventListener("animationend", () => ripple.remove());
});

/* ------------------------------------------------------------- play / stop */

async function play() {
  const url = urlInput.value.trim();
  if (!url) {
    log("warning", t("msg.enterLink"));
    return;
  }
  api = await whenApiReady(8000);
  if (!api) {
    log("error", t("msg.noApi"));
    return;
  }

  resetUI();
  setActive(true);
  setStatus("probing");
  showControls();

  let info;
  try {
    info = await api.play(url);
  } catch (err) {
    log("error", t("msg.bridgeErr") + ": " + err);
    setStatus("error");
    return;
  }

  if (!info || !info.ok) {
    log("error", (info && info.error) || t("msg.failedToStart"));
    setStatus("error");
    setActive(false);
    return;
  }

  log("info", t("msg.streamReady") + ": " + (info.filename || url));
  mode = info.mode;

  if (mode === "html5") {
    showHtml5();
    setStatus("connecting");
    video.src = info.url;
    const p = video.play();
    if (p && p.catch) {
      p.catch(() => log("warning", t("msg.clickToPlay")));
    }
  } else {
    showVlc();
    setStatus("connecting");
    log("info", t("msg.vlcStart"));
  }
}

function stop() {
  if (mode === "html5") {
    video.pause();
    video.removeAttribute("src");
    video.load();
  }
  if (api) api.stop().catch(() => {});
  log("info", t("msg.stopped"));
  resetUI();
}

function togglePlayPause() {
  if (!active || !mode) return;
  if (mode === "html5") {
    if (video.paused) {
      video.play().catch(() => {});
      playing = true;
      updatePlayPauseIcon();
      api.report_status("playing");
    } else {
      video.pause();
    }
  } else if (api) {
    api.toggle_pause();
  }
}

function seekRelative(sec) {
  if (!active || !mode) return;
  let target = posMs + sec * 1000;
  if (mode === "html5") {
    const d = video.duration;
    if (d && isFinite(d)) target = Math.max(0, Math.min(d * 1000, target));
    video.currentTime = target / 1000;
  } else if (api) {
    const total = durationMs || 1;
    api.seek(Math.max(0, Math.min(1, target / total)));
  }
}

/* ----------------------------------------------------------------- polling */

let lastTimeStr = "";
let lastPosReport = 0;

function updateTimeLabel(pos) {
  const str = fmtTime(pos) + " / " + fmtTime(durationMs);
  if (str !== lastTimeStr) {
    lastTimeStr = str;
    timeLabel.textContent = str;
  }
}

function frame() {
  if (mode === "html5" && !seeking) {
    const d = video.duration;
    if (d && isFinite(d)) {
      durationMs = d * 1000;
      posMs = video.currentTime * 1000;
      setSeekRatio(posMs / durationMs);
      updateTimeLabel(posMs);
      // keep the backend's playback position fresh so the parallel
      // read-ahead downloader knows how far ahead it may fetch
      const now = performance.now();
      if (api && now - lastPosReport > 1000) {
        lastPosReport = now;
        api.report_position(Math.round(posMs), Math.round(durationMs));
      }
    }
  }
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

async function pollStats() {
  if (!resolveApi()) return;
  let snap;
  try {
    snap = await api.snapshot();
  } catch (err) {
    return;
  }
  lastSnap = snap;

  // window state (OS-level fullscreen / maximize) reconciliation
  if (typeof snap.win_fullscreen === "boolean" && snap.win_fullscreen !== lastWinFs) {
    lastWinFs = snap.win_fullscreen;
    fsOptimistic = snap.win_fullscreen;
    document.body.classList.toggle("fs-os", fsOptimistic);
    updateFsIcon();
    syncFsVisibility();
    resetCursorTimer();
  }
  if (typeof snap.win_maximized === "boolean") {
    snapshotMaximized = snap.win_maximized;
    const mx = snap.win_maximized;
    iconMax.classList.toggle("hidden-svg", mx);
    iconRestore.classList.toggle("hidden-svg", !mx);
    maxBtn.title = mx ? t("tb.restore") : t("tb.maximize");
  }

  if (mode === "vlc") {
    setStatus(snap.status);
    durationMs = snap.length_ms || durationMs;
    posMs = snap.position_ms;
    if (durationMs > 0) {
      setSeekRatio(posMs / durationMs);
      updateTimeLabel(posMs);
    }
  }

  if (snap.status === "stopped" && active) resetUI();

  speedLabel.textContent = fmtSpeed(snap.speed_bps);
  downloadLabel.textContent = snap.bytes_total
    ? fmtBytes(snap.bytes_fetched) + " / " + fmtBytes(snap.bytes_total)
    : fmtBytes(snap.bytes_fetched);

  if (mode === "vlc" && snap.bytes_total) {
    seekBuffer.style.setProperty("--buf", Math.max(0, Math.min(1, snap.cache_bytes / snap.bytes_total)));
  }
}

async function pollLogs() {
  if (!resolveApi()) return;
  let items;
  try {
    items = await api.drain_logs();
  } catch (err) {
    return;
  }
  if (items && items.length) {
    for (const item of items) log(item.level, item.message);
  }
}

/* --------------------------------------------------------------- keyboard */

document.addEventListener("keydown", (e) => {
  if (e.target) {
    const tag = e.target.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "BUTTON") return;
  }
  switch (e.key) {
    case " ":
    case "Spacebar":
      e.preventDefault();
      togglePlayPause();
      break;
    case "ArrowRight":
      e.preventDefault();
      seekRelative(5);
      break;
    case "ArrowLeft":
      e.preventDefault();
      seekRelative(-5);
      break;
    case "ArrowUp":
      e.preventDefault();
      setVolume(volumeLevel + 5);
      break;
    case "ArrowDown":
      e.preventDefault();
      setVolume(volumeLevel - 5);
      break;
    case "f":
    case "F":
      toggleFullscreen();
      break;
    case "m":
    case "M":
      setVolume(volumeLevel === 0 ? 100 : 0);
      break;
    case "Escape":
      if (isFullscreen()) toggleFullscreen();
      break;
  }
});

/* ------------------------------------------------------------------ wiring */

/* Custom title bar */
let titleDrag = false;
let dragPending = null;

titlebar.addEventListener("pointerdown", (e) => {
  if (e.button !== 0) return;
  if (e.target.closest(".tb-btn") || e.target.closest(".lang-switch")) return;
  if (!api) return;
  titleDrag = true;
  dragPending = null;
  try {
    titlebar.setPointerCapture(e.pointerId);
  } catch (err) { /* synthetic / edge */ }
  e.preventDefault();
  api.window_start_drag();
});
titlebar.addEventListener("pointermove", (e) => {
  if (!titleDrag) return;
  dragPending = { x: e.screenX, y: e.screenY };
});
titlebar.addEventListener("pointerup", (e) => {
  if (!titleDrag) return;
  titleDrag = false;
  dragPending = null;
  try {
    titlebar.releasePointerCapture(e.pointerId);
  } catch (err) { /* synthetic / edge */ }
  if (api) api.window_end_drag();
});
titlebar.addEventListener("pointercancel", (e) => {
  if (!titleDrag) return;
  titleDrag = false;
  dragPending = null;
  if (api) api.window_end_drag();
});

// Flush at most one window move per animation frame while dragging.
function dragFlushLoop() {
  if (titleDrag && dragPending && api) {
    api.window_drag_to(dragPending.x, dragPending.y);
    dragPending = null;
  }
  requestAnimationFrame(dragFlushLoop);
}
requestAnimationFrame(dragFlushLoop);

titlebar.addEventListener("dblclick", (e) => {
  if (e.target.closest(".tb-btn") || e.target.closest(".lang-switch")) return;
  if (api) api.window_toggle_maximize();
});
minBtn.addEventListener("click", () => api && api.window_minimize());
maxBtn.addEventListener("click", () => api && api.window_toggle_maximize());
closeBtn.addEventListener("click", () => api && api.window_close());

/* Language switch */
langSwitch.addEventListener("click", (e) => {
  const opt = e.target.closest(".lang-opt");
  if (!opt) return;
  setLanguage(opt.dataset.lang);
});

playBtn.addEventListener("click", play);
stopBtn.addEventListener("click", stop);
stopBtn2.addEventListener("click", stop);
pauseBtn.addEventListener("click", togglePlayPause);
muteBtn.addEventListener("click", () => setVolume(volumeLevel === 0 ? 100 : 0));
fsBtn.addEventListener("click", toggleFullscreen);
clearLogBtn.addEventListener("click", () => { logPanel.innerHTML = ""; });
toggleLogBtn.addEventListener("click", () => {
  logCard.classList.toggle("collapsed");
  toggleLogBtn.textContent = logCard.classList.contains("collapsed") ? "▲" : "▼";
});

urlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") play();
});

player.addEventListener("dblclick", () => {
  if (active) toggleFullscreen();
});

/* ------------------------------------------------------------------- init */

setVolume(100);
resetUI();
applyLanguage();

if (INITIAL_URL) {
  urlInput.value = INITIAL_URL;
  setTimeout(() => {
    whenApiReady(8000).then((ready) => {
      if (ready) play();
      else log("error", t("msg.noApi"));
    });
  }, 300);
}

setInterval(pollStats, 250);
setInterval(pollLogs, 600);
