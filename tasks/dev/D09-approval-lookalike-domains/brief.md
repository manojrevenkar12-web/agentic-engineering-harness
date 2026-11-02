Security bug in agent runs: an email the agent sends to an address at a look-alike domain, such as
`someone@notexample.com` or `someone@example.com.attacker.net`, is treated as internal and goes out
without human approval.

An address counts as internal only when its domain is exactly one of the internal domains (compare
domains case-insensitively). Everything else, subdomains included, needs approval. An email with
several recipients needs approval if any one of them is external.
