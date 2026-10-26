// Mission assistant chat widget. Talks to the Lambda function URL in window.CHAT_API.
// Renders as a floating panel on every page, or inline when #chat-page exists.
(function () {
  const API = window.CHAT_API;
  if (!API) return;
  const KEY = "ltm-chat-history-v1";
  let history = [];
  try { history = JSON.parse(sessionStorage.getItem(KEY) || "[]"); } catch (_) { history = []; }
  const save = () => sessionStorage.setItem(KEY, JSON.stringify(history.slice(-30)));

  const SUGGESTIONS = [
    "How much transponder time per day can the power system support?",
    "Can I work this satellite with a handheld Yagi?",
    "Does the mission meet the FCC 5-year deorbit rule?",
    "What has AMSAT flown the LTM on before, and how did those missions go?",
  ];

  // ---------------------------------------------------------------- minimal safe markdown
  const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  function inline(s) {
    return s
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
      .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+|[a-z0-9_-]+\.html[^\s)]*)\)/gi, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  }
  function md(src) {
    const lines = esc(src).split("\n");
    let out = "", list = null, table = [];
    const flushList = () => { if (list) { out += `</${list}>`; list = null; } };
    const flushTable = () => {
      if (!table.length) return;
      const rows = table.filter((r) => !/^\s*\|?\s*:?-{2,}/.test(r));
      out += '<div class="table-wrap"><table>' + rows.map((r, i) => {
        const cells = r.replace(/^\s*\|/, "").replace(/\|\s*$/, "").split("|");
        const t = i === 0 ? "th" : "td";
        return "<tr>" + cells.map((c) => `<${t}>${inline(c.trim())}</${t}>`).join("") + "</tr>";
      }).join("") + "</table></div>";
      table = [];
    };
    let inCode = false;
    for (const line of lines) {
      if (line.startsWith("```")) { flushList(); flushTable(); out += inCode ? "</code></pre>" : "<pre><code>"; inCode = !inCode; continue; }
      if (inCode) { out += line + "\n"; continue; }
      if (/^\s*\|.*\|\s*$/.test(line)) { flushList(); table.push(line); continue; }
      flushTable();
      let m;
      if ((m = line.match(/^(#{1,4})\s+(.*)/))) { flushList(); out += `<h4>${inline(m[2])}</h4>`; }
      else if ((m = line.match(/^\s*[-*]\s+(.*)/))) { if (list !== "ul") { flushList(); out += "<ul>"; list = "ul"; } out += `<li>${inline(m[1])}</li>`; }
      else if ((m = line.match(/^\s*\d+[.)]\s+(.*)/))) { if (list !== "ol") { flushList(); out += "<ol>"; list = "ol"; } out += `<li>${inline(m[1])}</li>`; }
      else if (!line.trim()) { flushList(); }
      else { flushList(); out += `<p>${inline(line)}</p>`; }
    }
    flushList(); flushTable();
    if (inCode) out += "</code></pre>";
    return out;
  }

  // ---------------------------------------------------------------- DOM
  const inlineHost = document.getElementById("chat-page");
  const root = document.createElement("div");
  root.className = "chat " + (inlineHost ? "chat-inline" : "chat-floating");
  root.innerHTML = `
    <div class="chat-head"><b>Mission assistant</b><span>Claude · answers + research</span>
      <button class="chat-clear" title="Clear conversation">Clear</button>
      ${inlineHost ? "" : '<button class="chat-close" aria-label="Close">×</button>'}</div>
    <div class="chat-log" aria-live="polite"></div>
    <form class="chat-form"><textarea rows="2" maxlength="4000" placeholder="Ask about the mission, the LTM, power, links, debris…" aria-label="Your question"></textarea>
      <button type="submit">Send</button></form>
    <div class="chat-foot">AI-generated; may be wrong. Planning estimates, not flight data. Don't share personal info.</div>`;
  const log = root.querySelector(".chat-log");
  const form = root.querySelector("form");
  const ta = root.querySelector("textarea");

  if (inlineHost) inlineHost.appendChild(root);
  else {
    const fab = document.createElement("button");
    fab.className = "chat-fab";
    fab.innerHTML = "💬 Ask the mission assistant";
    fab.addEventListener("click", () => { root.classList.add("open"); fab.hidden = true; ta.focus(); });
    root.querySelector(".chat-close").addEventListener("click", () => { root.classList.remove("open"); fab.hidden = false; });
    document.body.appendChild(fab);
    document.body.appendChild(root);
  }

  function bubble(role, html, extra) {
    const d = document.createElement("div");
    d.className = "msg " + role;
    d.innerHTML = html;
    if (extra) d.appendChild(extra);
    log.appendChild(d);
    log.scrollTop = log.scrollHeight;
    return d;
  }
  function sourcesEl(sources, activity) {
    if (!(sources && sources.length) && !(activity && activity.length)) return null;
    const det = document.createElement("details");
    det.className = "msg-sources";
    const items = (sources || []).map((u) => `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https:\/\//, ""))}</a></li>`).join("");
    det.innerHTML = `<summary>Research: ${(activity || []).length} tool call${(activity || []).length === 1 ? "" : "s"}${sources && sources.length ? ` · ${sources.length} source${sources.length === 1 ? "" : "s"}` : ""}</summary><ul>${items}</ul>`;
    return det;
  }
  function renderAll() {
    log.innerHTML = "";
    if (!history.length) {
      const intro = bubble("assistant", "<p>Hi! I can answer questions about this CubeSat (the AMSAT LTM payload, power and link budgets, ConOps, debris assessment) and research related topics on amsat.org, GitHub, NASA, FCC and Wikipedia.</p>");
      const sug = document.createElement("div");
      sug.className = "chat-suggest";
      SUGGESTIONS.forEach((s) => { const b = document.createElement("button"); b.type = "button"; b.textContent = s; b.onclick = () => send(s); sug.appendChild(b); });
      intro.appendChild(sug);
    }
    for (const m of history) bubble(m.role, m.role === "user" ? `<p>${esc(m.content)}</p>` : md(m.content), m.role === "assistant" ? sourcesEl(m.sources, m.activity) : null);
  }

  let busy = false;
  async function send(text) {
    text = text.trim();
    if (!text || busy) return;
    busy = true;
    history.push({ role: "user", content: text });
    save(); renderAll();
    ta.value = "";
    const wait = bubble("assistant pending", '<p><span class="dots"><i></i><i></i><i></i></span> Thinking… research questions can take up to a minute.</p>');
    try {
      const r = await fetch(API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history.map(({ role, content }) => ({ role, content })) }),
      });
      const data = await r.json().catch(() => ({}));
      wait.remove();
      if (!r.ok) {
        history.pop();
        bubble("assistant error", `<p>${esc(data.error || `Request failed (${r.status}).`)}</p>`);
        ta.value = text;
      } else {
        history.push({ role: "assistant", content: data.reply, sources: data.sources, activity: data.activity });
        save(); renderAll();
      }
    } catch (e) {
      wait.remove(); history.pop();
      bubble("assistant error", "<p>Network error. Please try again.</p>");
      ta.value = text;
    } finally { busy = false; }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); send(ta.value); });
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(ta.value); } });
  root.querySelector(".chat-clear").addEventListener("click", () => { history = []; save(); renderAll(); });
  renderAll();
})();
