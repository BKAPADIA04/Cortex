"use client";

import { useEffect, useRef, useState } from "react";
import Sidebar from "@/components/Sidebar";
import Chat from "@/components/Chat";
import ConfirmDialog from "@/components/ConfirmDialog";
import type { Message, PendingInterrupt, Thread, ToolCall, UploadedDocument } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/chat";
const STREAM_URL = `${API_URL}/stream`;
const RESUME_URL = `${API_URL}/resume`;
const API_ROOT = API_URL.replace(/\/chat$/, "");
const DOCUMENTS_URL = `${API_ROOT}/documents`;
const STORAGE_KEY = "cortex.threads";

function newThread(): Thread {
  return { id: crypto.randomUUID(), title: "New chat", messages: [] };
}

export default function ChatApp() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeId, setActiveId] = useState("");
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [docPendingDelete, setDocPendingDelete] = useState<UploadedDocument | null>(null);
  const nextId = useRef(0);
  const hydrated = useRef(false);

  useEffect(() => {
    fetch(DOCUMENTS_URL)
      .then((res) => (res.ok ? res.json() : []))
      .then((docs: { doc_id: string; filename: string; chunks: number }[]) => {
        setDocuments(docs.map((d) => ({ id: d.doc_id, filename: d.filename, chunks: d.chunks, status: "done" as const })));
      })
      .catch(() => {});
  }, []);

  async function handleUploadFiles(files: FileList) {
    for (const file of Array.from(files)) {
      const tempId = crypto.randomUUID();
      setDocuments((prev) => [...prev, { id: tempId, filename: file.name, status: "uploading" }]);

      try {
        const formData = new FormData();
        formData.append("file", file);
        const res = await fetch(DOCUMENTS_URL, { method: "POST", body: formData });
        const body = await res.json().catch(() => ({}));

        if (!res.ok) throw new Error(body.detail || `Upload failed: ${res.status}`);

        setDocuments((prev) =>
          prev.map((d) =>
            d.id === tempId
              ? { id: body.doc_id, filename: body.filename, chunks: body.chunks, pages: body.pages, status: "done" }
              : d
          )
        );
      } catch (err) {
        setDocuments((prev) =>
          prev.map((d) =>
            d.id === tempId ? { ...d, status: "error", error: (err as Error).message } : d
          )
        );
      }
    }
  }

  function handleRequestRemoveDocument(doc: UploadedDocument) {
    setDocPendingDelete(doc);
  }

  async function confirmRemoveDocument() {
    const doc = docPendingDelete;
    if (!doc) return;
    setDocPendingDelete(null);
    setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
    try {
      await fetch(`${DOCUMENTS_URL}/${doc.id}`, { method: "DELETE" });
    } catch {
      // Best-effort — the doc chip is already gone from the UI either way.
    }
  }

  useEffect(() => {
    let initial: Thread[] = [];
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) initial = JSON.parse(raw);
    } catch {
      initial = [];
    }
    if (initial.length === 0) initial = [newThread()];

    let maxId = 0;
    for (const t of initial) for (const m of t.messages) maxId = Math.max(maxId, m.id + 1);
    nextId.current = maxId;

    setThreads(initial);
    setActiveId(initial[0].id);
    hydrated.current = true;
  }, []);

  useEffect(() => {
    if (!hydrated.current) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(threads));
  }, [threads]);

  const activeThread = threads.find((t) => t.id === activeId);

  function handleNewChat() {
    const thread = newThread();
    setThreads((prev) => [thread, ...prev]);
    setActiveId(thread.id);
  }

  function handleDelete(id: string) {
    setThreads((prev) => {
      const remaining = prev.filter((t) => t.id !== id);
      const next = remaining.length ? remaining : [newThread()];
      if (id === activeId) setActiveId(next[0].id);
      return next;
    });
  }

  async function consumeStream(res: Response, threadId: string, pendingId: number) {
    function updatePendingMessage(updater: (m: Message) => Message) {
      setThreads((prev) =>
        prev.map((t) =>
          t.id !== threadId
            ? t
            : { ...t, messages: t.messages.map((m) => (m.id === pendingId ? updater(m) : m)) }
        )
      );
    }

    function appendToken(content: string) {
      updatePendingMessage((m) => ({ ...m, text: m.text + content, pending: false }));
    }

    function startTool(call: ToolCall) {
      updatePendingMessage((m) => ({ ...m, toolCalls: [...(m.toolCalls ?? []), call], pending: false }));
    }

    function finishTool(id: string, output: string) {
      updatePendingMessage((m) => ({
        ...m,
        toolCalls: (m.toolCalls ?? []).map((tc) =>
          tc.id === id ? { ...tc, status: "done" as const, output } : tc
        ),
      }));
    }

    function setInterrupt(interrupt: PendingInterrupt | undefined) {
      updatePendingMessage((m) => ({ ...m, interrupt, pending: false }));
    }

    try {
      if (!res.ok || !res.body) throw new Error(`Request failed: ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let interrupted = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.trim()) continue;
          const event = JSON.parse(line);
          if (event.type === "token") {
            appendToken(event.content);
          } else if (event.type === "tool_start") {
            startTool({ id: event.id, tool: event.tool, input: event.input, status: "running" });
          } else if (event.type === "tool_end") {
            finishTool(event.id, event.output);
          } else if (event.type === "interrupt") {
            interrupted = true;
            setInterrupt(
              event.payload.type === "tool_approval"
                ? { type: "tool_approval", calls: event.payload.calls }
                : {
                    type: "retrieval_review",
                    toolCallId: event.payload.tool_call_id,
                    chunks: event.payload.chunks,
                  }
            );
          }
        }
      }

      if (!interrupted) updatePendingMessage((m) => ({ ...m, pending: false }));
    } catch (err) {
      console.error(err);
      updatePendingMessage((m) => ({
        ...m,
        text: "Something went wrong reaching Cortex. Is the backend running?",
        pending: false,
      }));
    }
  }

  async function resolveInterrupt(threadId: string, pendingId: number, value: unknown) {
    setThreads((prev) =>
      prev.map((t) =>
        t.id !== threadId
          ? t
          : {
              ...t,
              messages: t.messages.map((m) =>
                m.id === pendingId ? { ...m, interrupt: undefined, pending: true } : m
              ),
            }
      )
    );

    const res = await fetch(RESUME_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread_id: threadId, value }),
    });
    await consumeStream(res, threadId, pendingId);
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || !activeThread) return;

    const threadId = activeThread.id;
    const isFirstMessage = activeThread.messages.length === 0;
    const userId = nextId.current++;
    const pendingId = nextId.current++;

    setThreads((prev) =>
      prev.map((t) =>
        t.id !== threadId
          ? t
          : {
              ...t,
              title: isFirstMessage ? trimmed.slice(0, 40) : t.title,
              messages: [
                ...t.messages,
                { id: userId, label: "Me" as const, text: trimmed },
                { id: pendingId, label: "Cortex" as const, text: "", pending: true, toolCalls: [] },
              ],
            }
      )
    );

    const res = await fetch(STREAM_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: trimmed, thread_id: threadId }),
    });
    await consumeStream(res, threadId, pendingId);
  }

  if (!activeThread) return null;

  return (
    <div className="shell">
      <Sidebar
        threads={threads}
        activeId={activeId}
        onSelect={setActiveId}
        onNewChat={handleNewChat}
        onDelete={handleDelete}
      />
      <Chat
        messages={activeThread.messages}
        started={activeThread.messages.length > 0}
        onSend={sendMessage}
        documents={documents}
        onUploadFiles={handleUploadFiles}
        onRemoveDocument={handleRequestRemoveDocument}
        onResolveInterrupt={(messageId, value) => resolveInterrupt(activeThread.id, messageId, value)}
      />
      {docPendingDelete && (
        <ConfirmDialog
          title={`Delete "${docPendingDelete.filename}"?`}
          description="This removes it and its indexed chunks permanently — Cortex won't be able to search it anymore."
          confirmLabel="Delete"
          danger
          onConfirm={confirmRemoveDocument}
          onCancel={() => setDocPendingDelete(null)}
        />
      )}
    </div>
  );
}
