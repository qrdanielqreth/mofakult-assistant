# Mofakult Assistant

RAG-basierter Knowledge Assistant für Firmendokumente.

## Features

- 💬 Natürlichsprachige Fragen zu Firmendokumenten
- 🔍 Semantische Suche in Google Drive
- 🧠 Konversationsgedächtnis für Folgefragen
- 🎨 Modernes, responsives UI

## Tech Stack

- **Frontend:** Streamlit
- **LLM:** Google Gemini 2.0 Flash (via OpenRouter)
- **Embeddings:** OpenAI text-embedding-3-small
- **Vector Store:** Pinecone
- **Datenquelle:** Google Drive

## Lokale Installation

```bash
# Repository klonen
git clone https://github.com/qrdanielqreth/mofakult-assistant.git
cd mofakult-assistant

# Virtual Environment erstellen
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Dependencies installieren
pip install -r requirements.txt

# Umgebungsvariablen konfigurieren
# Kopiere env.template nach .env und trage API-Keys ein

# App starten
streamlit run app.py
```

## Deployment auf Streamlit Cloud

1. Repository auf GitHub pushen
2. [share.streamlit.io](https://share.streamlit.io) öffnen
3. "New app" → Repository auswählen
4. Secrets in den App Settings konfigurieren

### Required Secrets

```toml
OPENROUTER_API_KEY = "sk-or-v1-..."
OPENAI_API_KEY = "sk-proj-..."
PINECONE_API_KEY = "pcsk_..."
PINECONE_INDEX_NAME = "rag-index"
COMPANY_NAME = "Mofakult"
```

## Lizenz

Proprietär - Alle Rechte vorbehalten
