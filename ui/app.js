"use strict";

/*
 * Browser UI for the legal review pipeline.
 *
 * It drives the same endpoints a script would: POST /legal starts a review,
 * GET /legal/{task_id} follows it, POST /legal/{task_id}/respond answers the
 * model's questions. No build step and no dependencies. Every value that comes
 * back from the API reaches the page through text nodes and is never parsed as
 * HTML, so a summary or a question written by the model cannot inject markup.
 */

const POLL_MS = 2500;
const MAX_BACKOFF_MS = 30000;
const QUIET_HINT_MS = 45000;
const HEALTH_MS = 15000;
const RECENT_KEY = "legal-review-agent:recent";
const RECENT_LIMIT = 20;

const RUNNING = new Set(["processing", "awaiting_human"]);
const SEVERITIES = ["critical", "high", "medium", "low"];

const STATUS_LABELS = {
  loading: "Loading",
  processing: "Processing",
  awaiting_human: "Needs your answer",
  completed: "Completed",
  failed: "Failed",
  canceled: "Canceled",
  terminated: "Terminated",
  timed_out: "Timed out",
  continued_as_new: "Continued",
};

const DOCUMENT_LABELS = {
  processing: "In progress",
  awaiting_human: "Waiting for your answer",
  completed: "Done",
};

const DECISION_LABELS = {
  auto_approved: "Auto-approved",
  human_approved: "Revised with your answer",
  human_rejected: "Rejected by a reviewer",
  unreviewed_timeout: "Unreviewed",
};

const state = {
  // files chosen for the next review
  files: [],
  // identifies the review on screen, so a poll that returns after the user
  // has moved on is ignored
  view: null,
  timer: null,
  failures: 0,
  lastSignature: "",
  lastChangeAt: 0,
  // "<task_id>/<pdf_key>" for answers sent from this page
  answered: new Set(),
  // pdf_key -> question card, kept across polls so a half-typed answer survives
  questionCards: new Map(),
  // pdf_keys whose result card is already on screen while the review runs
  resultCards: new Set(),
};

/* --- small helpers ------------------------------------------------------ */

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);

  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }

  for (const child of children.flat()) {
    if (child === undefined || child === null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }

  return node;
}

function byId(id) {
  return document.getElementById(id);
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function relativeTime(timestamp) {
  const seconds = Math.round((Date.now() - timestamp) / 1000);
  if (!Number.isFinite(seconds)) return "";
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return new Date(timestamp).toLocaleDateString();
}

function displayName(pdfKey) {
  // uploads are stored as <name>-<8 hex>.pdf; the suffix only keeps keys unique
  return String(pdfKey).replace(/-[0-9a-f]{8}(\.pdf)$/i, "$1");
}

function plural(count, one, many) {
  return `${count} ${count === 1 ? one : many}`;
}

function setBusy(button, busy, text) {
  if (busy) {
    button.dataset.label = button.textContent;
    button.textContent = text;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  } else {
    button.textContent = button.dataset.label || button.textContent;
    button.disabled = false;
    button.removeAttribute("aria-busy");
  }
}

function showInlineError(node, message) {
  if (!node) return;
  node.textContent = message;
  node.hidden = !message;
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // navigator.clipboard needs a secure context, and plain http on a LAN
    // address is not one, so fall back to the old selection trick
    const area = el("textarea", { class: "visually-hidden", "aria-hidden": "true" });
    area.value = text;
    document.body.append(area);
    area.select();
    try {
      return document.execCommand("copy");
    } catch {
      return false;
    } finally {
      area.remove();
    }
  }
}

function copyButton(text, label) {
  const button = el(
    "button",
    {
      type: "button",
      class: "icon-button",
      title: label,
      "aria-label": label,
      onclick: async () => {
        button.textContent = (await copyText(text)) ? "Copied" : "Copy failed";
        setTimeout(() => {
          button.textContent = "Copy";
        }, 1500);
      },
    },
    "Copy",
  );
  return button;
}

function downloadJson(filename, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const link = el("a", { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function statusPill(status, small = false) {
  return el(
    "span",
    { class: `pill pill-${status}${small ? " pill-small" : ""}` },
    STATUS_LABELS[status] || status || "Unknown",
  );
}

function severityChip(severity, text) {
  return el("span", { class: `severity severity-${severity}` }, text || severity);
}

function severityRank(severity) {
  const rank = SEVERITIES.indexOf(severity);
  return rank === -1 ? SEVERITIES.length : rank;
}

/* --- the API ------------------------------------------------------------ */

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new ApiError(0, "Can't reach the API. Is it running (uv run python main.py)?");
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    // not JSON; the status code is all there is
  }

  if (!response.ok) {
    throw new ApiError(response.status, describeError(response.status, body));
  }

  return body;
}

function describeError(status, body) {
  const detail = body && body.detail;
  let text = `The API answered ${status}`;

  if (typeof detail === "string") text = detail;
  // FastAPI's validation errors are a list of {loc, msg}
  else if (Array.isArray(detail)) text = detail.map((item) => item.msg).join("; ");

  if (status === 503) {
    // a query to a running workflow also needs a worker to answer it
    return `${text}. Check that the Temporal server and the legal worker are running.`;
  }
  return text;
}

async function checkHealth() {
  const node = byId("api-status");
  const label = node.querySelector(".status-text");
  try {
    await api("/health");
    node.dataset.state = "ok";
    label.textContent = "API connected";
  } catch {
    node.dataset.state = "down";
    label.textContent = "API unreachable";
  }
}

/* --- recent reviews, remembered in this browser -------------------------- */

function loadRecent() {
  try {
    const parsed = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item) => item && typeof item.taskId === "string")
      .map((item) => ({ ...item, files: Array.isArray(item.files) ? item.files : [] }));
  } catch {
    return [];
  }
}

function saveRecent(items) {
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(items.slice(0, RECENT_LIMIT)));
  } catch {
    // storage is unavailable (private mode, blocked site data); the list just won't persist
  }
}

function rememberReview(entry) {
  saveRecent([entry, ...loadRecent().filter((item) => item.taskId !== entry.taskId)]);
}

function documentKeys(body) {
  if (Array.isArray(body.documents)) return body.documents.map((doc) => doc.pdf_key);
  return Object.keys(body.documents || {});
}

function updateRecent(taskId, body) {
  const items = loadRecent();
  let item = items.find((entry) => entry.taskId === taskId);

  if (!item) {
    // opened by id rather than started here
    item = { taskId, files: [], status: body.status, createdAt: Date.now() };
    items.unshift(item);
  } else if (item.status === body.status && item.files.length) {
    return;
  }

  item.status = body.status;
  if (!item.files.length) item.files = documentKeys(body).map(displayName);

  saveRecent(items);
  renderRecent();
}

function describeFiles(item) {
  if (!item.files.length) return `Task ${item.taskId}`;
  const [first, ...rest] = item.files;
  return rest.length ? `${first} + ${rest.length} more` : first;
}

function renderRecent() {
  const items = loadRecent();
  const active = currentTaskId();

  byId("recent").replaceChildren(
    ...items.map((item) =>
      el(
        "li",
        {},
        el(
          "a",
          {
            class: "recent-item",
            href: `#/review/${item.taskId}`,
            "aria-current": item.taskId === active ? "page" : null,
          },
          el("span", { class: "recent-name", title: item.files.join(", ") }, describeFiles(item)),
          el(
            "span",
            { class: "recent-meta" },
            item.status ? statusPill(item.status, true) : null,
            el("span", {}, relativeTime(item.createdAt)),
          ),
        ),
      ),
    ),
  );

  byId("recent-empty").hidden = items.length > 0;
  byId("clear-recent").hidden = items.length === 0;
}

/* --- routing ------------------------------------------------------------- */

function currentTaskId() {
  const match = location.hash.match(/^#\/review\/([A-Za-z0-9_-]+)$/);
  return match ? match[1] : null;
}

function stopPolling() {
  clearTimeout(state.timer);
  state.timer = null;
  state.view = null;
}

function route() {
  stopPolling();

  const taskId = currentTaskId();
  if (taskId) showReview(taskId);
  else showNewReview();

  renderRecent();
}

/* --- new review ------------------------------------------------------------ */

function showNewReview() {
  const input = el("input", {
    type: "file",
    id: "file-input",
    class: "visually-hidden",
    accept: "application/pdf,.pdf",
    multiple: true,
    "aria-label": "Choose PDF documents",
    onchange: (event) => {
      addFiles(event.target.files);
      event.target.value = "";
    },
  });

  const dropzone = el(
    "label",
    {
      class: "dropzone",
      ondragover: (event) => {
        event.preventDefault();
        dropzone.classList.add("dragging");
      },
      ondragleave: () => dropzone.classList.remove("dragging"),
      ondrop: (event) => {
        event.preventDefault();
        dropzone.classList.remove("dragging");
        addFiles(event.dataTransfer.files);
      },
    },
    input,
    el("span", { class: "dropzone-icon", "aria-hidden": "true" }, "⇪"),
    el("strong", {}, "Drop PDF documents here"),
    el("span", { class: "muted small" }, "or click to choose. You can add several at once."),
  );

  byId("main").replaceChildren(
    el(
      "section",
      { class: "panel" },
      el("h2", {}, "New review"),
      el(
        "p",
        { class: "muted" },
        "Each document is read by the model and checked for legal risk. Documents are sent to the model provider configured on the server.",
      ),
      dropzone,
      el("ul", { class: "file-list", id: "file-list" }),
      el(
        "div",
        { class: "actions" },
        el("span", { class: "muted small", id: "file-summary" }),
        el("button", { type: "button", class: "button primary", id: "submit", onclick: submitReview }, "Start review"),
      ),
      el("p", { class: "form-error", id: "submit-error", role: "alert", hidden: true }),
    ),
    el(
      "section",
      { class: "panel" },
      el("h3", {}, "How a review works"),
      el(
        "ol",
        { class: "steps" },
        el(
          "li",
          {},
          el(
            "div",
            {},
            el("strong", {}, "Upload"),
            "Your PDFs are stored and a workflow starts. A few documents are analysed at a time.",
          ),
        ),
        el(
          "li",
          {},
          el(
            "div",
            {},
            el("strong", {}, "Answer questions"),
            "When the model needs something only you know, it asks here and that document waits for you.",
          ),
        ),
        el(
          "li",
          {},
          el(
            "div",
            {},
            el("strong", {}, "Read the risks"),
            "Each document gets a summary and its key risks, worst first. Unanswered questions are flagged.",
          ),
        ),
      ),
    ),
  );

  renderFiles();
}

function addFiles(fileList) {
  const problems = [];

  for (const file of fileList) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      problems.push(`${file.name} is not a PDF`);
    } else if (file.size === 0) {
      problems.push(`${file.name} is empty`);
    } else if (!state.files.some((chosen) => chosen.name === file.name && chosen.size === file.size)) {
      state.files.push(file);
    }
  }

  renderFiles();
  showInlineError(byId("submit-error"), problems.length ? `${problems.join(". ")}.` : "");
}

function renderFiles() {
  const list = byId("file-list");
  if (!list) return;

  list.replaceChildren(
    ...state.files.map((file, index) =>
      el(
        "li",
        { class: "file-row" },
        el("span", { class: "file-icon", "aria-hidden": "true" }, "PDF"),
        el("span", { class: "file-name", title: file.name }, file.name),
        el("span", { class: "muted small" }, formatBytes(file.size)),
        el(
          "button",
          {
            type: "button",
            class: "icon-button",
            "aria-label": `Remove ${file.name}`,
            onclick: () => {
              state.files.splice(index, 1);
              renderFiles();
            },
          },
          "Remove",
        ),
      ),
    ),
  );

  const total = state.files.reduce((sum, file) => sum + file.size, 0);
  byId("file-summary").textContent = state.files.length
    ? `${plural(state.files.length, "file", "files")} · ${formatBytes(total)}`
    : "No files chosen yet";
  byId("submit").disabled = state.files.length === 0;
}

async function submitReview() {
  const button = byId("submit");
  const form = new FormData();
  for (const file of state.files) form.append("files", file, file.name);

  setBusy(button, true, "Uploading…");
  showInlineError(byId("submit-error"), "");

  try {
    const body = await api("/legal", { method: "POST", body: form });
    rememberReview({
      taskId: body.task_id,
      files: state.files.map((file) => file.name),
      status: body.status,
      createdAt: Date.now(),
    });
    state.files = [];
    location.hash = `#/review/${body.task_id}`;
  } catch (error) {
    showInlineError(byId("submit-error"), error.message);
    setBusy(button, false);
  }
}

/* --- following a review ---------------------------------------------------- */

function showReview(taskId) {
  const token = {};
  state.view = token;
  state.failures = 0;
  state.lastSignature = "";
  state.lastChangeAt = Date.now();
  state.questionCards = new Map();
  state.resultCards = new Set();

  byId("main").replaceChildren(
    el(
      "section",
      { class: "panel review-head" },
      el(
        "div",
        {},
        el("h2", {}, "Review"),
        el(
          "div",
          { class: "task-line" },
          el("span", { class: "muted" }, "Task"),
          el("code", {}, taskId),
          copyButton(taskId, "Copy task id"),
        ),
      ),
      el(
        "div",
        { class: "review-status", "aria-live": "polite" },
        el("span", { id: "overall-status" }, statusPill("loading")),
        el("span", { id: "checked-at", class: "muted small" }, "Fetching status…"),
      ),
    ),
    el("div", { id: "notice", "aria-live": "polite" }),
    el("section", { id: "questions", class: "questions", hidden: true }),
    el("section", { id: "progress", class: "panel", hidden: true }),
    el("section", { id: "results", class: "results", hidden: true }),
  );

  poll(taskId, token);
}

function schedule(taskId, token, delay) {
  clearTimeout(state.timer);
  state.timer = setTimeout(() => poll(taskId, token), delay);
}

async function poll(taskId, token) {
  if (state.view !== token) return;

  let body;
  try {
    body = await api(`/legal/${encodeURIComponent(taskId)}`);
  } catch (error) {
    if (state.view !== token) return;
    if (error.status === 404) {
      renderNotFound(taskId);
      return;
    }
    state.failures += 1;
    renderNotice("error", `${error.message} Trying again…`);
    schedule(taskId, token, Math.min(POLL_MS * 2 ** state.failures, MAX_BACKOFF_MS));
    return;
  }

  if (state.view !== token) return;

  state.failures = 0;
  renderReview(taskId, body);
  updateRecent(taskId, body);

  if (RUNNING.has(body.status)) schedule(taskId, token, POLL_MS);
}

function renderReview(taskId, body) {
  byId("overall-status").replaceChildren(statusPill(body.status));
  byId("checked-at").textContent = `Checked ${new Date().toLocaleTimeString()}`;

  if (body.status === "completed") {
    clearNotice();
    byId("questions").hidden = true;
    byId("progress").hidden = true;
    renderResults(taskId, body);
    return;
  }

  if (!RUNNING.has(body.status)) {
    byId("questions").hidden = true;
    byId("progress").hidden = true;
    renderNotice(
      "error",
      `This review ended as "${STATUS_LABELS[body.status] || body.status}" without results. The Temporal UI (port 8233 with the dev server) shows which step failed and why.`,
    );
    return;
  }

  renderQuestions(taskId, body.pending_questions || []);
  renderProgress(taskId, body.documents || {});
  renderFinished(body.results || [], body.documents || {});
  noticeWhenQuiet(body);
}

function renderFinished(results, documents) {
  // cards are added as documents finish and never redrawn, so reading one
  // is not interrupted by the next poll; the completed view replaces them all
  const section = byId("results");
  if (!results.length) {
    section.hidden = true;
    return;
  }

  if (!section.dataset.partial) {
    section.dataset.partial = "true";
    section.replaceChildren(
      el(
        "div",
        { class: "section-head" },
        el("h3", {}, "Finished so far"),
        el("span", { class: "muted small", id: "finished-count" }),
      ),
    );
  }

  for (const doc of results) {
    if (state.resultCards.has(doc.pdf_key)) continue;
    state.resultCards.add(doc.pdf_key);
    section.append(resultCard(doc));
  }

  byId("finished-count").textContent = `${results.length} of ${Object.keys(documents).length} documents`;
  section.hidden = false;
}

function renderQuestions(taskId, questions) {
  const section = byId("questions");
  const pending = new Map(questions.map((item) => [item.pdf_key, item.question]));

  if (!section.childElementCount) {
    section.append(
      el(
        "div",
        { class: "section-head" },
        el("h3", {}, "The model has a question"),
        el(
          "p",
          { class: "muted small" },
          "That document waits for your answer. If nobody answers in time it finishes anyway and is flagged as unreviewed.",
        ),
      ),
    );
  }

  for (const [key, card] of state.questionCards) {
    if (!pending.has(key)) {
      card.remove();
      state.questionCards.delete(key);
    }
  }

  for (const [key, question] of pending) {
    if (!state.questionCards.has(key)) {
      const card = questionCard(taskId, key, question);
      state.questionCards.set(key, card);
      section.append(card);
    }
  }

  section.hidden = pending.size === 0;
}

function questionCard(taskId, pdfKey, question) {
  const id = `answer-${pdfKey.replace(/[^A-Za-z0-9_-]/g, "-")}`;
  const textarea = el("textarea", { id, rows: "3", required: true, placeholder: "Your answer…" });
  const error = el("p", { class: "form-error", role: "alert", hidden: true });
  const button = el("button", { type: "submit", class: "button primary" }, "Send answer");

  const form = el(
    "form",
    {
      class: "answer-form",
      onsubmit: async (event) => {
        event.preventDefault();

        const answer = textarea.value.trim();
        if (!answer) {
          showInlineError(error, "Write an answer first.");
          textarea.focus();
          return;
        }

        setBusy(button, true, "Sending…");
        textarea.disabled = true;
        showInlineError(error, "");

        try {
          await api(`/legal/${encodeURIComponent(taskId)}/respond`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pdf_key: pdfKey, answer }),
          });
          state.answered.add(`${taskId}/${pdfKey}`);
          form.classList.add("sent");
          button.textContent = "Answer sent";
        } catch (failure) {
          showInlineError(error, failure.message);
          setBusy(button, false);
          textarea.disabled = false;
        }
      },
    },
    el("label", { for: id, class: "visually-hidden" }, `Answer for ${displayName(pdfKey)}`),
    textarea,
    el("div", { class: "actions" }, el("span", { class: "muted small" }, "Ctrl+Enter to send"), button),
    error,
  );

  textarea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) form.requestSubmit();
  });

  return el(
    "article",
    { class: "question-card" },
    el(
      "div",
      { class: "question-doc" },
      el("span", { class: "label" }, "Document"),
      el("strong", { title: pdfKey }, displayName(pdfKey)),
    ),
    el("blockquote", { class: "question" }, question),
    form,
  );
}

function renderProgress(taskId, documents) {
  const entries = Object.entries(documents);
  const done = entries.filter(([, status]) => status === "completed").length;
  const percent = entries.length ? Math.round((done / entries.length) * 100) : 0;

  const section = byId("progress");
  section.hidden = false;
  section.replaceChildren(
    el(
      "div",
      { class: "section-head" },
      el("h3", {}, "Documents"),
      el("span", { class: "muted small" }, `${done} of ${entries.length} done`),
    ),
    el(
      "div",
      {
        class: "progress-bar",
        role: "progressbar",
        "aria-label": "Documents finished",
        "aria-valuemin": "0",
        "aria-valuemax": "100",
        "aria-valuenow": String(percent),
      },
      el("span", { style: `width: ${percent}%` }),
    ),
    el(
      "ul",
      { class: "doc-list" },
      entries.map(([key, status]) => {
        // after an answer the document is back to "processing" while the model revises
        const revising = status === "processing" && state.answered.has(`${taskId}/${key}`);
        return el(
          "li",
          { class: "doc-row" },
          el("span", { class: "doc-name", title: key }, displayName(key)),
          el(
            "span",
            { class: `doc-status doc-${revising ? "revising" : status}` },
            el("span", { class: "dot", "aria-hidden": "true" }),
            revising ? "Revising with your answer" : DOCUMENT_LABELS[status] || status,
          ),
        );
      }),
    ),
    el(
      "p",
      { class: "muted small" },
      "Only a few documents are analysed at once; the others show as in progress until their turn.",
    ),
  );
}

function noticeWhenQuiet(body) {
  const signature = JSON.stringify([body.documents, body.pending_questions]);
  const now = Date.now();

  if (signature !== state.lastSignature) {
    state.lastSignature = signature;
    state.lastChangeAt = now;
  }

  if (body.status === "processing" && now - state.lastChangeAt > QUIET_HINT_MS) {
    renderNotice(
      "info",
      "Still working. Every 10 pages is a separate model call, so long documents take a while. If nothing changes for several minutes, check that the legal worker is running (uv run python -m workers.legal_advice_worker).",
    );
  } else {
    clearNotice();
  }
}

function renderResults(taskId, body) {
  const section = byId("results");
  if (section.dataset.rendered === taskId) return;
  section.dataset.rendered = taskId;
  section.hidden = false;

  const documents = body.documents || [];
  const risks = documents.flatMap((doc) => doc.key_risks || []);
  const attention = documents.filter((doc) => doc.needs_attention).length;
  const counts = {};
  for (const risk of risks) counts[risk.severity] = (counts[risk.severity] || 0) + 1;

  section.replaceChildren(
    el(
      "div",
      { class: "panel summary-strip" },
      stat(documents.length, documents.length === 1 ? "document" : "documents"),
      stat(risks.length, risks.length === 1 ? "risk flagged" : "risks flagged"),
      el(
        "div",
        { class: "severity-counts" },
        SEVERITIES.filter((severity) => counts[severity]).map((severity) =>
          severityChip(severity, `${counts[severity]} ${severity}`),
        ),
      ),
      attention ? el("span", { class: "attention-count" }, `${plural(attention, "document", "documents")} unreviewed`) : null,
      el(
        "div",
        { class: "summary-actions" },
        el(
          "button",
          { type: "button", class: "button", onclick: () => downloadJson(`legal-review-${taskId}.json`, body) },
          "Download JSON",
        ),
      ),
    ),
    // replaceChildren does not flatten arrays, unlike el()
    ...documents.map(resultCard),
  );
}

function stat(value, label) {
  return el(
    "div",
    { class: "stat" },
    el("span", { class: "stat-value" }, value),
    el("span", { class: "stat-label" }, label),
  );
}

function resultCard(doc) {
  const risks = [...(doc.key_risks || [])].sort((a, b) => severityRank(a.severity) - severityRank(b.severity));

  return el(
    "article",
    { class: `panel result-card${doc.needs_attention ? " needs-attention" : ""}` },
    el(
      "header",
      { class: "result-head" },
      el("h3", { title: doc.pdf_key }, displayName(doc.pdf_key)),
      el(
        "span",
        { class: `decision decision-${doc.review_decision}` },
        DECISION_LABELS[doc.review_decision] || doc.review_decision,
      ),
    ),
    doc.needs_attention
      ? el(
          "p",
          { class: "attention" },
          "The model had a question that nobody answered in time. Treat this advice as a draft.",
        )
      : null,
    el("p", { class: "summary" }, doc.summary),
    el("h4", {}, risks.length ? `Key risks (${risks.length})` : "No key risks flagged"),
    risks.length
      ? el(
          "ol",
          { class: "risks" },
          risks.map((risk) =>
            el(
              "li",
              { class: "risk" },
              severityChip(risk.severity),
              el(
                "div",
                {},
                el("p", {}, risk.description),
                risk.location ? el("p", { class: "muted small" }, risk.location) : null,
              ),
            ),
          ),
        )
      : null,
    doc.s3_path
      ? el(
          "footer",
          { class: "result-foot" },
          el("span", { class: "muted small" }, "Stored at"),
          el("code", {}, doc.s3_path),
          copyButton(doc.s3_path, "Copy S3 path"),
        )
      : null,
  );
}

function renderNotFound(taskId) {
  byId("main").replaceChildren(
    el(
      "section",
      { class: "panel" },
      el("h2", {}, "Review not found"),
      el(
        "p",
        { class: "muted" },
        "Temporal has no review with task id ",
        el("code", {}, taskId),
        ". A Temporal dev server forgets its history when it restarts, unless it was started with --db-filename.",
      ),
      el(
        "div",
        { class: "actions" },
        el(
          "button",
          {
            type: "button",
            class: "button",
            onclick: () => {
              saveRecent(loadRecent().filter((item) => item.taskId !== taskId));
              location.hash = "#/new";
            },
          },
          "Remove from recent",
        ),
        el("a", { class: "button primary", href: "#/new" }, "Start a new review"),
      ),
    ),
  );
}

function renderNotice(kind, text) {
  const node = byId("notice");
  if (node) node.replaceChildren(el("div", { class: `notice notice-${kind}`, role: kind === "error" ? "alert" : "status" }, text));
}

function clearNotice() {
  const node = byId("notice");
  if (node) node.replaceChildren();
}

/* --- start ------------------------------------------------------------------ */

function init() {
  byId("open-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = byId("open-task");
    // accept the workflow id too, since that is what the Temporal UI shows
    const taskId = input.value.trim().replace(/^legal-review-/, "");
    if (!/^[A-Za-z0-9_-]+$/.test(taskId)) {
      input.focus();
      return;
    }
    input.value = "";
    location.hash = `#/review/${taskId}`;
  });

  byId("clear-recent").addEventListener("click", () => {
    saveRecent([]);
    renderRecent();
  });

  // a file dropped outside the drop zone must not navigate away from the page
  window.addEventListener("dragover", (event) => event.preventDefault());
  window.addEventListener("drop", (event) => event.preventDefault());

  window.addEventListener("hashchange", () => {
    route();
    byId("main").focus({ preventScroll: true });
  });

  route();
  checkHealth();
  setInterval(checkHealth, HEALTH_MS);
  // keeps "5 min ago" in the recent list honest
  setInterval(renderRecent, 60000);
}

init();
