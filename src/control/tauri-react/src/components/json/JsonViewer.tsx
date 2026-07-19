import { useEffect, useMemo, useRef, useState } from "react";
import { CheckIcon, CopyIcon } from "lucide-react";


// JSON tokens
type JsonTokenKind =
  | "boolean"
  | "key"
  | "null"
  | "number"
  | "punctuation"
  | "string";

interface JsonToken {
  kind: JsonTokenKind;
  value: string;
}

const TOKEN_PATTERN =
  /("(?:\\.|[^"\\])*")(?=\s*:)|("(?:\\.|[^"\\])*")|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\b(?:true|false)\b|\bnull\b/g;

const TOKEN_CLASSES: Record<JsonTokenKind, string> = {
  boolean: "text-blue-700",
  key: "text-violet-700",
  null: "text-neutral-500",
  number: "text-amber-700",
  punctuation: "text-neutral-500",
  string: "text-emerald-700",
};

function tokenizeJson(json: string): JsonToken[] {
  const tokens: JsonToken[] = [];
  let cursor = 0;

  for (const match of json.matchAll(TOKEN_PATTERN)) {
    const start = match.index;
    if (start > cursor) {
      tokens.push({
        kind: "punctuation",
        value: json.slice(cursor, start),
      });
    }

    const value = match[0];
    let kind: JsonTokenKind = "number";
    if (match[1]) {
      kind = "key";
    } else if (match[2]) {
      kind = "string";
    } else if (value === "true" || value === "false") {
      kind = "boolean";
    } else if (value === "null") {
      kind = "null";
    }

    tokens.push({ kind, value });
    cursor = start + value.length;
  }

  if (cursor < json.length) {
    tokens.push({
      kind: "punctuation",
      value: json.slice(cursor),
    });
  }

  return tokens;
}


// JSON viewer
interface JsonViewerProps {
  json: string;
  label: string;
}

export function JsonViewer({ json, label }: JsonViewerProps) {
  const [copied, setCopied] = useState(false);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tokens = useMemo(() => tokenizeJson(json), [json]);

  useEffect(
    () => () => {
      if (resetTimer.current) {
        clearTimeout(resetTimer.current);
      }
    },
    [],
  );

  async function handleCopy() {
    await navigator.clipboard?.writeText(json);
    setCopied(true);

    if (resetTimer.current) {
      clearTimeout(resetTimer.current);
    }
    resetTimer.current = setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="overflow-hidden rounded-xl border border-neutral-200 bg-neutral-50">
      <div className="flex h-10 items-center justify-between border-b border-neutral-200 px-3.5">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-neutral-700">{label}</span>
          <span className="rounded bg-neutral-200/70 px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-neutral-500 uppercase">
            JSON
          </span>
        </div>
        <button
          type="button"
          onClick={handleCopy}
          aria-label={`Copy ${label} JSON`}
          className="rounded-md p-1.5 text-neutral-500 transition-colors hover:bg-neutral-200/70 hover:text-neutral-900 focus-visible:outline-2 focus-visible:outline-ring"
        >
          {copied ? (
            <CheckIcon className="size-3.5" />
          ) : (
            <CopyIcon className="size-3.5" />
          )}
        </button>
      </div>
      <pre
        className="max-h-[32rem] overflow-auto px-4 py-3 font-mono text-[13px] leading-5"
        aria-label={`${label} JSON`}
        aria-live="polite"
      >
        <code>
          {tokens.map((token, index) => (
            <span
              className={TOKEN_CLASSES[token.kind]}
              key={`${index}-${token.kind}`}
            >
              {token.value}
            </span>
          ))}
        </code>
      </pre>
    </div>
  );
}
