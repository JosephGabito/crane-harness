// Message domain contract
export interface Message {
  readonly sender: "user" | "assistant";
  readonly message: string;
  readonly attachments: readonly string[];
}
