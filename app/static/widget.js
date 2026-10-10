/*
 * Embeddable support chat widget.
 * Add one line to any website:
 *   <script src="https://YOUR-BOT-HOST/static/widget.js" data-title="Harbour Bikes" data-accent="#1d4ed8" defer></script>
 */
(function () {
  var script = document.currentScript;
  var API = new URL(script.src).origin;
  var TITLE = script.getAttribute("data-title") || "Support";
  var ACCENT = script.getAttribute("data-accent") || "#1d4ed8";
  var GREETING = script.getAttribute("data-greeting") || "Hi! Ask me anything about orders, shipping, returns or our bikes.";

  function sessionId() {
    var key = "supportbot_session";
    try {
      var s = localStorage.getItem(key);
      if (s) return s;
      s = "s" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem(key, s);
      return s;
    } catch (e) {
      return "s" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    }
  }
  var SESSION = sessionId();

  var css = "\n.sb-btn{position:fixed;right:20px;bottom:20px;width:56px;height:56px;border-radius:50%;border:0;background:" + ACCENT + ";color:#fff;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.2);z-index:2147483000;display:flex;align-items:center;justify-content:center}" +
    ".sb-btn:focus-visible{outline:3px solid #111;outline-offset:3px}" +
    ".sb-panel{position:fixed;right:20px;bottom:88px;width:360px;max-width:calc(100vw - 32px);height:520px;max-height:calc(100vh - 120px);background:#fff;color:#1a1a1a;border-radius:14px;box-shadow:0 12px 40px rgba(0,0,0,.18);display:none;flex-direction:column;overflow:hidden;z-index:2147483000;font:14px/1.45 system-ui,-apple-system,'Segoe UI',sans-serif}" +
    ".sb-panel.open{display:flex}" +
    ".sb-head{background:" + ACCENT + ";color:#fff;padding:14px 16px;font-weight:600;display:flex;justify-content:space-between;align-items:center}" +
    ".sb-head button{background:transparent;border:0;color:#fff;font-size:20px;cursor:pointer;line-height:1;padding:4px 8px}" +
    ".sb-log{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;background:#f7f7f8}" +
    ".sb-msg{max-width:85%;padding:9px 12px;border-radius:12px;white-space:pre-wrap;word-wrap:break-word}" +
    ".sb-user{align-self:flex-end;background:" + ACCENT + ";color:#fff;border-bottom-right-radius:4px}" +
    ".sb-bot{align-self:flex-start;background:#fff;border:1px solid #e3e3e6;border-bottom-left-radius:4px}" +
    ".sb-src{display:block;margin-top:6px;font-size:12px;color:#5f5f66}" +
    ".sb-form{display:flex;gap:8px;padding:10px;border-top:1px solid #e3e3e6;background:#fff}" +
    ".sb-form input{flex:1;border:1px solid #cfcfd4;border-radius:8px;padding:9px 10px;font:inherit;min-width:0}" +
    ".sb-form button,.sb-lead button{background:" + ACCENT + ";color:#fff;border:0;border-radius:8px;padding:0 14px;font:inherit;font-weight:600;cursor:pointer;min-height:38px}" +
    ".sb-lead{display:flex;flex-direction:column;gap:6px;margin-top:8px}" +
    ".sb-lead input{border:1px solid #cfcfd4;border-radius:8px;padding:8px 10px;font:inherit}" +
    ".sb-typing{color:#5f5f66;font-style:italic}";
  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  var btn = document.createElement("button");
  btn.className = "sb-btn";
  btn.setAttribute("aria-label", "Open support chat");
  btn.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';

  var panel = document.createElement("div");
  panel.className = "sb-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", TITLE + " chat");
  panel.innerHTML =
    '<div class="sb-head"><span></span><button type="button" aria-label="Close chat">×</button></div>' +
    '<div class="sb-log" aria-live="polite"></div>' +
    '<form class="sb-form"><label for="sb-input" style="position:absolute;left:-9999px">Your message</label>' +
    '<input id="sb-input" autocomplete="off" maxlength="1000" placeholder="Type your question…" />' +
    '<button type="submit">Send</button></form>';
  panel.querySelector(".sb-head span").textContent = TITLE;

  document.body.appendChild(btn);
  document.body.appendChild(panel);

  var log = panel.querySelector(".sb-log");
  var form = panel.querySelector(".sb-form");
  var input = panel.querySelector("#sb-input");
  var greeted = false;

  function add(text, who, sources) {
    var el = document.createElement("div");
    el.className = "sb-msg " + (who === "user" ? "sb-user" : "sb-bot");
    el.textContent = text;
    if (sources && sources.length) {
      var s = document.createElement("span");
      s.className = "sb-src";
      s.textContent = "Source: " + sources.join("; ");
      el.appendChild(s);
    }
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  function leadForm(question) {
    var wrap = add("", "bot");
    wrap.textContent = "";
    var f = document.createElement("form");
    f.className = "sb-lead";
    f.innerHTML =
      '<label>Name<input name="name" required maxlength="200" /></label>' +
      '<label>Email<input name="email" type="email" required maxlength="200" /></label>' +
      '<button type="submit">Send to the team</button>';
    wrap.appendChild(f);
    log.scrollTop = log.scrollHeight;
    f.addEventListener("submit", function (e) {
      e.preventDefault();
      var data = { session_id: SESSION, name: f.name.value, email: f.email.value, question: question };
      fetch(API + "/api/lead", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(data) })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          wrap.textContent = res.ok ? res.j.message : (res.j.detail || "Something went wrong.");
        })
        .catch(function () { wrap.textContent = "Couldn't send - please try again."; });
    });
  }

  function toggle() {
    panel.classList.toggle("open");
    if (panel.classList.contains("open")) {
      if (!greeted) { add(GREETING, "bot"); greeted = true; }
      input.focus();
    }
  }
  btn.addEventListener("click", toggle);
  panel.querySelector(".sb-head button").addEventListener("click", toggle);

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    input.value = "";
    add(text, "user");
    var typing = add("Typing…", "bot");
    typing.classList.add("sb-typing");
    fetch(API + "/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message: text, session_id: SESSION })
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        typing.remove();
        if (!res.ok) { add(res.j.detail || "Something went wrong.", "bot"); return; }
        add(res.j.answer, "bot", res.j.sources);
        if (res.j.handoff) leadForm(text);
      })
      .catch(function () { typing.remove(); add("Connection problem - please try again.", "bot"); });
  });

  // expose for demo pages: window.SupportBot.open()
  window.SupportBot = { open: function () { if (!panel.classList.contains("open")) toggle(); } };
})();
