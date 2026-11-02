import pytest

from mrp.router import classify


def m(text):
    return [{"role": "user", "content": text}]


@pytest.mark.parametrize(
    "text,task",
    [
        ("Extrahiere die Rechnungsnummer und den Betrag.", "extraction"),
        ("Lies bitte die Felder aus diesem Formular aus.", "extraction"),
        ("Gib mir die Adresse als JSON.", "extraction"),
        ("Klassifiziere diese Bewertung.", "classification"),
        ("Kategorisiere die folgenden Tickets.", "classification"),
        ("Ordne die E-Mail einer Abteilung zu.", "classification"),
        ("Wie ist die Stimmung in diesem Kommentar?", "classification"),
        ("Schreibe eine Funktion, die Primzahlen findet.", "code"),
        ("Korrigiere die Abfrage, sie liefert zu viele Zeilen.", "code"),
        ("Implementiere die Klasse für den Warenkorb.", "code"),
        ("Fasse das Protokoll in drei Sätzen zusammen.", "summarization"),
        ("Bitte eine kurze Zusammenfassung des Gesprächs.", "summarization"),
        ("Berechne die Rendite Schritt für Schritt.", "reasoning"),
        ("Begründe, warum die Lösung korrekt ist.", "reasoning"),
        ("Warum ist der Himmel blau?", "reasoning"),
        ("Erkläre die Lösung Schritt für Schritt.", "reasoning"),
        ("EXTRAHIERE DIE IBAN.", "extraction"),
        ("Hallo, wie geht es dir?", "chat"),
    ],
)
def test_german_requests(text, task):
    assert classify(m(text)) == task


@pytest.mark.parametrize(
    "text,task",
    [
        ("Extract the fields as JSON", "extraction"),
        ("Classify the sentiment of this review", "classification"),
        ("Summarize this thread", "summarization"),
        ("Prove that the sum is even, step by step", "reasoning"),
        ("hi!", "chat"),
        ("Write a function that reverses a string", "code"),
    ],
)
def test_english_is_unchanged(text, task):
    assert classify(m(text)) == task
