# Let customers create, list and revoke their own API keys

**Requested by:** an enterprise customer's security team (their policy is to rotate keys every
90 days and to revoke a key within minutes when a laptop is lost).

Today a workspace gets exactly one API key, when an admin creates the workspace, and only we can
revoke it (by hand in the database). Customers should manage their keys themselves, authenticated
with any of their current keys.

## API

- `POST /v1/api-keys` creates a new key for the caller's workspace and returns **200** with
  `{"id": "<uuid>", "api_key": "mrp_...", "prefix": "<first 8 characters of the key>"}`. The key is
  shown only in this response; the new key works like the workspace's other keys right away.
- `GET /v1/api-keys` lists the workspace's keys, oldest first, including the one created with the
  workspace and revoked ones. Each item has exactly the fields
  `{"id", "prefix", "created_at", "revoked_at"}` (`revoked_at` is `null` for an active key).
- `DELETE /v1/api-keys/{key_id}` revokes a key: returns **200** with `{"id": "<uuid>", "revoked": true}`;
  from then on requests with that key get 401. A revoked key stays in the listing with its
  `revoked_at` set.
  - A key that does not belong to the caller's workspace, or does not exist: **404** with detail
    `no such key`, and nothing changes.
  - The key used to make the `DELETE` request itself: **409** (so nobody locks themselves out by
    mistake); revoke it with another key.

## Rules

- Like every other secret here: we store only the key's SHA-256 hash, and a key never appears in a
  response other than the creating one, in a log line or in a trace.
- One workspace can never see, use or revoke another workspace's keys.
