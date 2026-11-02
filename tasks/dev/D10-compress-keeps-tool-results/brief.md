Bug: when a long conversation is compressed (`mrp.cache.compress`), the cut between the condensed
older turns and the kept recent turns can fall between an assistant message that calls tools
(`tool_calls`) and the `tool` messages that answer it. Providers then reject the request because a
tool result has no matching call.

Compression must never separate them: if the kept recent turns would start with `tool` messages,
also keep the assistant message that made those calls (and anything between). System messages and
the rest of the behaviour stay as they are.
