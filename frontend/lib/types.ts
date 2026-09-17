export type ToolCall = {
  id: string;
  tool: string;
  input?: unknown;
  output?: string;
  status: "running" | "done";
};

export type PendingToolApproval = {
  type: "tool_approval";
  calls: { id: string; tool: string; input: unknown }[];
};

export type PendingRetrievalReview = {
  type: "retrieval_review";
  toolCallId: string;
  chunks: { index: number; source: string; text: string }[];
};

export type PendingInterrupt = PendingToolApproval | PendingRetrievalReview;

export type Message = {
  id: number;
  label: "Me" | "Cortex";
  text: string;
  pending?: boolean;
  toolCalls?: ToolCall[];
  interrupt?: PendingInterrupt;
};

export type Thread = {
  id: string;
  title: string;
  messages: Message[];
};

export type UploadedDocument = {
  id: string;
  filename: string;
  chunks?: number;
  pages?: number | null;
  status: "uploading" | "done" | "error";
  error?: string;
};
