`GET /v1/usage?month=...` answers HTTP 500 when `month` is not a valid `YYYY-MM` month (for example
`2026-13`, `26-01`, `january` or an empty value). It should answer HTTP 422 with a message saying
the month must be given as YYYY-MM. Valid months behave as today.
