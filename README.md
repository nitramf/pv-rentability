# ☀️ PV Profitability – Home Assistant Integration

Eine HACS-kompatible Integration zur Berechnung der **Rentabilität deiner Photovoltaik-Anlage(n)**.

---

## Features

- **Mehrere Anlagen** konfigurierbar (z. B. Hausdach + Carport)
- **Zusatzausgaben** je Anlage (Reparaturen, Wechselrichtertausch, etc.)
- **Jahresabrechnungen** manuell einpflegbar (Stromkosten + Einspeisevergütung)
- **Live-Sensor-Anbindung** – liest erzeugte & eingespeiste kWh direkt aus HA
- **Amortisationsprognose** – berechnet das voraussichtliche Amortisationsjahr
- **Lovelace-Karte** mit interaktiver Amortisationskurve + Prognosekurve

---

## Installation via HACS

1. HACS öffnen → **Integrationen** → drei Punkte → *Benutzerdefiniertes Repository hinzufügen*
2. URL: `https://github.com/YOUR_USER/pv_profitability` · Kategorie: **Integration**
3. Integration installieren, Home Assistant neu starten

### Lovelace-Karte installieren

1. Datei `www/pv-profitability-card.js` liegt nach der Installation unter `/config/www/`
2. HA → Einstellungen → Dashboards → Ressourcen → `+` hinzufügen:
   - URL: `/local/pv-profitability-card.js`
   - Typ: JavaScript-Modul

---

## Konfiguration

### Erste Anlage einrichten

1. **Einstellungen → Geräte & Dienste → + Integration hinzufügen → PV Profitability**
2. Felder ausfüllen:

| Feld | Beschreibung | Beispiel |
|---|---|---|
| Name | Name der Anlage | `Hauptdach` |
| Investitionskosten | Gesamtkosten in € | `12500` |
| Produktions-Sensor | HA-Entity, erzeugte kWh (kumulativ) | `sensor.solaranlage_ertrag_gesamt` |
| Einspeise-Sensor | HA-Entity, eingespeiste kWh | `sensor.solaranlage_einspeisung` |
| Einspeisevergütung | €/kWh | `0.082` |
| Strompreis | €/kWh (für Eigenverbrauchsersparnis) | `0.30` |

### Energie-Dashboard-Sensoren (optional, aber empfohlen)

Diese Felder sind im Options-Flow unter **Anlage verwalten** konfigurierbar. Sie werden automatisch aus dem HA-Energie-Dashboard befüllt und haben **Vorrang** vor den einfachen kWh-Sensoren, da sie Eigenverbrauch und Einspeisung exakter trennen.

| Feld | Beschreibung | Typischer Sensor |
|---|---|---|
| Eigenverbrauch-Sensor | Direkt gemessene selbstverbrauchte kWh | `sensor.solax_self_used_energy` |
| Netzbezug-Sensor | Aus dem Netz bezogene kWh | `sensor.energy_net_consumption` |
| Netzeinspeisung-Sensor | Ins Netz eingespeiste kWh | `sensor.solax_energy_to_grid` |

**Eigenverbrauch-Priorität:**
1. Direkter Eigenverbrauch-Sensor → präziseste Quelle
2. Erzeugt − Netzeinspeisung (beide aus Energie-Dashboard)
3. Erzeugt − Einspeise-Sensor (einfache Sensoren, Fallback)

**Eigenverbrauchsersparnis** = Eigenverbrauch (kWh) × Strompreis (€/kWh)
— dieser Betrag reduziert die Amortisationszeit erheblich und wird
**getrennt von der Einspeisevergütung** ausgewiesen.

### Weitere Anlagen & Ausgaben

Einstellungen → Geräte & Dienste → PV Profitability → **Konfigurieren**:

- **Anlagen verwalten** → Neue Anlage hinzufügen
- **Zusatzausgabe** → Reparaturen, Versicherung etc. einer Anlage zuordnen
- **Jahresabrechnung** → Jährlich eintragen:
  - Jahr
  - Bezogener Strom (€) – Kosten, die *ohne* PV angefallen wären, oder tatsächliche Einsparung
  - Einspeisevergütung (€) – aus der Jahresabrechnung des Netzbetreibers

---

## Sensoren

Nach der Einrichtung stehen folgende Sensoren bereit:

| Sensor | Beschreibung |
|---|---|
| `sensor.pv_gesamtinvestition` | Summe aller Kosten in € |
| `sensor.pv_gesamteinnahmen` | Kumulierte Einnahmen + Ersparnisse in € |
| `sensor.pv_netto_saldo` | Einnahmen minus Investition |
| `sensor.pv_amortisation` | Amortisationsfortschritt in % |
| `sensor.pv_amortisationsjahr` | Voraussichtliches Amortisationsjahr |
| `sensor.pv_verlaufsdaten` | Jahrestimeline als JSON-Attribut (für Karte) |

---

## Lovelace-Karte

```yaml
type: custom:pv-profitability-card
timeline_entity: sensor.pv_verlaufsdaten
investment_entity: sensor.pv_gesamtinvestition
revenue_entity: sensor.pv_gesamteinnahmen
balance_entity: sensor.pv_netto_saldo
percent_entity: sensor.pv_amortisation
year_entity: sensor.pv_amortisationsjahr
```

Die Karte zeigt:
- **4 KPI-Kacheln** (Investition, Einnahmen, Saldo, Amortisationsjahr)
- **Fortschrittsbalken** Amortisationsfortschritt in %
- **Amortisationskurve** (Ist-Werte blau, Prognose orange)
- **Investitions-Linie** (rot gestrichelt)
- **Amortisationspunkt** (grüner Punkt)

---

## Berechnungslogik

```
Gesamtinvestition = Σ (Anlagekosten + Zusatzausgaben)

Einnahmen pro Jahr = Einspeisevergütung (€) + Stromkosteneinsparung (€)

Amortisationsfortschritt = Kumulierte Einnahmen / Gesamtinvestition × 100 %

Prognose = Durchschnitt der letzten 3 Jahre hochgerechnet
```

Bei Sensor-Betrieb (ohne manuelle Jahresabrechnungen):
```
Einspeisevergütung = eingespeiste kWh × Vergütung €/kWh
Eigenverbrauchsersparnis = Eigenverbrauch kWh × Strompreis €/kWh
```

---

## Entwicklung

```bash
# Repository klonen
git clone https://github.com/YOUR_USER/pv_profitability

# Integration nach /config/custom_components/ kopieren
cp -r custom_components/pv_profitability /config/custom_components/

# JS-Karte nach /config/www/ kopieren
cp www/pv-profitability-card.js /config/www/
```

---

## Lizenz

MIT License – freie Nutzung, Änderung und Weitergabe.
