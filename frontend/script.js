const API_URL = "http://localhost:8000/chat";
const THREAD_ID = crypto.randomUUID();

const intro = document.getElementById("intro");
const suggestions = document.getElementById("suggestions");
const messagesEl = document.getElementById("messages");
const composer = document.getElementById("composer");
const input = document.getElementById("input");

let started = false;

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
  bubble.textContent = text;

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
    pendingBubble.textContent = data.response;
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
