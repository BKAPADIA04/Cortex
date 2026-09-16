export type ToolCall = {
  id: string;
  tool: string;
  input?: unknown;
  output?: string;
  status: "running" | "done";
};

export type Message = {
  id: number;
  label: "Me" | "Cortex";
  text: string;
  pending?: boolean;
  toolCalls?: ToolCall[];
};

export type Thread = {
  id: string;
  title: string;
  messages: Message[];
};
