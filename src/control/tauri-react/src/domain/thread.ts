import type { Message } from "./message";


// Domain model
export interface Thread {
  readonly messages: readonly Message[];
}
