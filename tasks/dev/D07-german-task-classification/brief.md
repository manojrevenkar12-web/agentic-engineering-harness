Many of our customers in Germany send requests in German, and the router classifies almost all of
them as `chat`, which sends them to a more expensive route than needed. Teach the rule-based task
classification (`mrp.router.classify`) common German phrasings, in addition to the English ones:

- extraction: "extrahiere", "lies ... aus" (e.g. "Lies die Felder aus"), "als JSON"
- classification: "klassifiziere", "kategorisiere", "ordne ... zu" / "einordnen", "Stimmung"
- code: "schreibe/korrigiere/implementiere eine/die Funktion" (also Klasse, Test, Skript, Abfrage)
- summarization: "fasse ... zusammen", "Zusammenfassung"
- reasoning: "Schritt für Schritt", "berechne", "begründe", "beweise", "warum"

Matching must not depend on case. English classification must not change.
