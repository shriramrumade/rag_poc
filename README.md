# Credit Card Finder — RAG POC

A minimal Retrieval-Augmented Generation (RAG) proof-of-concept that takes a
user's free-text requirement (e.g. *"no annual fee, high cashback on groceries
and online shopping"*) and recommends the best-fitting credit card from a small
curated catalog of Indian credit cards.

## How it works

1. **Catalog**: `data/credit_cards.json` — a hand-written list of ~18 popular
   Indian credit cards with fees, rewards, perks and eligibility.
2. **Indexing**: Each card is flattened into a text document and embedded with
   `sentence-transformers/all-MiniLM-L6-v2` (runs locally, no API needed).
   Embeddings are stored in an in-memory FAISS index.
3. **Retrieval**: The user's query is embedded and the top-K most similar cards
   are pulled from FAISS.
4. **Generation**: The retrieved cards plus the user's query are sent to an
   OpenAI chat model (`gpt-4o-mini` by default), which returns a concise
   grounded recommendation with a top pick, runner-up, and caveats.
5. **UI**: A Streamlit app (`src/app.py`) exposes a text box for the user and
   shows the recommendation alongside the candidate cards that were retrieved.

```
User query ─► embed ─► FAISS top-K ─► prompt (query + cards) ─► LLM ─► answer
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env and put your OPENAI_API_KEY
```

## Run

```bash
streamlit run src/app.py
```

Open the URL Streamlit prints (usually http://localhost:8501), type what you're
looking for and hit **Find my card**.

## Files

- `data/credit_cards.json` — credit card catalog
- `src/rag.py` — embedding, FAISS index and OpenAI generation
- `src/app.py` — Streamlit UI
- `requirements.txt` — Python dependencies

## Extending

- Replace the JSON catalog with a scraped / API-fed list of cards.
- Swap FAISS for a persistent store (Chroma, Qdrant, pgvector) if the catalog
  grows.
- Add metadata filters (e.g. hard-filter by income before retrieval).
- Add evaluation: a small set of (query, expected card) pairs and measure
  top-1 / top-3 accuracy as you change the prompt or embedding model.
