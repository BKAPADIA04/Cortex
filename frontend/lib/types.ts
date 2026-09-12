export type Message = {
  id: number;
  label: "Me" | "Cortex";
  text: string;
  pending?: boolean;
};

export type Thread = {
  id: string;
  title: string;
  messages: Message[];
};
