# PDF to JSON Extractor

## 📚 Projektbeschreibung
Dieses Python-Projekt extrahiert Daten aus einer PDF-Datei und konvertiert sie in eine JSON-Datei. Es nutzt gängige Bibliotheken zur PDF-Verarbeitung und strukturiert die extrahierten Informationen in einem leicht weiterverwendbaren JSON-Format.

## 🔧 Installation
### Voraussetzungen
Stelle sicher, dass Python (Version 3.7 oder höher) installiert ist.

### Abhängigkeiten installieren
```sh
pip install -r requirements.txt
```

## 💪 Nutzung
### PDF-Datei verarbeiten
```sh
python main.py input.pdf output.json
```
Dabei:
- `input.pdf` die zu analysierende PDF-Datei ist.
- `output.json` die generierte JSON-Datei sein wird.

## 🎨 Beispiel einer JSON-Ausgabe
```json
{
  "title": "Beispielbericht",
  "author": "Max Mustermann",
  "content": "Hier steht der Inhalt der PDF-Datei..."
}
```

## 🔨 Technologien
- Python
- PyPDF2 
- json (eingebaute Python-Bibliothek)

## 🛠 Anpassungen & Weiterentwicklung
Falls Anpassungen benötigt werden, kannst du die `extractor.py`-Datei editieren, um spezifische Informationen aus der PDF zu extrahieren.

## 🛡 Lizenz
Dieses Projekt steht unter der MIT-Lizenz. Mehr Details findest du in der Datei `LICENSE`.

## 💬 Feedback & Support
Bei Fragen oder Anmerkungen erstelle gerne ein Issue oder einen Pull-Request auf GitHub!



