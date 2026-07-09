// Live meeting page: render streamed transcript lines and validate the
// manual-upload fallback form. Written defensively so the page still works
// when SocketIO isn't connected (e.g. the manual-upload demo path).

(function () {
  "use strict";

  var transcript = document.getElementById("transcript");
  var liveStatus = document.getElementById("live-status");

  function appendLine(data) {
    if (!transcript) return;
    var empty = transcript.querySelector(".transcript-empty");
    if (empty) empty.remove();

    var line = document.createElement("p");
    line.className = "transcript-line";

    if (data && data.speaker) {
      var who = document.createElement("span");
      who.className = "transcript-speaker";
      who.textContent = data.speaker + ": ";
      line.appendChild(who);
    }
    line.appendChild(document.createTextNode((data && data.text) || String(data || "")));
    transcript.appendChild(line);
    transcript.scrollTop = transcript.scrollHeight;
  }

  // Only wire up SocketIO if the client library actually loaded.
  if (typeof io !== "undefined") {
    try {
      var socket = io();
      socket.on("connect", function () {
        if (liveStatus) {
          liveStatus.textContent = "Listening";
          liveStatus.className = "status-pill status-pill-ok";
        }
      });
      socket.on("transcript_line", appendLine);
      socket.on("disconnect", function () {
        if (liveStatus) {
          liveStatus.textContent = "Disconnected";
          liveStatus.className = "status-pill status-pill-off";
        }
      });
    } catch (err) {
      // SocketIO present but server unreachable - leave the manual path usable.
    }
  }

  // Manual upload: require either pasted text or a file before submitting.
  var form = document.querySelector(".upload-form");
  if (form) {
    var textarea = form.querySelector("#transcript-text");
    var fileInput = form.querySelector("#transcript-file");
    var hint = form.querySelector("#upload-hint");

    form.addEventListener("submit", function (event) {
      var hasText = textarea && textarea.value.trim().length > 0;
      var hasFile = fileInput && fileInput.files && fileInput.files.length > 0;
      if (!hasText && !hasFile) {
        event.preventDefault();
        if (hint) {
          hint.textContent = "Paste a transcript or choose a file first.";
          hint.classList.add("upload-hint-error");
        }
      }
    });

    if (textarea) {
      textarea.addEventListener("input", function () {
        if (hint) {
          hint.textContent = "";
          hint.classList.remove("upload-hint-error");
        }
      });
    }
  }
})();
