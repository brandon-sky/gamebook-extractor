# Basis-Image mit Python 3.12 (leichtgewichtiges Image)
FROM python:3.12-slim

# Setze das Arbeitsverzeichnis im Container
WORKDIR /app

# Kopiere die Poetry-Dateien zuerst, um Layer-Caching zu optimieren
COPY pyproject.toml poetry.lock ./

# Installiere Poetry
RUN pip install --no-cache-dir poetry

# Stelle sicher, dass Poetry das virtuelle Environment im Container verwendet
RUN poetry config virtualenvs.create false

# Installiere Poetry
RUN pip install --no-cache-dir poetry

# Installiere die Abhängigkeiten
RUN poetry install --no-root --no-interaction --no-ansi


# Kopiere den gesamten Code inklusive der Streamlit-Config
COPY src/ ./src
# COPY .streamlit/ ./.streamlit

# Setze den Port für Streamlit
EXPOSE 8501

# Befehl zum Starten der Streamlit-App mit der Config
CMD ["poetry", "run", "streamlit", "run", "src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]