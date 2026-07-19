import { JsonViewer } from "../../components/json/JsonViewer";
import { formatThread } from "../../domain/formatThread";
import type { Thread } from "../../domain/thread";


// Domain projection
interface DomainThreadProps {
  thread: Thread;
  sentAt?: Date;
}

export function DomainThread({ thread, sentAt }: DomainThreadProps) {
  return (
    <div className="flex flex-col gap-3">
      <JsonViewer json={formatThread(thread)} label="Thread" />
      {sentAt ? (
        <span className="px-1 text-xs tabular-nums text-muted-foreground">
          {sentAt.toLocaleTimeString([], {
            hour: "numeric",
            minute: "2-digit",
          })}
        </span>
      ) : null}
    </div>
  );
}
