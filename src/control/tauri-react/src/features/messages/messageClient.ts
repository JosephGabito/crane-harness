import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import type { Message } from "../../domain/message";
import {
  EMPTY_RUNTIME_SNAPSHOT,
  type RuntimeSnapshot,
} from "../../domain/runtimeSnapshot";


// Application boundary
export interface SendMessageResult {
  readonly accepted: boolean;
  readonly snapshot: RuntimeSnapshot;
}

export type SendMessageCommand = (
  message: Message,
) => Promise<SendMessageResult>;

export interface ClearRuntimeResult {
  readonly cleared: boolean;
  readonly snapshot: RuntimeSnapshot;
}

export type ClearRuntimeCommand = () => Promise<ClearRuntimeResult>;

export interface GetRuntimeResult {
  readonly snapshot: RuntimeSnapshot;
}

export type GetRuntimeSnapshotCommand = () => Promise<GetRuntimeResult>;
export type RuntimeSnapshotSubscriber = (
  subscriber: (snapshot: RuntimeSnapshot) => void,
) => Promise<() => void>;


// Development-only lifecycle
const TEMPORARY_REPLIES = [
  "Interesting. Tell me more.",
  "Got it. What should we do next?",
  "I am only pretending to be intelligent, but I received your message.",
  "The loop is alive.",
] as const;
const FAKE_MODEL_DELAY_MILLISECONDS = 5_000;

let developmentSnapshot = EMPTY_RUNTIME_SNAPSHOT;
let developmentScheduled = false;
const developmentSubscribers = new Set<
  (snapshot: RuntimeSnapshot) => void
>();

function publishDevelopmentSnapshot(snapshot: RuntimeSnapshot) {
  developmentSnapshot = snapshot;
  for (const subscriber of developmentSubscribers) {
    subscriber(snapshot);
  }
}

function scheduleDevelopmentLoop() {
  if (developmentScheduled) {
    return;
  }
  developmentScheduled = true;

  window.setTimeout(() => {
    developmentScheduled = false;
    const snapshot = developmentSnapshot;
    if (snapshot.status === "running" || !snapshot.inbox.messages.length) {
      return;
    }

    const batch = snapshot.inbox.messages;
    const userMessage: Message = {
      sender: "user",
      message: batch.map((message) => message.message.trim()).join(". "),
      attachments: batch.flatMap((message) => message.attachments),
    };
    const runningSnapshot: RuntimeSnapshot = {
      ...snapshot,
      revision: snapshot.revision + 1,
      status: "running",
      inbox: {
        messages: [],
      },
      thread: {
        messages: [...snapshot.thread.messages, userMessage],
      },
    };
    publishDevelopmentSnapshot(runningSnapshot);
    const activeEpoch = runningSnapshot.epoch;

    window.setTimeout(() => {
      if (
        developmentSnapshot.epoch !== activeEpoch ||
        developmentSnapshot.status !== "running"
      ) {
        scheduleDevelopmentLoop();
        return;
      }

      publishDevelopmentSnapshot({
        ...developmentSnapshot,
        revision: developmentSnapshot.revision + 1,
        status: "idle",
        thread: {
          messages: [
            ...developmentSnapshot.thread.messages,
            {
              sender: "assistant",
              message:
                TEMPORARY_REPLIES[
                  Math.floor(Math.random() * TEMPORARY_REPLIES.length)
                ],
              attachments: [],
            },
          ],
        },
      });
      scheduleDevelopmentLoop();
    }, FAKE_MODEL_DELAY_MILLISECONDS);
  }, 0);
}


// Desktop adapter
function isTauriRuntime() {
  return "__TAURI_INTERNALS__" in window;
}

export const sendMessage: SendMessageCommand = async (message) => {
  if (!isTauriRuntime()) {
    if (!import.meta.env.DEV) {
      throw new Error("The desktop runtime is unavailable.");
    }

    const snapshot: RuntimeSnapshot = {
      ...developmentSnapshot,
      revision: developmentSnapshot.revision + 1,
      inbox: {
        messages: [...developmentSnapshot.inbox.messages, message],
      },
    };
    publishDevelopmentSnapshot(snapshot);
    scheduleDevelopmentLoop();
    return {
      accepted: true,
      snapshot,
    };
  }

  return invoke<SendMessageResult>("add_message", { message });
};

export const getRuntimeSnapshot: GetRuntimeSnapshotCommand = async () => {
  if (!isTauriRuntime()) {
    if (!import.meta.env.DEV) {
      throw new Error("The desktop runtime is unavailable.");
    }
    return { snapshot: developmentSnapshot };
  }

  return invoke<GetRuntimeResult>("get_runtime_snapshot");
};

export const clearRuntime: ClearRuntimeCommand = async () => {
  if (!isTauriRuntime()) {
    if (!import.meta.env.DEV) {
      throw new Error("The desktop runtime is unavailable.");
    }

    const snapshot: RuntimeSnapshot = {
      ...EMPTY_RUNTIME_SNAPSHOT,
      epoch: developmentSnapshot.epoch + 1,
    };
    publishDevelopmentSnapshot(snapshot);
    return {
      cleared: true,
      snapshot,
    };
  }

  return invoke<ClearRuntimeResult>("clear_thread");
};

export const subscribeToRuntimeSnapshots: RuntimeSnapshotSubscriber = async (
  subscriber,
) => {
  if (!isTauriRuntime()) {
    if (!import.meta.env.DEV) {
      throw new Error("The desktop runtime is unavailable.");
    }

    developmentSubscribers.add(subscriber);
    return () => developmentSubscribers.delete(subscriber);
  }

  return listen<RuntimeSnapshot>("runtime-snapshot", (event) => {
    subscriber(event.payload);
  });
};
