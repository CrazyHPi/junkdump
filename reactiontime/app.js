"use strict";

const ROUNDS_PER_TEST = 5;
const MAX_HISTORY = 200;
const STORAGE_KEY = "reactionTimeHistory";
const PREF_KEY = "reactionTimeOutlierPref";
const SCREEN_CLASSES = ["screen-start", "screen-wait", "screen-go", "screen-result"];

const area = document.getElementById("area");
const runText = document.getElementById("run-text");
const runSub = document.getElementById("run-sub");
const singleValue = document.getElementById("single-value");
const finalValue = document.getElementById("final-value");
const finalSub = document.getElementById("final-sub");
const attemptList = document.getElementById("attempt-list");
const middleResult = document.getElementById("middle-result");
const finalResult = document.getElementById("final-result");
const startScreen = document.querySelector('[data-screen="start"]');
const runScreen = document.querySelector('[data-screen="run"]');
const resultScreen = document.querySelector('[data-screen="result"]');

const historyTable = document.getElementById("history-table");
const historyBody = document.getElementById("history-body");
const historyEmpty = document.getElementById("history-empty");
const clearBtn = document.getElementById("clear-history");
const outlierToggle = document.getElementById("outlier-toggle");
const outlierNote = document.getElementById("outlier-note");
const tryAgainBtn = document.getElementById("try-again");

let phase = "start";
let waitTimer = null;
let greenRaf = null;
// Bumped every time pending work is cancelled. A scheduled green captures the
// generation it was created under, so a stale frame can never flip the screen.
let waitGen = 0;
let goTime = 0;
let attempts = [];
let lastResult = [];
let history = loadHistory();

/* ---------- math ---------- */

function avg(arr) {
  if (!arr.length) return 0;
  return arr.reduce(function (a, b) { return a + b; }, 0) / arr.length;
}

function round(v) { return Math.round(v); }

// Single source of truth for the displayed average. The result screen and the
// history table both go through here, so they can never disagree.
function computeStats(list, excludeOutliers) {
  const n = list.length;
  if (n === 0) return { value: 0, excluded: false, used: 0, total: 0 };
  if (!excludeOutliers || n < 3) {
    return { value: avg(list), excluded: false, used: n, total: n };
  }
  const sorted = list.slice().sort(function (a, b) { return a - b; });
  const kept = sorted.slice(1, -1);
  return { value: avg(kept), excluded: true, used: kept.length, total: n };
}

/* ---------- dom helpers ---------- */

function setScreen(screen) {
  for (let i = 0; i < SCREEN_CLASSES.length; i++) {
    area.classList.remove(SCREEN_CLASSES[i]);
  }
  area.classList.add("screen-" + screen);
}

function show(el) { el.hidden = false; }
function hide(el) { el.hidden = true; }

function showOnly(target) {
  const screens = [startScreen, runScreen, resultScreen];
  for (let i = 0; i < screens.length; i++) {
    if (screens[i] === target) show(screens[i]);
    else hide(screens[i]);
  }
}

/* ---------- timers ---------- */

function cancelPending() {
  waitGen++;
  if (waitTimer !== null) {
    clearTimeout(waitTimer);
    waitTimer = null;
  }
  if (greenRaf !== null) {
    cancelAnimationFrame(greenRaf);
    greenRaf = null;
  }
}

/* ---------- flow ---------- */

function toStartScreen() {
  cancelPending();
  phase = "start";
  attempts = [];
  setScreen("start");
  showOnly(startScreen);
  area.focus();
}

function beginWait() {
  cancelPending();
  phase = "wait";
  setScreen("wait");
  showOnly(runScreen);
  runText.textContent = "Wait for green";
  hide(runSub);

  const delay = 1500 + Math.random() * 3000;
  waitTimer = setTimeout(turnGreen, delay);
}

function turnGreen() {
  waitTimer = null;
  const gen = waitGen;
  // Apply the green AND stamp the clock in the same frame. Stamping inside the
  // rAF means the measurement starts at the paint that makes green visible,
  // instead of at an arbitrary point before it.
  greenRaf = requestAnimationFrame(function () {
    greenRaf = null;
    // A cancelled frame must never fire. Comparing generations catches the case
    // where cancelAnimationFrame did not take effect (or raced).
    if (gen !== waitGen) return;
    setScreen("go");
    runText.textContent = "Click!";
    goTime = performance.now();
    phase = "go";
  });
}

function showTooEarly() {
  cancelPending();
  phase = "wait";
  setScreen("wait");
  showOnly(runScreen);
  runText.textContent = "Too early! Try again.";
  show(runSub);
  runSub.textContent = "Wait for green\u2026";
  waitTimer = setTimeout(beginWait, 1500);
}

function handleTrigger() {
  if (phase === "start") {
    beginWait();
  } else if (phase === "wait") {
    showTooEarly();
  } else if (phase === "go") {
    const ms = round(performance.now() - goTime);
    attempts.push(ms);
    if (attempts.length < ROUNDS_PER_TEST) {
      showMiddleResult(ms);
    } else {
      showFinalResult();
    }
  } else if (phase === "result") {
    beginWait();
  } else if (phase === "final") {
    toStartScreen();
  }
}

function showMiddleResult(ms) {
  phase = "result";
  setScreen("result");
  showOnly(resultScreen);
  hide(finalResult);
  show(middleResult);
  singleValue.textContent = ms + " ms";
}

function showFinalResult() {
  phase = "final";
  setScreen("result");
  showOnly(resultScreen);
  hide(middleResult);
  show(finalResult);

  lastResult = attempts.slice();
  renderFinalDisplay();

  const record = {
    timestamp: Date.now(),
    attempts: lastResult.slice(),
    average: round(avg(lastResult))
  };
  history.push(record);
  if (history.length > MAX_HISTORY) {
    history = history.slice(history.length - MAX_HISTORY);
  }
  const saved = saveHistory();
  renderHistory();
  if (!saved) {
    outlierNote.textContent = "Could not save to local storage (quota or private mode). This result is not persisted.";
  }
}

function renderFinalDisplay() {
  const stats = computeStats(lastResult, outlierToggle.checked);
  finalValue.textContent = round(stats.value) + "ms";
  attemptList.textContent = "Attempts: " + lastResult.join(" ms, ") + " ms";
  finalSub.textContent = stats.excluded
    ? "Average of " + stats.used + " of " + stats.total + " attempts (outliers excluded)"
    : "Average of " + ROUNDS_PER_TEST + " attempts";
}

/* ---------- persistence ---------- */

function isValidRecord(r) {
  if (!r || typeof r !== "object") return false;
  if (typeof r.timestamp !== "number" || !isFinite(r.timestamp)) return false;
  if (!Array.isArray(r.attempts) || r.attempts.length === 0) return false;
  for (let i = 0; i < r.attempts.length; i++) {
    const v = r.attempts[i];
    if (typeof v !== "number" || !isFinite(v) || v < 0) return false;
  }
  return true;
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isValidRecord);
  } catch (e) {
    return [];
  }
}

function saveHistory() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    return true;
  } catch (e) {
    return false;
  }
}

function loadOutlierPref() {
  try {
    const raw = localStorage.getItem(PREF_KEY);
    return raw === null ? true : raw === "1";
  } catch (e) {
    return true;
  }
}

function saveOutlierPref(value) {
  try {
    localStorage.setItem(PREF_KEY, value ? "1" : "0");
  } catch (e) {
    /* preference is cosmetic; ignore */
  }
}

/* ---------- history rendering ---------- */

function formatDate(ts) {
  return new Date(ts).toLocaleString();
}

function renderHistory() {
  historyBody.textContent = "";
  const excludeOutliers = outlierToggle.checked;

  if (!history.length) {
    historyTable.hidden = true;
    historyEmpty.hidden = false;
    outlierNote.textContent = "";
    return;
  }

  historyTable.hidden = false;
  historyEmpty.hidden = true;

  const rows = history.slice().reverse();
  let excludedCount = 0;

  for (let i = 0; i < rows.length; i++) {
    const record = rows[i];
    const stats = computeStats(record.attempts, excludeOutliers);
    if (stats.excluded) excludedCount++;

    const tr = document.createElement("tr");

    const tdDate = document.createElement("td");
    tdDate.textContent = formatDate(record.timestamp);
    tr.appendChild(tdDate);

    const tdAttempts = document.createElement("td");
    tdAttempts.textContent = record.attempts.join(" ms, ") + " ms";
    tr.appendChild(tdAttempts);

    const tdAvg = document.createElement("td");
    tdAvg.textContent = round(stats.value) + " ms" + (stats.excluded ? " (outliers excluded)" : "");
    tr.appendChild(tdAvg);

    historyBody.appendChild(tr);
  }

  outlierNote.textContent = excludeOutliers && excludedCount
    ? "Outlier exclusion applied to " + excludedCount + " round(s): fastest and slowest attempts removed before averaging."
    : "";
}

/* ---------- input ---------- */

function isInteractive(el) {
  return !!(el && el.closest && el.closest("button, a, label, input"));
}

function onPointerDown(e) {
  if (isInteractive(e.target)) return;
  handleTrigger();
}

function onKeyDown(e) {
  if (e.key !== " " && e.key !== "Enter" && e.key !== "Spacebar") return;
  if (isInteractive(e.target)) return;
  e.preventDefault();
  handleTrigger();
}

clearBtn.addEventListener("click", function () {
  if (!history.length) return;
  if (!window.confirm("Delete all saved reaction time records? This cannot be undone.")) return;
  history = [];
  saveHistory();
  renderHistory();
});

outlierToggle.addEventListener("change", function () {
  saveOutlierPref(outlierToggle.checked);
  renderHistory();
  if (phase === "final") renderFinalDisplay();
});

tryAgainBtn.addEventListener("click", function (e) {
  e.stopPropagation();
  toStartScreen();
});

area.addEventListener("pointerdown", onPointerDown);
area.addEventListener("keydown", onKeyDown);

/* ---------- init ---------- */

outlierToggle.checked = loadOutlierPref();
renderHistory();
toStartScreen();
