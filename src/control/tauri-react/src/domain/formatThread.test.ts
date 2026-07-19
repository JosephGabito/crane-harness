import { expect, test } from "vitest";
import { formatThread } from "./formatThread";


// Domain projection
test("formats the complete thread as JSON", () => {
  expect(
    formatThread({
      messages: [
        {
          sender: "user",
          message: "Hello.",
          attachments: [],
        },
        {
          sender: "assistant",
          message: "Hi.",
          attachments: [],
        },
      ],
    }),
  ).toBe(
    `{
  "messages": [
    {
      "sender": "user",
      "message": "Hello.",
      "attachments": []
    },
    {
      "sender": "assistant",
      "message": "Hi.",
      "attachments": []
    }
  ]
}`,
  );
});
