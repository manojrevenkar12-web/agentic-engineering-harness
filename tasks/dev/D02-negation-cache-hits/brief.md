Support ticket: a customer asked "Is the EU plan refundable?" and later "Is the EU plan not
refundable?" and got the same cached answer the second time. The same happens with "no" and
"never" ("Does the API have a rate limit?" / "Does the API have no rate limit?").

The semantic cache must never treat a question and its negation as the same request. Repeats that
differ only in greetings, filler words, case or punctuation must still be served from the cache as
they are today.
