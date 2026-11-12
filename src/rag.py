"""RAG pipeline for credit card recommendation.

Loads a small catalog of credit cards, indexes them with a local
sentence-transformers model into FAISS, retrieves the top-K matches
for a user's free-text requirement, and asks an OpenAI chat model to
produce a grounded recommendation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
from openai import OpenAI
from sentence_transformers import SentenceTransformer

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "credit_cards.json"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


@dataclass
class CreditCard:
    raw: dict

    @property
    def name(self) -> str:
        return self.raw["name"]

    def to_document(self) -> str:
        """Flatten a card into a single text blob used for embeddings."""
        fields = [
            f"Name: {self.raw.get('name', '')}",
            f"Issuer: {self.raw.get('issuer', '')}",
            f"Network: {self.raw.get('network', '')}",
            f"Annual fee (INR): {self.raw.get('annual_fee_inr', '')}",
            f"Joining fee (INR): {self.raw.get('joining_fee_inr', '')}",
            f"Fee waiver: {self.raw.get('fee_waiver', '')}",
            f"Rewards: {self.raw.get('rewards', '')}",
            f"Best for: {self.raw.get('best_for', '')}",
            f"Perks: {self.raw.get('perks', '')}",
            f"Income requirement: {self.raw.get('income_requirement', '')}",
            f"Credit score: {self.raw.get('credit_score', '')}",
            f"Foreign transaction fee: {self.raw.get('foreign_transaction_fee', '')}",
        ]
        return "\n".join(fields)


def load_cards(path: Path = DATA_PATH) -> list[CreditCard]:
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return [CreditCard(item) for item in raw]


class CreditCardRAG:
    def __init__(self, cards: list[CreditCard] | None = None) -> None:
        self.cards = cards or load_cards()
        self._embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
        documents = [card.to_document() for card in self.cards]
        embeddings = self._embedder.encode(
            documents, convert_to_numpy=True, normalize_embeddings=True
        ).astype("float32")
        self._index = faiss.IndexFlatIP(embeddings.shape[1])
        self._index.add(embeddings)

    def retrieve(self, query: str, k: int = 4) -> list[tuple[CreditCard, float]]:
        query_vec = self._embedder.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True
        ).astype("float32")
        scores, idxs = self._index.search(query_vec, k)
        results: list[tuple[CreditCard, float]] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            results.append((self.cards[int(idx)], float(score)))
        return results

    def recommend(
        self,
        query: str,
        k: int = 4,
        client: OpenAI | None = None,
    ) -> tuple[str, list[tuple[CreditCard, float]]]:
        retrieved = self.retrieve(query, k=k)
        context = "\n\n---\n\n".join(card.to_document() for card, _ in retrieved)

        system = (
            "You are a helpful Indian credit-card advisor. Recommend the single "
            "best-fitting card for the user's stated needs from ONLY the cards in "
            "the context. If multiple cards fit, rank them and explain trade-offs. "
            "Be concise, cite card names exactly, and call out annual fee, key "
            "rewards and any eligibility concerns. If no card in the context fits, "
            "say so honestly."
        )
        user = (
            f"User requirement:\n{query}\n\n"
            f"Candidate cards:\n{context}\n\n"
            "Respond with: 1) top pick and why, 2) runner-up if relevant, "
            "3) any caveats (fees, eligibility, caps)."
        )

        client = client or OpenAI()
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        answer = completion.choices[0].message.content or ""
        return answer, retrieved
