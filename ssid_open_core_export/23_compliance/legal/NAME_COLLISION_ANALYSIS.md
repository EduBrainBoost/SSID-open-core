# Name Collision Analysis

## Analyse-Datum: 2026-03-28

## Kollisionspaare

### 1. Self-Sovereign Identity (Konzept) vs. SSID (Projekt)
- **SSI** ist ein generisches Konzept (Decentralized Identity, W3C DID, Verifiable Credentials)
- **SSID** ist ein konkretes Projekt-Akronym: Self-Sovereign Identity Digital
- Abgrenzung: SSID implementiert SSI-Prinzipien, ist aber ein eigenstaendiges System
- Verwechslungsrisiko: Gering, da SSID ein spezifischer Projektname ist

### 2. SSI Digital (anderes Projekt) vs. SSID
- **SSI Digital**: Externes Unternehmen/Projekt im SSI-Oekosystem
- **SSID**: Eigenstaendiges Open-Source-Projekt mit eigener Architektur (24-Root, 16-Shard)
- Abgrenzung: Keine organisatorische, technische oder rechtliche Verbindung
- Verwechslungsrisiko: Mittel, da Namensaehnlichkeit besteht

### 3. SSID-Token auf BSC (fremd) vs. SSID-Token (eigen)
- **Fremder BSC-Token**: BEP-20 Token auf Binance Smart Chain mit SSID-Ticker
- **SSID-Token (eigen)**: Utility/Governance/Reward Token des SSID-Projekts
- Abgrenzung: Keinerlei technische oder vertragliche Verbindung
- Verwechslungsrisiko: Hoch, erfordert aktives Distancing (siehe SSID_TOKEN_DISTANCING.md)

### 4. WLAN-SSID (Service Set Identifier) vs. SSID (Projekt)
- **WLAN-SSID**: IEEE 802.11 Netzwerkkennung
- **SSID (Projekt)**: Self-Sovereign Identity Digital
- Abgrenzung: Voellig unterschiedliche Domaenen (Netzwerktechnik vs. Digital Identity)
- Verwechslungsrisiko: Gering in Fachkreisen, hoch bei Suchmaschinen-Ergebnissen

## Massnahmen
- Token Distancing Statement erstellt und versioniert
- Foreign Token Evidence dokumentiert
- Keine Integration fremder Tokens oder Projekte
- Regelmae Pruefung auf neue Kollisionsquellen empfohlen
