import { expect, test } from "vitest";
import { formatRuntimeSnapshot } from "./formatRuntimeSnapshot";


// Domain projection
test("formats the complete runtime as readable JSON", () => {
  const formatted = formatRuntimeSnapshot({
    epoch: 2,
    revision: 7,
    status: "running",
    inbox: {
      messages: [],
    },
    thread: {
      messages: [
        {
          sender: "user",
          message: "A. B. C",
          attachments: [],
        },
      ],
    },
  });

  expect(formatted).toContain('"epoch": 2');
  expect(formatted).toContain('"revision": 7');
  expect(formatted).toContain('"status": "running"');
  expect(formatted).toContain('"inbox"');
  expect(formatted).toContain('"thread"');
  expect(formatted).toContain('"A. B. C"');
});
