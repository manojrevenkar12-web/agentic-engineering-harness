Clients sometimes send an `Idempotency-Key` header that is empty or very long (whole request bodies
have been seen). Reject unusable keys on `POST /v1/chat/completions` with HTTP 400 and an error of
type `invalid_idempotency_key` before anything is recorded:

- a key that is empty or only whitespace,
- a key longer than 255 characters,
- a key containing characters outside printable ASCII.

Requests without the header, and with ordinary keys, behave as today (including replays).
