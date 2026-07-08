// ---------------------------------------------------------------------------
// Nudge dashboard realtime client (Dev C, Sprint 3)
//
// Handles: SocketIO live updates, task-card visual states (overdue / due soon
// / blocked / done), the comment thread drawer, and task actions (mark done,
// add / resolve blocker). Written defensively — every page element and every
// network call is optional, so the board still renders and stays interactive
// when SocketIO or the backend routes aren't wired yet.
//
// ---- Contract this expects from the backend (Dev B) -----------------------
//
// REST (fetch):
//   POST /api/tasks/<id>/done                -> marks task done
//   POST /api/tasks/<id>/blockers  {description}  -> adds blocker (status=blocked)
//   POST /api/tasks/<id>/blockers/resolve    -> clears blocker (status=pending)
//   GET  /api/tasks/<id>/comments            -> { comments: [Comment] }
//   POST /api/tasks/<id>/comments  {body}    -> { comment: Comment }
//   where Comment = { author, role, body, created_at }
//
// SocketIO (server -> client):
//   "task_updated"    { id, status, priority, due_date, due_date_iso }
//   "comment_added"   { task_id, comment: Comment }
//   "blocker_updated" { task_id, status, description }
//
// Until those exist the calls fail quietly and the UI updates optimistically,
// so a demo without the backend still behaves. Event/endpoint names are the
// single source of truth here — keep them in sync with routes/api.py + sockets.py.
// ---------------------------------------------------------------------------

(function () {
  "use strict";

  var COLUMNS = ["pending", "blocked", "done"];

  // ---- small helpers ----

  function card(taskId) {
    return document.querySelector('.task-card[data-task-id="' + taskId + '"]');
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function todayIso() {
    // Local date as YYYY-MM-DD (avoids UTC drift from toISOString()).
    var d = new Date();
    return (
      d.getFullYear() +
      "-" +
      String(d.getMonth() + 1).padStart(2, "0") +
      "-" +
      String(d.getDate()).padStart(2, "0")
    );
  }

  function daysUntil(iso) {
    if (!iso) return null;
    var due = new Date(iso + "T00:00:00");
    if (isNaN(due.getTime())) return null;
    var now = new Date(todayIso() + "T00:00:00");
    return Math.round((due - now) / 86400000);
  }

  // ---- visual states (badges) ----

  function renderBadges(el) {
    var slot = el.querySelector("[data-badges]");
    if (!slot) return;
    slot.innerHTML = "";

    var status = el.getAttribute("data-status");
    var badges = [];

    if (status === "done") {
      badges.push(["Done", "badge-done"]);
    } else if (status === "blocked") {
      badges.push(["Blocked", "badge-blocked"]);
    } else {
      var days = daysUntil(el.getAttribute("data-due"));
      if (days !== null && days < 0) {
        badges.push(["Overdue", "badge-overdue"]);
      } else if (days !== null && days <= 2) {
        badges.push(["Due soon", "badge-due-soon"]);
      }
    }

    badges.forEach(function (b) {
      var span = document.createElement("span");
      span.className = "task-badge " + b[1];
      span.textContent = b[0];
      slot.appendChild(span);
    });
  }

  function refreshAllBadges() {
    document.querySelectorAll(".task-card").forEach(renderBadges);
  }

  function updateCounts() {
    COLUMNS.forEach(function (key) {
      var container = document.querySelector('[data-column-cards="' + key + '"]');
      var count = document.querySelector('[data-count="' + key + '"]');
      if (container && count) {
        count.textContent = "(" + container.querySelectorAll(".task-card").length + ")";
      }
    });
  }

  // ---- moving a card between columns on a status change ----

  function applyStatus(taskId, status) {
    var el = card(taskId);
    if (!el) return;

    el.setAttribute("data-status", status);
    COLUMNS.forEach(function (s) {
      el.classList.remove("status-" + s);
    });
    el.classList.add("status-" + status);

    var target = document.querySelector('[data-column-cards="' + status + '"]');
    if (target && el.parentElement !== target) {
      target.appendChild(el);
    }

    // toggle the "Resolve Blocker" action to match the new status
    var resolve = el.querySelector('[data-only-status="blocked"]');
    if (resolve) resolve.style.display = status === "blocked" ? "" : "none";

    renderBadges(el);
    updateCounts();
  }

  // ---- task actions (fetch, optimistic) ----

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
  }

  function handleAction(action, taskId) {
    if (action === "done") {
      applyStatus(taskId, "done");
      postJson("/api/tasks/" + taskId + "/done").catch(function () {});
    } else if (action === "blocker") {
      var reason = window.prompt("Describe the blocker:");
      if (reason === null) return; // cancelled
      applyStatus(taskId, "blocked");
      postJson("/api/tasks/" + taskId + "/blockers", { description: reason }).catch(function () {});
    } else if (action === "resolve-blocker") {
      applyStatus(taskId, "pending");
      postJson("/api/tasks/" + taskId + "/blockers/resolve").catch(function () {});
    } else if (action === "comments") {
      openDrawer(taskId);
    }
  }

  // ---- comment drawer ----

  var drawer = document.getElementById("comment-drawer");

  function drawerParts() {
    return {
      task: drawer.querySelector("[data-drawer-task]"),
      thread: drawer.querySelector("[data-comment-thread]"),
      form: drawer.querySelector("[data-comment-form]"),
      input: drawer.querySelector("[data-comment-input]"),
      hint: drawer.querySelector("[data-comment-hint]"),
    };
  }

  function commentKey(comment) {
    return [comment.author || "", comment.created_at || "", comment.body || ""].join("");
  }

  function renderComment(comment, unsent) {
    var wrap = document.createElement("div");
    wrap.className = "comment" + (unsent ? " comment-unsent" : "");
    wrap.dataset.commentKey = commentKey(comment);
    var who = comment.author || "You";
    var role = comment.role ? " (" + comment.role + ")" : "";
    var when = comment.created_at ? " · " + comment.created_at : "";
    wrap.innerHTML =
      '<div class="comment-head">' +
      escapeHtml(who) +
      '<span class="comment-role">' +
      escapeHtml(role + when) +
      "</span></div>" +
      '<div class="comment-body">' +
      escapeHtml(comment.body) +
      "</div>";
    return wrap;
  }

  function setThread(comments) {
    var p = drawerParts();
    p.thread.innerHTML = "";
    if (!comments || !comments.length) {
      p.thread.innerHTML = '<p class="comment-drawer-empty">No comments yet.</p>';
      return;
    }
    comments.forEach(function (c) {
      p.thread.appendChild(renderComment(c, false));
    });
  }

  function appendComment(comment, unsent) {
    var p = drawerParts();
    // Dedupe: the author both renders their POST response and receives the
    // server's comment_added broadcast echo — only show the comment once.
    if (!unsent) {
      var key = commentKey(comment);
      var existing = p.thread.querySelector('.comment[data-comment-key="' + cssEscape(key) + '"]');
      if (existing) return;
    }
    var empty = p.thread.querySelector(".comment-drawer-empty");
    if (empty) empty.remove();
    p.thread.appendChild(renderComment(comment, unsent));
    p.thread.scrollTop = p.thread.scrollHeight;
  }

  function cssEscape(value) {
    if (window.CSS && window.CSS.escape) return window.CSS.escape(value);
    return value.replace(/["\\\]\[]/g, "\\$&");
  }

  function openDrawer(taskId) {
    if (!drawer) return;
    drawer.hidden = false;
    drawer.dataset.taskId = taskId;

    var p = drawerParts();
    var el = card(taskId);
    var label = el ? el.querySelector(".task-card-description") : null;
    p.task.textContent = label ? label.textContent : "Task #" + taskId;
    p.hint.textContent = "";
    p.thread.innerHTML = '<p class="comment-drawer-empty">Loading…</p>';

    fetch("/api/tasks/" + taskId + "/comments")
      .then(function (r) {
        if (!r.ok) throw new Error("unavailable");
        return r.json();
      })
      .then(function (data) {
        setThread(data.comments || []);
      })
      .catch(function () {
        setThread([]);
      });

    drawer.scrollIntoView({ behavior: "smooth", block: "nearest" });
    p.input.focus();
  }

  function closeDrawer() {
    if (drawer) drawer.hidden = true;
  }

  function submitComment(event) {
    event.preventDefault();
    var taskId = drawer.dataset.taskId;
    var p = drawerParts();
    var body = p.input.value.trim();
    if (!body || !taskId) return;

    p.input.value = "";
    p.hint.textContent = "";

    postJson("/api/tasks/" + taskId + "/comments", { body: body })
      .then(function (r) {
        if (!r.ok) throw new Error("unavailable");
        return r.json();
      })
      .then(function (data) {
        // Render from the server's canonical comment (real author/timestamp).
        // appendComment dedupes, so the comment_added socket echo won't double it.
        if (data && data.comment) appendComment(data.comment, false);
      })
      .catch(function () {
        // Offline / backend unavailable: show the text locally, marked unsent.
        appendComment({ author: "You", role: "", body: body, created_at: "just now" }, true);
        p.hint.textContent = "Not saved — backend unavailable.";
      });
  }

  // ---- socket wiring ----

  function wireSocket() {
    if (typeof io === "undefined") return;
    var socket;
    try {
      socket = io();
    } catch (err) {
      return;
    }

    socket.on("task_updated", function (data) {
      if (!data || data.id == null) return;
      var el = card(data.id);
      if (el && data.due_date_iso !== undefined) el.setAttribute("data-due", data.due_date_iso || "");
      if (data.status) applyStatus(data.id, data.status);
    });

    socket.on("blocker_updated", function (data) {
      if (!data || data.task_id == null) return;
      applyStatus(data.task_id, data.status || "blocked");
    });

    socket.on("comment_added", function (data) {
      if (!data || data.task_id == null || !data.comment) return;
      if (drawer && !drawer.hidden && String(drawer.dataset.taskId) === String(data.task_id)) {
        appendComment(data.comment, false);
      }
    });
  }

  // ---- init ----

  document.addEventListener("click", function (event) {
    var btn = event.target.closest("[data-action]");
    if (btn) {
      handleAction(btn.getAttribute("data-action"), btn.getAttribute("data-task-id"));
      return;
    }
    if (event.target.closest("[data-drawer-close]")) closeDrawer();
  });

  if (drawer) {
    var form = drawer.querySelector("[data-comment-form]");
    if (form) form.addEventListener("submit", submitComment);
  }

  refreshAllBadges();
  updateCounts();
  // Hide "Resolve Blocker" on non-blocked cards on first paint.
  document.querySelectorAll('[data-only-status="blocked"]').forEach(function (btn) {
    var el = btn.closest(".task-card");
    if (el && el.getAttribute("data-status") !== "blocked") btn.style.display = "none";
  });
  wireSocket();
})();
