const API_URL = "http://localhost:8000/chat";
const THREAD_ID = crypto.randomUUID();

const intro = document.getElementById("intro");
const suggestions = document.getElementById("suggestions");
const messagesEl = document.getElementById("messages");
const composer = document.getElementById("composer");
const input = document.getElementById("input");

let started = false;

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function inlineMarkdown(str) {
  return escapeHtml(str)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*(?!\s)(.+?)(?<!\s)\*(?=[\s).,!?]|$)/g, "$1<em>$2</em>");
}

function renderMarkdown(text) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const html = [];
  let listType = null;

  const closeList = () => {
    if (listType) {
      html.push(listType === "ul" ? "</ul>" : "</ol>");
      listType = null;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      closeList();
      continue;
    }
    if (/^---+$/.test(line)) {
      closeList();
      html.push("<hr>");
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      closeList();
      const level = heading[1].length;
      html.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }
    const ordered = line.match(/^\d+\.\s+(.*)$/);
    if (ordered) {
      if (listType !== "ol") {
        closeList();
        html.push("<ol>");
        listType = "ol";
      }
      html.push(`<li>${inlineMarkdown(ordered[1])}</li>`);
      continue;
    }
    const unordered = line.match(/^[*-]\s+(.*)$/);
    if (unordered) {
      if (listType !== "ul") {
        closeList();
        html.push("<ul>");
        listType = "ul";
      }
      html.push(`<li>${inlineMarkdown(unordered[1])}</li>`);
      continue;
    }

    closeList();
    html.push(`<p>${inlineMarkdown(line)}</p>`);
  }
  closeList();

  return html.join("");
}

function startConversation() {
  if (started) return;
  started = true;
  intro.classList.add("hidden");
  suggestions.classList.add("hidden");
}

function addMessage(label, text, { pending = false } = {}) {
  const group = document.createElement("div");
  group.className = `message-group ${label === "Me" ? "from-user" : "from-ai"}`;

  const labelEl = document.createElement("p");
  labelEl.className = "message-label";
  labelEl.textContent = label;

  const bubble = document.createElement("div");
  bubble.className = "bubble" + (pending ? " pending" : "");
  if (label === "Me" || pending) {
    bubble.textContent = text;
  } else {
    bubble.innerHTML = renderMarkdown(text);
  }

  group.appendChild(labelEl);
  group.appendChild(bubble);
  messagesEl.appendChild(group);
  messagesEl.scrollIntoView({ behavior: "smooth", block: "end" });

  return bubble;
}

async function sendMessage(text) {
  const trimmed = text.trim();
  if (!trimmed) return;

  startConversation();
  addMessage("Me", trimmed);
  input.value = "";

  const pendingBubble = addMessage("Cortex", "Thinking…", { pending: true });

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: trimmed, thread_id: THREAD_ID }),
    });

    if (!res.ok) throw new Error(`Request failed: ${res.status}`);

    const data = await res.json();
    pendingBubble.innerHTML = renderMarkdown(data.response);
    pendingBubble.classList.remove("pending");
  } catch (err) {
    pendingBubble.textContent = "Something went wrong reaching Cortex. Is the backend running?";
    pendingBubble.classList.remove("pending");
    console.error(err);
  }
}

composer.addEventListener("submit", (e) => {
  e.preventDefault();
  sendMessage(input.value);
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => sendMessage(chip.textContent));
});
