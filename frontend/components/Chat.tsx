"use client";

import { useRef, useState } from "react";
import { renderMarkdown } from "@/lib/markdown";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/chat";
const STREAM_URL = `${API_URL}/stream`;

const SUGGESTIONS = [
  "What can I ask you to do?",
  "Which one of my projects is performing the best?",
  "What projects should I be concerned about right now?",
];

type Message = {
  id: number;
  label: "Me" | "Cortex";
  text: string;
  pending?: boolean;
};

export default function Chat() {
  const [started, setStarted] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const threadId = useRef(crypto.randomUUID());
  const nextId = useRef(0);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;

    setStarted(true);
    setInput("");

    const userId = nextId.current++;
    const pendingId = nextId.current++;

    setMessages((prev) => [
      ...prev,
      { id: userId, label: "Me", text: trimmed },
      { id: pendingId, label: "Cortex", text: "Thinking…", pending: true },
    ]);

    try {
      const res = await fetch(STREAM_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, thread_id: threadId.current }),
      });

      if (!res.ok || !res.body) throw new Error(`Request failed: ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        accumulated += decoder.decode(value, { stream: true });
        setMessages((prev) =>
          prev.map((m) => (m.id === pendingId ? { ...m, text: accumulated, pending: false } : m))
        );
      }
    } catch (err) {
      console.error(err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? { ...m, text: "Something went wrong reaching Cortex. Is the backend running?", pending: false }
            : m
        )
      );
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  return (
    <div className="app">
      <div className="bg-glow" />

      {!started && (
        <div className="intro">
          <img className="logo" src="/logo.svg" alt="Cortex logo" />
          <p className="intro-title">Ask Cortex anything</p>
        </div>
      )}

      <div className="messages">
        {messages.map((m) => (
          <div key={m.id} className={`message-group ${m.label === "Me" ? "from-user" : "from-ai"}`}>
            <p className="message-label">{m.label}</p>
            {m.label === "Me" || m.pending ? (
              <div className={`bubble${m.pending ? " pending" : ""}`}>{m.text}</div>
            ) : (
              <div
                className="bubble"
                dangerouslySetInnerHTML={{ __html: renderMarkdown(m.text) }}
              />
            )}
          </div>
        ))}
      </div>

      {!started && (
        <div className="suggestions">
          <p className="suggestions-label">Suggestions on what to ask Cortex</p>
          <div className="chips">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="chip" onClick={() => sendMessage(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <form className="composer" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask me anything about your projects"
          autoComplete="off"
        />
        <button type="submit" className="send-btn" aria-label="Send">
          <img src="/send.svg" alt="" />
        </button>
      </form>
    </div>
  );
}
