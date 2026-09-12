"use client";

import type { Thread } from "@/lib/types";

type SidebarProps = {
  threads: Thread[];
  activeId: string;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
};

export default function Sidebar({ threads, activeId, onSelect, onNewChat, onDelete }: SidebarProps) {
  return (
    <aside className="sidebar">
      <button className="new-chat-btn" onClick={onNewChat}>
        + New chat
      </button>
      <div className="thread-list">
        {threads.map((t) => (
          <div
            key={t.id}
            className={`thread-item${t.id === activeId ? " active" : ""}`}
            onClick={() => onSelect(t.id)}
          >
            <span className="thread-title">{t.title}</span>
            {threads.length > 1 && (
              <button
                className="thread-delete"
                aria-label="Delete chat"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(t.id);
                }}
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}
