"""RAG knowledge system (Qdrant + sentence-transformers), shared singleton.

Prefers a persistent Qdrant on localhost:6333 (docker-compose), falling back to
an in-memory instance. The knowledge base is ingested once when the collection
is missing or empty.
"""

import logging
import threading
from datetime import datetime, timezone

from ..db import require_db
from ..errors import service_unavailable
from .ai import llm_fn

logger = logging.getLogger("floodsense.rag")

_lock = threading.Lock()
_client = None
_embedder = None


def get_rag():
    """Return (qdrant_client, embedder), initialising + ingesting on first use."""
    global _client, _embedder
    if _client is not None and _embedder is not None:
        return _client, _embedder
    with _lock:
        if _client is not None and _embedder is not None:
            return _client, _embedder
        try:
            from qdrant_client import QdrantClient

            from rag import EmbeddingPipeline, ingest_documents
            from rag.ingest import COLLECTION_NAME

            embedder = EmbeddingPipeline()
            try:
                client = QdrantClient(url="http://localhost:6333", timeout=5)
                client.get_collections()  # probe: raises if Docker Qdrant isn't up
            except Exception:
                client = QdrantClient(":memory:")

            collections = {c.name for c in client.get_collections().collections}
            populated = (
                COLLECTION_NAME in collections
                and client.count(COLLECTION_NAME).count > 0
            )
            if not populated:
                logger.info("Ingesting RAG knowledge base...")
                ingest_documents(client, embedder)

            _client, _embedder = client, embedder
            return _client, _embedder
        except Exception as e:
            logger.error("RAG initialisation failed: %s", e)
            raise service_unavailable(
                "RAG_UNAVAILABLE", f"Knowledge system could not be initialised: {e}"
            )


def build_rag_context_for_district(district: str):
    """Best-effort RAGContext for the agent pipeline (never blocks the workflow)."""
    from agent.schemas import RAGContext

    try:
        from rag import build_context, retrieve

        client, embedder = get_rag()
        docs = retrieve(
            f"flood risk and history for {district}", client, embedder, top_k=3
        )
        if not docs:
            return RAGContext()
        sources = sorted({d.get("source", "") for d in docs if d.get("source")})
        return RAGContext(context=build_context(docs), sources=sources)
    except Exception as e:
        logger.warning("RAG context unavailable for pipeline: %s", e)
        return RAGContext()


def answer_question(question: str, top_k: int = 3) -> dict:
    """Retrieve knowledge chunks and answer with the LLM (grounded RAG chat)."""
    from rag import build_context, retrieve

    client, embedder = get_rag()
    docs = retrieve(question, client, embedder, top_k=top_k)

    sources = [
        {
            "source": d.get("source", "Unknown"),
            "section": d.get("section"),
            "page_number": d.get("page_number"),
        }
        for d in docs
    ]

    context = build_context(docs)
    prompt = (
        "You are a disaster intelligence assistant for Pakistan. "
        "Answer the question strictly using the provided context. "
        "If the context does not contain enough information, say so.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )

    answer = llm_fn(prompt)
    llm_used = answer is not None
    if not llm_used:
        answer = (
            "No LLM API key is configured, so here is the most relevant knowledge "
            "retrieved for your question:\n\n" + (context or "No matching documents found.")
        )

    result = {
        "question": question,
        "answer": answer,
        "sources": sources,
        "llm_used": llm_used,
    }

    # Persist chat history (best-effort — chat must work even if Mongo hiccups).
    try:
        require_db().chats.insert_one(
            {**result, "created_at": datetime.now(timezone.utc)}
        )
    except Exception as e:
        logger.warning("Could not persist chat message: %s", e)

    return result
