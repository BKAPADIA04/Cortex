"use client";

import { useEffect, useRef, useState } from "react";
import Sidebar from "@/components/Sidebar";
import Chat from "@/components/Chat";
import type { Thread } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/chat";
const STREAM_URL = `${API_URL}/stream`;
const STORAGE_KEY = "cortex.threads";

function newThread(): Thread {
  return { id: crypto.randomUUID(), title: "New chat", messages: [] };
}

export default function ChatApp() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeId, setActiveId] = useState("");
  const nextId = useRef(0);
  const hydrated = useRef(false);

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
                { id: pendingId, label: "Cortex" as const, text: "Thinking…", pending: true },
              ],
            }
      )
    );

    function updatePending(text: string, pending: boolean) {
      setThreads((prev) =>
        prev.map((t) =>
          t.id !== threadId
            ? t
            : { ...t, messages: t.messages.map((m) => (m.id === pendingId ? { ...m, text, pending } : m)) }
        )
      );
    }

    try {
      const res = await fetch(STREAM_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, thread_id: threadId }),
      });

      if (!res.ok || !res.body) throw new Error(`Request failed: ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        accumulated += decoder.decode(value, { stream: true });
        updatePending(accumulated, false);
      }
    } catch (err) {
      console.error(err);
      updatePending("Something went wrong reaching Cortex. Is the backend running?", false);
    }
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
      <Chat messages={activeThread.messages} started={activeThread.messages.length > 0} onSend={sendMessage} />
    </div>
  );
}
