# Testfreigabe 0.3.1

Diese Version ist ausschließlich für `test.erp.brightsteps.at` und die GLS-Sandbox vorgesehen. Sie ist nicht für den Produktivbetrieb freigegeben.

## Vor der Installation

1. ERPNext-, Frappe- und Python-Version der Testinstanz dokumentieren.
2. Vollständige Datenbank- und Dateisicherung erstellen.
3. Wiederherstellung beziehungsweise Deinstallation mit dem Betreiber abstimmen.
4. Prüfen, dass GLS auf `Sandbox` und alle Automatiken auf `Aus` stehen.

## Abnahmereihenfolge

1. App installieren und Migration ausführen.
2. Anmeldung sowie bestehende Verkaufs- und Lagerbelege stichprobenartig prüfen.
3. Versandlauf zunächst nur als Vorschau ausführen.
4. Zwei Testaufträge mit gleicher Versandadresse und einen mit abweichender Adresse anlegen.
5. Gruppierte Picklisten kontrollieren; dabei noch keine GLS-Labels erzeugen.
6. Kommissionierung bestätigen und getrennte Lieferscheine je Auftrag prüfen.
7. Paketanzahl und Einzelgewichte der gemeinsamen GLS-Sendung prüfen.
8. GLS-Sandbox-Labels erzeugen und am Zebra ZD421 drucken.
9. Paket ergänzen, korrigieren und stornieren.
10. Wiederholtes Speichern und Klicken auf doppelte Sendungen prüfen.
11. Statusprüfung und interne Testmail prüfen.
12. Deinstallation beziehungsweise Wiederherstellung einmal auf der Testumgebung erproben.

Jeder Fehler wird mit Ausgangsdaten, erwartetem Ergebnis, tatsächlichem Ergebnis und ERPNext-Fehlerprotokoll dokumentiert. Erst nach Abschluss dieser Liste wird eine Release-Version erstellt.

