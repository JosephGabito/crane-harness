import type { Thread } from "./thread";


// Domain projection
export function formatThread(thread: Thread): string {
  return JSON.stringify(thread, null, 2);
}
