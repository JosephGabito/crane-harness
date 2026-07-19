import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import { Spinner } from "@/components/ui/spinner";
import { ArrowUpIcon } from "lucide-react";
import { JsonViewer } from "./components/json/JsonViewer";
import { formatRuntimeSnapshot } from "./domain/formatRuntimeSnapshot";
import {
  EMPTY_RUNTIME_SNAPSHOT,
  type RuntimeSnapshot,
} from "./domain/runtimeSnapshot";
import {
  clearRuntime,
  getRuntimeSnapshot,
  sendMessage,
  subscribeToRuntimeSnapshots,
} from "./features/messages/messageClient";
import type {
  ClearRuntimeCommand,
  GetRuntimeSnapshotCommand,
  RuntimeSnapshotSubscriber,
  SendMessageCommand,
} from "./features/messages/messageClient";


// Application contract
interface AppProps {
  sendMessageCommand?: SendMessageCommand;
  clearRuntimeCommand?: ClearRuntimeCommand;
  getRuntimeSnapshotCommand?: GetRuntimeSnapshotCommand;
  runtimeSnapshotSubscriber?: RuntimeSnapshotSubscriber;
}


// Application composition
function App({
  sendMessageCommand = sendMessage,
  clearRuntimeCommand = clearRuntime,
  getRuntimeSnapshotCommand = getRuntimeSnapshot,
  runtimeSnapshotSubscriber = subscribeToRuntimeSnapshots,
}: AppProps) {
  const [draft, setDraft] = useState("");
  const [snapshot, setSnapshot] = useState<RuntimeSnapshot>(
    EMPTY_RUNTIME_SNAPSHOT,
  );
  const [error, setError] = useState<string | null>(null);
  const [pendingCommands, setPendingCommands] = useState(0);
  const commandChain = useRef<Promise<void>>(Promise.resolve());

  useEffect(() => {
    let active = true;
    let unsubscribe: (() => void) | undefined;

    async function connectRuntime() {
      try {
        unsubscribe = await runtimeSnapshotSubscriber((nextSnapshot) => {
          if (active) {
            setSnapshot((current) =>
              selectLatestSnapshot(current, nextSnapshot),
            );
          }
        });
        const result = await getRuntimeSnapshotCommand();
        if (active) {
          setSnapshot((current) =>
            selectLatestSnapshot(current, result.snapshot),
          );
        }
      } catch (cause) {
        if (active) {
          setError(formatError(cause));
        }
      }
    }

    void connectRuntime();
    return () => {
      active = false;
      unsubscribe?.();
    };
  }, [getRuntimeSnapshotCommand, runtimeSnapshotSubscriber]);

  function queueCommand(command: () => Promise<RuntimeSnapshot>) {
    setPendingCommands((count) => count + 1);
    commandChain.current = commandChain.current
      .catch(() => undefined)
      .then(command)
      .then((nextSnapshot) =>
        setSnapshot((current) =>
          selectLatestSnapshot(current, nextSnapshot),
        ),
      )
      .catch((cause) => setError(formatError(cause)))
      .finally(() => setPendingCommands((count) => count - 1));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = draft.trim();
    if (!content) {
      return;
    }

    setDraft("");
    setError(null);

    if (content === "/clear") {
      queueCommand(async () => (await clearRuntimeCommand()).snapshot);
      return;
    }

    queueCommand(
      async () =>
        (
          await sendMessageCommand({
            sender: "user",
            message: content,
            attachments: [],
          })
        ).snapshot,
    );
  }

  return (
    <main className="grid h-svh grid-rows-[minmax(0,1fr)_auto] bg-background text-foreground">
      <section
        className="min-h-0 overflow-auto px-5 py-10 md:px-12 md:py-14"
        aria-label="Runtime domain response"
      >
        <div className="mx-auto w-full max-w-[736px]">
          <JsonViewer
            json={formatRuntimeSnapshot(snapshot)}
            label="Runtime"
          />
        </div>
      </section>

      <footer className="px-4 pb-3 md:px-8">
        <form className="mx-auto max-w-[736px]" onSubmit={handleSubmit}>
          <FieldGroup className="gap-2">
            <Field data-invalid={Boolean(error)}>
              <FieldLabel className="sr-only" htmlFor="message-input">
                Message
              </FieldLabel>
              <InputGroup className="min-h-24 rounded-[28px] border-neutral-200 bg-background shadow-[0_2px_4px_rgba(0,0,0,0.04),0_6px_16px_rgba(0,0,0,0.06)] transition-none has-disabled:bg-background has-disabled:opacity-100 has-[[data-slot=input-group-control]:focus-visible]:border-neutral-300 has-[[data-slot=input-group-control]:focus-visible]:ring-0 dark:border-border dark:has-disabled:bg-background">
                <InputGroupTextarea
                  id="message-input"
                  name="message"
                  autoComplete="off"
                  autoFocus
                  aria-invalid={Boolean(error)}
                  value={draft}
                  onChange={(event) => setDraft(event.currentTarget.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  placeholder="Do anything"
                  className="min-h-12 px-3 pt-4 text-base"
                />
                <InputGroupAddon
                  align="block-end"
                  className="justify-end gap-3 px-2.5 pb-2.5"
                >
                  {pendingCommands > 0 ? (
                    <Spinner className="text-muted-foreground" />
                  ) : null}
                  <InputGroupButton
                    type="submit"
                    variant="default"
                    size="icon-sm"
                    className="rounded-full disabled:opacity-100 disabled:bg-neutral-200 disabled:text-neutral-400 dark:disabled:bg-muted dark:disabled:text-muted-foreground"
                    aria-label="Send message"
                    disabled={!draft.trim()}
                  >
                    <ArrowUpIcon />
                  </InputGroupButton>
                </InputGroupAddon>
              </InputGroup>
              <FieldError>{error}</FieldError>
            </Field>
          </FieldGroup>
        </form>
      </footer>
    </main>
  );
}

function formatError(cause: unknown): string {
  if (cause instanceof Error) {
    return cause.message;
  }
  return typeof cause === "string"
    ? cause
    : "Unable to contact the runtime.";
}

function selectLatestSnapshot(
  current: RuntimeSnapshot,
  incoming: RuntimeSnapshot,
): RuntimeSnapshot {
  if (incoming.epoch !== current.epoch) {
    return incoming.epoch > current.epoch ? incoming : current;
  }
  return incoming.revision >= current.revision ? incoming : current;
}

export default App;
