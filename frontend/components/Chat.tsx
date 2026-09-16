"use client";

import { useState } from "react";
import { renderMarkdown } from "@/lib/markdown";
import type { Message, ToolCall } from "@/lib/types";

const SUGGESTIONS = [
  "What can I ask you to do?",
  "Which one of my projects is performing the best?",
  "What projects should I be concerned about right now?",
];

const TOOL_LABELS: Record<string, string> = {
  duckduckgo_search: "Searching the web",
  calculator: "Calculating",
};

function toolLabel(tool: string): string {
  return TOOL_LABELS[tool] ?? `Running ${tool}`;
}

function toolQuery(call: ToolCall): string | null {
  if (call.input && typeof call.input === "object") {
    const values = Object.values(call.input as Record<string, unknown>);
    if (values.length && typeof values[0] === "string") return values[0];
  }
  return null;
}

function ToolCallChip({ call }: { call: ToolCall }) {
  const query = toolQuery(call);
  return (
    <div className={`tool-call${call.status === "running" ? " running" : " done"}`}>
      <span className="tool-call-icon" aria-hidden="true">
        {call.status === "running" ? (
          <span className="tool-spinner" />
        ) : (
          <span className="tool-check">✓</span>
        )}
      </span>
      <span className="tool-call-label">
        {toolLabel(call.tool)}
        {query ? `: "${query}"` : ""}
      </span>
    </div>
  );
}

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

            {!!m.toolCalls?.length && (
              <div className="tool-calls">
                {m.toolCalls.map((call) => (
                  <ToolCallChip key={call.id} call={call} />
                ))}
              </div>
            )}

            {m.label === "Me" ? (
              <div className="bubble">{m.text}</div>
            ) : m.pending ? (
              <div className="bubble pending">
                <span className="thinking-dots">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            ) : m.text ? (
              <div
                className="bubble"
                dangerouslySetInnerHTML={{ __html: renderMarkdown(m.text) }}
              />
            ) : null}
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
