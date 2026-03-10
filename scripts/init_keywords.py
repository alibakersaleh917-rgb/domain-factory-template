#!/usr/bin/env python3
"""Initialize keyword queue with 100 legal-tech German keywords."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

KEYWORDS = [
    "Rechtsanwalt online finden", "Anwalt Erstberatung kostenlos", "Fachanwalt Arbeitsrecht Berlin", "Fachanwalt Mietrecht München", "Scheidungsanwalt Hamburg", "Fachanwalt Verkehrsrecht", "Anwalt Familienrecht", "Rechtsberatung online", "Anwalt Erbrecht", "Fachanwalt Sozialrecht", "Wirtschaftsanwalt", "Anwalt Gesellschaftsrecht", "Strafverteidiger", "Anwalt Baurecht", "Fachanwalt Steuerrecht", "Rechtsanwalt Versicherungsrecht", "Anwalt Handelsrecht", "Fachanwalt IT-Recht", "Anwalt Medizinrecht", "Rechtsanwalt Datenschutz", "Kanzlei Software", "Legal Tech Deutschland", "Anwaltssoftware Vergleich", "Mandantenverwaltung digital", "Kanzleimanagement Software", "Rechtsberatung digital", "Online Anwalt 24h", "Videoberatung Anwalt", "Anwalt Chat Beratung", "Juristische Beratung online", "Arbeitsrecht Abmahnung", "Kündigung Arbeitsrecht", "Aufhebungsvertrag prüfen", "Arbeitszeugnis Anwalt", "Lohnklage Anwalt", "Abfindung berechnen Anwalt", "Betriebsrat Anwalt", "Diskriminierung Arbeitsplatz Anwalt", "Mietminderung Anwalt", "Kündigung Mietverhältnis Anwalt", "Mieterhöhung prüfen Anwalt", "Nebenkostenabrechnung Anwalt", "Räumungsklage Anwalt", "Schönheitsreparaturen Anwalt", "Kaution Rückzahlung Anwalt", "Scheidung online einreichen", "Scheidungskosten Rechner", "Unterhalt berechnen Anwalt", "Sorgerecht Anwalt", "Ehevertrag Anwalt", "Scheidung einvernehmlich Anwalt", "Zugewinnausgleich Anwalt", "Versorgungsausgleich Anwalt", "Umgangsrecht Anwalt", "Testament erstellen Anwalt", "Erbausschlagung Anwalt", "Pflichtteil Anwalt", "Erbstreit Anwalt", "Nachlassverwaltung Anwalt", "Erbschaftssteuer Anwalt", "Vorsorgevollmacht Anwalt", "Patientenverfügung Anwalt", "Verkehrsunfall Anwalt", "Bußgeld Anwalt", "Führerscheinentzug Anwalt", "Fahrverbot Anwalt", "Unfallregulierung Anwalt", "Schmerzensgeld Anwalt", "Verkehrsstrafrecht Anwalt", "MPU Anwalt", "Strafverteidigung Berlin", "Strafverteidigung München", "Betrug Anwalt", "Körperverletzung Anwalt", "Diebstahl Anwalt", "Wirtschaftsstrafrecht Anwalt", "Drogendelikte Anwalt", "Vertragsrecht Anwalt", "Gewährleistung Anwalt", "Schadenersatz Anwalt", "Widerrufsrecht Anwalt", "AGB prüfen Anwalt", "Kaufvertrag Anwalt", "Werkvertrag Anwalt", "Insolvenzanwalt", "Privatinsolvenz Anwalt", "Regelinsolvenz Anwalt", "Forderungsmanagement Anwalt", "Inkasso Abwehr Anwalt", "Verbraucherinsolvenz Anwalt", "Markenrecht Anwalt", "Patent Anwalt", "Urheberrecht Anwalt", "Wettbewerbsrecht Anwalt", "Abmahnung Urheberrecht", "DSGVO Anwalt", "Datenschutz Beratung Anwalt", "Impressum Anwalt", "Social Media Recht Anwalt", "Anwalt Vertragsprüfung online",
]


def init_keywords() -> None:
    keywords_dir = Path("keywords")
    archive_dir = keywords_dir / "archive"
    logs_dir = Path("logs")
    keywords_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    queue_file = keywords_dir / "queue.txt"
    used_file = keywords_dir / "used.txt"
    log_file = logs_dir / "keyword_log.txt"

    queue_file.write_text("\n".join(KEYWORDS) + "\n", encoding="utf-8")
    used_file.touch(exist_ok=True)

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now().isoformat()}] INIT: Loaded {len(KEYWORDS)} keywords into queue\n")

    print(f"Initialized {len(KEYWORDS)} keywords")


if __name__ == "__main__":
    init_keywords()
