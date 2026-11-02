# Streamed answers sometimes contain two different answers glued together

**Reported by:** customer support (two tickets from the same customer this week)

A customer streams answers (`"stream": true`) into their chat widget. Twice this week a user saw an
answer that starts in one voice, stops mid-sentence and then starts over with a complete, different
answer, ending normally. Our provider dashboard shows that each time the first model's connection
was reset after it had already sent some text, and the gateway then streamed the whole answer of a
fallback model into the same response. Every chunk carries its `model`, and the chunks of these
responses name two different models.

Falling back is right when a model fails before it has said anything. Once the client has received
part of an answer, another model's answer must never be added to it: the client cannot tell where one
ends and the other begins.

## Expected

- Before the first content chunk is sent, a failing model is still replaced by the next fallback,
  exactly as today.
- After the first content chunk has been sent, a failure of that model ends the stream: no other
  model is called, the last event is
  `data: {"error": {"type": "provider_error", "message": "<the provider's error>"}}` (the only
  error event in the response), and no `data: [DONE]` is sent. All content chunks in the response come from that one model.
- The request is settled as `cancelled` in `mrp.usage` (as for a client that went away mid-stream),
  and only the call that was actually made is in `mrp.provider_calls`.
