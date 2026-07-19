import type { RuntimeSnapshot } from "./runtimeSnapshot";


// Domain projection
export function formatRuntimeSnapshot(snapshot: RuntimeSnapshot): string {
  return JSON.stringify(snapshot, null, 2);
}
