import type { Inbox } from "./inbox";
import type { Thread } from "./thread";


// Domain model
export interface RuntimeSnapshot {
  readonly epoch: number;
  readonly revision: number;
  readonly status: "idle" | "running";
  readonly inbox: Inbox;
  readonly thread: Thread;
}

export const EMPTY_RUNTIME_SNAPSHOT: RuntimeSnapshot = {
  epoch: 0,
  revision: 0,
  status: "idle",
  inbox: {
    messages: [],
  },
  thread: {
    messages: [],
  },
};
