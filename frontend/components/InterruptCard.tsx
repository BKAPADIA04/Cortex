"use client";

import { useState } from "react";
import type { PendingInterrupt } from "@/lib/types";

const TOOL_LABELS: Record<string, string> = {
  duckduckgo_search: "Search the web",
  retrieve_documents: "Search your documents",
};

function toolQuery(input: unknown): string | null {
  if (input && typeof input === "object") {
    const values = Object.values(input as Record<string, unknown>);
    if (values.length && typeof values[0] === "string") return values[0];
  }
  return null;
}

type InterruptCardProps = {
  interrupt: PendingInterrupt;
  onApprove: (decisions: Record<string, boolean>) => void;
  onReview: (selected: number[]) => void;
};

export default function InterruptCard({ interrupt, onApprove, onReview }: InterruptCardProps) {
  if (interrupt.type === "tool_approval") {
    return <ToolApprovalCard interrupt={interrupt} onApprove={onApprove} />;
  }
  return <RetrievalReviewCard interrupt={interrupt} onReview={onReview} />;
}

function ToolApprovalCard({
  interrupt,
  onApprove,
}: {
  interrupt: Extract<PendingInterrupt, { type: "tool_approval" }>;
  onApprove: (decisions: Record<string, boolean>) => void;
}) {
  const [decisions, setDecisions] = useState<Record<string, boolean>>(
    Object.fromEntries(interrupt.calls.map((c) => [c.id, true]))
  );
  const [submitted, setSubmitted] = useState(false);

  return (
    <div className="interrupt-card">
      <p className="interrupt-title">Cortex wants to run {interrupt.calls.length > 1 ? "these actions" : "this action"}</p>
      <div className="interrupt-list">
        {interrupt.calls.map((call) => {
          const query = toolQuery(call.input);
          const allowed = decisions[call.id];
          return (
            <div key={call.id} className="interrupt-item">
              <span className="interrupt-item-label">
                {TOOL_LABELS[call.tool] ?? call.tool}
                {query ? `: "${query}"` : ""}
              </span>
              <div className="interrupt-toggle">
                <button
                  type="button"
                  disabled={submitted}
                  className={`interrupt-toggle-btn${allowed ? " active-allow" : ""}`}
                  onClick={() => setDecisions((d) => ({ ...d, [call.id]: true }))}
                >
                  Allow
                </button>
                <button
                  type="button"
                  disabled={submitted}
                  className={`interrupt-toggle-btn${!allowed ? " active-deny" : ""}`}
                  onClick={() => setDecisions((d) => ({ ...d, [call.id]: false }))}
                >
                  Deny
                </button>
              </div>
            </div>
          );
        })}
      </div>
      <button
        type="button"
        className="interrupt-confirm-btn"
        disabled={submitted}
        onClick={() => {
          setSubmitted(true);
          onApprove(decisions);
        }}
      >
        {submitted ? "Sent" : "Confirm"}
      </button>
    </div>
  );
}

function RetrievalReviewCard({
  interrupt,
  onReview,
}: {
  interrupt: Extract<PendingInterrupt, { type: "retrieval_review" }>;
  onReview: (selected: number[]) => void;
}) {
  const [selected, setSelected] = useState<Set<number>>(
    new Set(interrupt.chunks.map((c) => c.index))
  );
  const [submitted, setSubmitted] = useState(false);

  function toggle(index: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  return (
    <div className="interrupt-card">
      <p className="interrupt-title">Review the passages Cortex found before it answers</p>
      <div className="interrupt-list">
        {interrupt.chunks.map((chunk) => (
          <label key={chunk.index} className="review-chunk">
            <input
              type="checkbox"
              checked={selected.has(chunk.index)}
              disabled={submitted}
              onChange={() => toggle(chunk.index)}
            />
            <div className="review-chunk-body">
              <span className="review-chunk-source">{chunk.source}</span>
              <span className="review-chunk-text">{chunk.text}</span>
            </div>
          </label>
        ))}
      </div>
      <button
        type="button"
        className="interrupt-confirm-btn"
        disabled={submitted}
        onClick={() => {
          setSubmitted(true);
          onReview(Array.from(selected));
        }}
      >
        {submitted ? "Sent" : "Use selected passages"}
      </button>
    </div>
  );
}
