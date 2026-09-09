# Bright Steps GLS

> **Entwicklungsstand 0.3.1:** ausschließlich zur Installation auf `test.erp.brightsteps.at` und für GLS-Sandbox-Tests. Keine Produktivfreigabe.

## Versandablauf

Der manuelle oder tägliche Versandlauf erzeugt zunächst ausschließlich nach Lieferadresse gruppierte Picklisten. Gleiche Artikel werden dabei für die Kommissionierung zusammengefasst. Noch nicht verfügbare Mengen bleiben im Auftrag offen; es entstehen zu diesem Zeitpunkt keine Lieferscheine.

Nach der Kommissionierung bestätigt das Lager im Versandlauf die jeweilige Pickliste und gibt Paketanzahl sowie Gewichte ein. Erst dieser Schritt erzeugt und bucht je Auftrag einen eigenen Lieferschein, speichert den Rückstands-Snapshot und erstellt anschließend eine gemeinsame GLS-Sendung für dieselbe Lieferadresse. Bereits verarbeitete Picklisten werden nicht erneut angeboten.

Installierbare ERPNext-App für GLS ShipIT. Sie ersetzt die während der Erprobung direkt in ERPNext angelegten Client- und Serverskripte.

## Versandlauf (ab Version 0.2)

Die App enthält zusätzlich einen regelgesteuerten Versandlauf für ERPNext 16:

- gemeinsame Pickliste je normalisierter Lieferadresse; gleiche Artikel werden im Ausdruck summiert,
- weiterhin ein eigener Lieferschein pro Auftrag,
- Picklisten werden vollständig vor den Lieferscheinen erzeugt,
- Endkunden nur als Gesamtlieferung,
- Kindergarten vollständig sofort, sonst nach fünf Werktagen,
- Teillieferung für andere Gruppen ab 150 EUR verfügbarem Netto-Warenwert je Lieferadresse,
- vollständig lieferbare Aufträge unabhängig vom Mindestwert,
- Rückstände als unveränderlicher Snapshot am Lieferschein,
- täglicher Rückstandsmonitor mit Ampel, Fehlartikeln und Zurückstellungsgrund,
- optionaler automatischer Lauf täglich um 07:00 Uhr.

Die TEST-Ausgabe ist für eine vollständige Abnahme konfiguriert: Automatik sowie das Buchen von Picklisten und Lieferscheinen sind eingeschaltet. In **Shipping Run Settings** stehen zusätzlich die Schaltflächen für Vorschau und manuellen Lauf.

## Geschäftsablauf

1. Im Lieferschein wird die GLS-Paketanzahl eingetragen.
2. Die App sucht eine offene GLS-Sendung mit derselben Firma, demselben Versandtag und exakt derselben normalisierten Versandadresse.
3. Passende Lieferscheine werden derselben GLS-Sendung zugeordnet. Die Paketanzahl gilt für die **gesamte gemeinsame Sendung** und wird nicht je Lieferschein addiert.
4. Das Lager trägt in der GLS-Sendung für jedes physische Paket ein Gewicht ein.
5. Nach der Erstellung speichert die App jede Trackingnummer und jedes PDF als eigenes Paket. Bereits vorhandene Paketscheine bleiben beim Ergänzen bestehen.
6. Ein einzelnes Paket kann storniert oder mit korrigiertem Gewicht neu erstellt werden. Bei der GLS-Antwort `SCANNED` bleibt das bestehende Label erhalten.
7. Um 12:00 und 18:00 Uhr prüft ERPNext den GLS-Status. In der Sandbox gehen Testmails ausschließlich an die in den GLS-Einstellungen hinterlegte interne Adresse.

Eine Sendung wird nicht mehr für neue Lieferscheine verwendet, sobald GLS-Labels erstellt oder Pakete übernommen wurden. Dadurch kann eine später erstellte Lieferung an dieselbe Adresse nicht versehentlich an einen bereits laufenden Versand angehängt werden.

## Installation durch den ERPNext-Betreiber

```bash
cd /path/to/frappe-bench
bench get-app /path/or/git/url/brightsteps_gls
bench --site test.erp.brightsteps.at install-app brightsteps_gls
bench --site test.erp.brightsteps.at migrate
bench build --app brightsteps_gls
bench restart
```

Danach unter **GLS Settings** zunächst `Sandbox` wählen und Client ID, Client Secret sowie GLS-Testkundennummer eintragen. Die Installation deaktiviert die exakt benannten alten GLS-Testskripte automatisch, löscht sie aber nicht. Vor der Produktionsinstallation müssen Backup, GLS-Freigabe und ein vollständiger Abnahmetest erfolgen.

## Update

```bash
cd /path/to/frappe-bench
bench update --reset
bench --site SITE migrate
bench build --app brightsteps_gls
bench restart
```

Die App verwendet DocTypes, Hooks und Patches von Frappe. Es sind keine manuellen Änderungen an ERPNext-Core-Dateien erforderlich.

## Migration des bisherigen Prototyps

Die bestehenden Sandbox-Dateien und Trackingnummern werden nicht automatisch in Produktivdaten umgewandelt. Vor der Installation werden die drei alten Server Scripts und das alte Client Script deaktiviert. Ein separater Migrationslauf übernimmt bei Bedarf ausschließlich eindeutig zuordenbare Sandbox-Datensätze. Unklare oder ältere Labels bleiben als Anhänge erhalten und werden als manuell zu prüfen markiert.
