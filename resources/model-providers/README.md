# Model providers

Crane Harness owns the conversation history.

A model provider does not decide how Crane stores history. The provider only
translates data between Crane and its API.

This rule allows one Thread to work with OpenAI, Anthropic, Gemini, a local
model, or a future provider.

## The boundary

```text
Crane history
    |
    v
Input adapter
    |
    v
Model provider
    |
    v
Output adapter
    |
    v
Crane values
```

Each provider has two adapters:

1. The **input adapter** prepares a provider request.
2. The **output adapter** reads the provider response.

Provider code stays outside the domain.

## Input adapter

The input adapter receives Crane values. It returns a request in the format
required by one provider.

It may:

- change Crane senders into provider roles;
- change attachments into provider content blocks;
- change Crane tools into provider tool definitions;
- add a system instruction to the correct provider field; and
- include private provider data required to continue a run.

The input adapter must not change Crane history.

## Output adapter

The output adapter receives a provider response. It returns values understood
by Crane.

It may translate:

- assistant text;
- tool calls;
- tool results;
- usage information;
- stop reasons;
- provider errors; and
- private continuation data.

The output adapter must not write directly to history. It returns values to an
application use case. The application validates and saves them.

## History

History is the provider-neutral source of truth.

It must:

- keep entries in the correct order;
- work without a model provider;
- survive an application restart;
- support replay and tests; and
- allow a different provider to continue the conversation.

The Crane domain owns the history format.

## Provider state

Some providers return private data that must be sent back later.

Examples include:

- a response or continuation ID;
- an encrypted reasoning value;
- a provider cache key; or
- a provider-specific run identifier.

Crane may store this data as provider state linked to a run. Provider state is
not conversation history.

Another provider does not need to read or understand it.

## Tools

Crane will own the provider-neutral tool definitions and tool lifecycle.

An input adapter changes those definitions into the provider format. An output
adapter changes provider tool calls back into Crane values.

The provider does not execute a tool. It only asks for a tool call. Crane
decides whether the call is valid, whether it needs approval, and when it may
run.

## Errors

Provider errors must cross the adapter boundary as clear Crane values.

Adapters must not hide:

- authentication failures;
- rate limits;
- invalid requests;
- safety rejections;
- network failures; or
- malformed provider responses.

The application decides whether an error may be retried or shown to the user.

## Example

Crane may own this history:

```json
{
  "messages": [
    {
      "sender": "user",
      "message": "Describe this image",
      "attachments": ["photo.png"]
    }
  ]
}
```

An OpenAI adapter may turn it into OpenAI content items. A Gemini adapter may
turn it into Gemini parts. An Anthropic adapter may turn it into Anthropic
content blocks.

Those requests can look different. The Crane history does not change.

## Main rule

> Crane owns history. Providers own translation.

If provider-specific data begins to control the domain, the boundary is in the
wrong place.
