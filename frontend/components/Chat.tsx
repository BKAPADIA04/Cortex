"use client";

import { useRef, useState } from "react";
import { renderMarkdown } from "@/lib/markdown";
import InterruptCard from "@/components/InterruptCard";
import type { Message, ToolCall, UploadedDocument } from "@/lib/types";

const SUGGESTIONS = [
  "What can I ask you to do?",
  "Which one of my projects is performing the best?",
  "What projects should I be concerned about right now?",
];

const TOOL_LABELS: Record<string, string> = {
  duckduckgo_search: "Searching the web",
  calculator: "Calculating",
  retrieve_documents: "Searching your documents",
  list_uploaded_documents: "Checking uploaded documents",
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

const ACCEPTED_EXTENSIONS = ".pdf,.docx,.txt";

function DocumentChip({ doc, onRemove }: { doc: UploadedDocument; onRemove: (id: string) => void }) {
  return (
    <div className={`doc-chip doc-chip-${doc.status}`} title={doc.error}>
      <span className="doc-chip-icon" aria-hidden="true">
        {doc.status === "uploading" ? (
          <span className="tool-spinner" />
        ) : doc.status === "error" ? (
          "!"
        ) : (
          <span className="tool-check">✓</span>
        )}
      </span>
      <span className="doc-chip-label">{doc.filename}</span>
      <button
        type="button"
        className="doc-chip-remove"
        aria-label={`Remove ${doc.filename}`}
        onClick={() => onRemove(doc.id)}
      >
        ×
      </button>
    </div>
  );
}

type ChatProps = {
  messages: Message[];
  started: boolean;
  onSend: (text: string) => void;
  documents: UploadedDocument[];
  onUploadFiles: (files: FileList) => void;
  onRemoveDocument: (id: string) => void;
  onResolveInterrupt: (messageId: number, value: unknown) => void;
};

export default function Chat({
  messages,
  started,
  onSend,
  documents,
  onUploadFiles,
  onRemoveDocument,
  onResolveInterrupt,
}: ChatProps) {
  const [input, setInput] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input;
    setInput("");
    onSend(text);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files?.length) onUploadFiles(e.target.files);
    e.target.value = "";
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
            ) : m.interrupt ? (
              <InterruptCard
                interrupt={m.interrupt}
                onApprove={(decisions) => onResolveInterrupt(m.id, { decisions })}
                onReview={(selected) => onResolveInterrupt(m.id, { selected })}
              />
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

      {!!documents.length && (
        <div className="doc-chips">
          {documents.map((doc) => (
            <DocumentChip key={doc.id} doc={doc} onRemove={onRemoveDocument} />
          ))}
        </div>
      )}

      <form className="composer" onSubmit={handleSubmit}>
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          multiple
          className="hidden"
          onChange={handleFileChange}
        />
        <button
          type="button"
          className="attach-btn"
          aria-label="Upload document"
          onClick={() => fileInputRef.current?.click()}
        >
          <img src="/attach.svg" alt="" />
        </button>
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
