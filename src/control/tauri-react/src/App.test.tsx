import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import type { RuntimeSnapshot } from "./domain/runtimeSnapshot";
import App from "./App";


// Test state
const EMPTY_SNAPSHOT: RuntimeSnapshot = {
  epoch: 0,
  revision: 0,
  status: "idle",
  inbox: { messages: [] },
  thread: { messages: [] },
};

function runtimeConnection() {
  let subscriber: ((snapshot: RuntimeSnapshot) => void) | undefined;
  const subscribe = vi.fn(async (callback) => {
    subscriber = callback;
    return vi.fn();
  });
  const getRuntime = vi.fn(async () => ({ snapshot: EMPTY_SNAPSHOT }));

  return {
    getRuntime,
    subscribe,
    publish(snapshot: RuntimeSnapshot) {
      subscriber?.(snapshot);
    },
  };
}


// Message flow
test("queues a message and renders the returned runtime snapshot", async () => {
  const user = userEvent.setup();
  const connection = runtimeConnection();
  const queuedSnapshot: RuntimeSnapshot = {
    ...EMPTY_SNAPSHOT,
    revision: 1,
    inbox: {
      messages: [
        {
          sender: "user",
          message: "Hello, agent.",
          attachments: [],
        },
      ],
    },
  };
  const sendMessage = vi.fn(async () => ({
    accepted: true,
    snapshot: queuedSnapshot,
  }));
  render(
    <App
      sendMessageCommand={sendMessage}
      getRuntimeSnapshotCommand={connection.getRuntime}
      runtimeSnapshotSubscriber={connection.subscribe}
    />,
  );

  const input = screen.getByRole("textbox", { name: "Message" });
  await user.type(input, "Hello, agent.{Enter}");

  expect(sendMessage).toHaveBeenCalledWith({
    sender: "user",
    message: "Hello, agent.",
    attachments: [],
  });
  const runtimeJson = await screen.findByLabelText("Runtime JSON");
  expect(runtimeJson).toHaveTextContent('"inbox"');
  expect(runtimeJson).toHaveTextContent('"Hello, agent."');
  expect(input).toHaveValue("");
});


test("renders pushed AgentLoop snapshots", async () => {
  const connection = runtimeConnection();
  render(
    <App
      getRuntimeSnapshotCommand={connection.getRuntime}
      runtimeSnapshotSubscriber={connection.subscribe}
    />,
  );
  await waitFor(() => expect(connection.subscribe).toHaveBeenCalledOnce());

  await act(async () => {
    connection.publish({
      ...EMPTY_SNAPSHOT,
      revision: 2,
      status: "running",
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
  });

  const runtimeJson = screen.getByLabelText("Runtime JSON");
  expect(runtimeJson).toHaveTextContent('"running"');
  expect(runtimeJson).toHaveTextContent('"A. B. C"');
});


test("accepts multiple submissions while preserving command order", async () => {
  const user = userEvent.setup();
  const connection = runtimeConnection();
  let resolveFirst:
    | ((result: { accepted: true; snapshot: RuntimeSnapshot }) => void)
    | undefined;
  const firstResult = new Promise<{
    accepted: true;
    snapshot: RuntimeSnapshot;
  }>((resolve) => {
    resolveFirst = resolve;
  });
  const sendMessage = vi
    .fn()
    .mockImplementationOnce(() => firstResult)
    .mockResolvedValue({
      accepted: true,
      snapshot: EMPTY_SNAPSHOT,
    });
  render(
    <App
      sendMessageCommand={sendMessage}
      getRuntimeSnapshotCommand={connection.getRuntime}
      runtimeSnapshotSubscriber={connection.subscribe}
    />,
  );

  const input = screen.getByRole("textbox", { name: "Message" });
  await user.type(input, "First{Enter}");
  await user.type(input, "Second{Enter}");

  expect(input).toHaveValue("");
  expect(sendMessage).toHaveBeenCalledTimes(1);
  expect(sendMessage).toHaveBeenNthCalledWith(1, {
    sender: "user",
    message: "First",
    attachments: [],
  });

  await act(async () => {
    resolveFirst?.({ accepted: true, snapshot: EMPTY_SNAPSHOT });
    await firstResult;
  });
  await waitFor(() => expect(sendMessage).toHaveBeenCalledTimes(2));
  expect(sendMessage).toHaveBeenNthCalledWith(2, {
    sender: "user",
    message: "Second",
    attachments: [],
  });
});


test("does not rewind when a stale command snapshot arrives", async () => {
  const user = userEvent.setup();
  const connection = runtimeConnection();
  let resolveSend:
    | ((result: { accepted: true; snapshot: RuntimeSnapshot }) => void)
    | undefined;
  const sendResult = new Promise<{
    accepted: true;
    snapshot: RuntimeSnapshot;
  }>((resolve) => {
    resolveSend = resolve;
  });
  render(
    <App
      sendMessageCommand={() => sendResult}
      getRuntimeSnapshotCommand={connection.getRuntime}
      runtimeSnapshotSubscriber={connection.subscribe}
    />,
  );
  await waitFor(() => expect(connection.subscribe).toHaveBeenCalledOnce());

  await user.type(
    screen.getByRole("textbox", { name: "Message" }),
    "Hello{Enter}",
  );
  await act(async () => {
    connection.publish({
      ...EMPTY_SNAPSHOT,
      revision: 3,
      thread: {
        messages: [
          {
            sender: "user",
            message: "Hello",
            attachments: [],
          },
          {
            sender: "assistant",
            message: "Done",
            attachments: [],
          },
        ],
      },
    });
    resolveSend?.({
      accepted: true,
      snapshot: {
        ...EMPTY_SNAPSHOT,
        revision: 1,
        inbox: {
          messages: [
            {
              sender: "user",
              message: "Hello",
              attachments: [],
            },
          ],
        },
      },
    });
    await sendResult;
  });

  const runtimeJson = screen.getByLabelText("Runtime JSON");
  expect(runtimeJson).toHaveTextContent('"revision": 3');
  expect(runtimeJson).toHaveTextContent('"Done"');
});


test("displays a runtime error without blocking later composition", async () => {
  const user = userEvent.setup();
  const connection = runtimeConnection();
  const sendMessage = vi.fn(async () => {
    throw new Error("Runtime unavailable");
  });
  render(
    <App
      sendMessageCommand={sendMessage}
      getRuntimeSnapshotCommand={connection.getRuntime}
      runtimeSnapshotSubscriber={connection.subscribe}
    />,
  );

  const input = screen.getByRole("textbox", { name: "Message" });
  await user.type(input, "First attempt{Enter}");

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Runtime unavailable",
  );
  await user.type(input, "Still available");
  expect(input).toHaveValue("Still available");
});


test("clears Inbox and Thread with the /clear command", async () => {
  const user = userEvent.setup();
  const connection = runtimeConnection();
  const clearedSnapshot: RuntimeSnapshot = {
    ...EMPTY_SNAPSHOT,
    epoch: 1,
  };
  const clearRuntime = vi.fn(async () => ({
    cleared: true,
    snapshot: clearedSnapshot,
  }));
  render(
    <App
      clearRuntimeCommand={clearRuntime}
      getRuntimeSnapshotCommand={connection.getRuntime}
      runtimeSnapshotSubscriber={connection.subscribe}
    />,
  );

  const input = screen.getByRole("textbox", { name: "Message" });
  await user.type(input, "/clear{Enter}");

  expect(clearRuntime).toHaveBeenCalledOnce();
  await waitFor(() =>
    expect(screen.getByLabelText("Runtime JSON")).toHaveTextContent(
      '"epoch": 1',
    ),
  );
});
