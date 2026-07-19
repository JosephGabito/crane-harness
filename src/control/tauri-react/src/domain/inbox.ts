import type { Message } from "./message";


// Domain model
export interface Inbox {
  readonly messages: readonly Message[];
}
