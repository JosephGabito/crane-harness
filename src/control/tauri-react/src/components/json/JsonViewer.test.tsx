import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { JsonViewer } from "./JsonViewer";


// JSON presentation
test("highlights JSON semantics and copies the original document", async () => {
  const user = userEvent.setup();
  const writeText = vi.fn(async () => undefined);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText },
  });
  const json = `{
  "message": "Hello.",
  "complete": true,
  "attempt": 1,
  "error": null
}`;

  render(<JsonViewer json={json} label="Thread" />);

  expect(screen.getByText('"message"')).toHaveClass("text-violet-700");
  expect(screen.getByText('"Hello."')).toHaveClass("text-emerald-700");
  expect(screen.getByText("true")).toHaveClass("text-blue-700");
  expect(screen.getByText("1")).toHaveClass("text-amber-700");
  expect(screen.getByText("null")).toHaveClass("text-neutral-500");

  await user.click(screen.getByRole("button", { name: "Copy Thread JSON" }));

  expect(writeText).toHaveBeenCalledWith(json);
});
