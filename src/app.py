"""Streamlit UI for the credit card recommender RAG POC."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from rag import CreditCardRAG

load_dotenv()

st.set_page_config(page_title="Credit Card Finder (RAG POC)", page_icon="💳")

st.title("💳 Credit Card Finder")
st.caption(
    "POC: tell me what you want in a credit card and I'll pick the best fit "
    "from a small Indian credit-card catalog using RAG (FAISS + OpenAI)."
)


@st.cache_resource(show_spinner="Indexing credit card catalog...")
def get_rag() -> CreditCardRAG:
    return CreditCardRAG()


if not os.getenv("OPENAI_API_KEY"):
    st.warning(
        "OPENAI_API_KEY is not set. Put it in a `.env` file or export it before "
        "running `streamlit run src/app.py`."
    )

rag = get_rag()

with st.form("query_form"):
    query = st.text_area(
        "Describe what you're looking for",
        placeholder=(
            "e.g. I want a card with no annual fee, high cashback on groceries "
            "and online shopping, and some airport lounge access."
        ),
        height=120,
    )
    k = st.slider("How many candidate cards to consider", 2, 8, 4)
    submitted = st.form_submit_button("Find my card")

if submitted:
    if not query.strip():
        st.error("Please describe what you're looking for.")
    elif not os.getenv("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY missing — can't generate recommendation.")
    else:
        with st.spinner("Thinking..."):
            answer, retrieved = rag.recommend(query, k=k)

        st.subheader("Recommendation")
        st.markdown(answer)

        st.subheader("Retrieved candidate cards")
        for card, score in retrieved:
            with st.expander(f"{card.name}  —  similarity {score:.3f}"):
                st.json(card.raw)
