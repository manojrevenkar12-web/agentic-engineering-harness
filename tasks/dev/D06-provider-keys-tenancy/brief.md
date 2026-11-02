Security report from a customer: `GET /v1/provider-keys` lists providers (with key fingerprints)
that were configured by other workspaces, not only their own.

A workspace must only ever see its own provider keys in that listing. Fix it the way this codebase
keeps workspaces apart.
