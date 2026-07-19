import { expect, test } from "vitest";
import { formatMessage } from "./formatMessage";


// Domain projection
test("formats messages like the frozen Python domain", () => {
  expect(
    formatMessage({
      sender: "user",
      message: "It's alive\n",
      attachments: ["notes.txt"],
    }),
  ).toBe(
    "Message(sender='user', message='It\\'s alive\\n', attachments=('notes.txt',))",
  );
});
