import type { Message } from "./message";


// Python domain representation
function formatPythonString(value: string): string {
  return `'${value
    .replace(/\\/g, "\\\\")
    .replace(/'/g, "\\'")
    .replace(/\r/g, "\\r")
    .replace(/\n/g, "\\n")
    .replace(/\t/g, "\\t")}'`;
}

export function formatAttachments(
  attachments: readonly string[],
): string {
  if (attachments.length === 0) {
    return "()";
  }

  const values = attachments.map(formatPythonString).join(", ");
  const trailingComma = attachments.length === 1 ? "," : "";
  return `(${values}${trailingComma})`;
}

export function formatMessage(message: Message): string {
  return [
    "Message(",
    `sender=${formatPythonString(message.sender)}, `,
    `message=${formatPythonString(message.message)}, `,
    `attachments=${formatAttachments(message.attachments)}`,
    ")",
  ].join("");
}

export { formatPythonString };
