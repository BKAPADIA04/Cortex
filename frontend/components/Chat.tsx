"use client";

import { useState } from "react";
import { renderMarkdown } from "@/lib/markdown";
import type { Message } from "@/lib/types";

const SUGGESTIONS = [
  "What can I ask you to do?",
  "Which one of my projects is performing the best?",
  "What projects should I be concerned about right now?",
];

type ChatProps = {
  messages: Message[];
  started: boolean;
  onSend: (text: string) => void;
};

export default function Chat({ messages, started, onSend }: ChatProps) {
  const [input, setInput] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input;
    setInput("");
    onSend(text);
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
              <button key={s} className="chip" onClick={() => onSend(s)}>
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
