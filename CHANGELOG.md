# Changelog

## 0.3.1 – 2026-09-07

- Sichere Erstinstallation: Versandlauf und Zeitautomatik sind ausgeschaltet
- Picklisten und Lieferscheine werden nach Installation nicht automatisch gebucht
- GLS bleibt deaktiviert und auf Sandbox, bis ein Administrator bewusst freigibt
- Spätere Migrationen überschreiben bewusst gesetzte Aktivierungswerte nicht

## 0.3.0 – 2026-09-04

- Versandlauf erzeugt zunächst ausschließlich gruppierte Picklisten
- Keine vorzeitigen Lieferscheine bei Fehlbestand oder Korrekturen im Lager
- Lagerbestätigung pro Pickliste mit Paketanzahl und Einzelgewichten
- Lieferscheine werden erst beim Anfordern der GLS-Paketscheine erzeugt und gebucht
- Tatsächlich bestätigte Pickmengen bestimmen Liefer- und Rückstandsmengen
- Gemeinsame GLS-Sendung pro Lieferadresse, aber weiterhin einzelne Lieferscheine pro Auftrag
- Wiederholschutz für bereits verarbeitete Picklisten

## 0.1.0 – 2026-09-04

- Installierbare Frappe/ERPNext-App angelegt
- Gemeinsame GLS-Sendungen für Lieferscheine mit gleicher Firma, Versandadresse und gleichem Versandtag
- Paketanzahl gilt einmal für die gemeinsame Sendung
- Einzelne Paketgewichte und dauerhaft zugeordnete PDF-Labels
- Idempotenzmarker vor externen Label- und Stornoanforderungen
- Einzelstorno und Ersatzlabel bei Gewichtskorrektur
- Sperre bei bereits von GLS gescannten Paketen
- Getrennte und verschlüsselte Sandbox- und Produktivzugänge
- Statusprüfung zweimal täglich und einmaliger Mailversand pro Trackingnummer
