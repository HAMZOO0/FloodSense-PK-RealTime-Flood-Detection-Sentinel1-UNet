"""RAG Knowledge Assistant — grounded Q&A over the flood knowledge base."""

from fastapi import APIRouter, Query

from ..db import require_db, serialize
from ..schemas import ChatRequest
from ..services.rag import answer_question

router = APIRouter(prefix="/chat", tags=["Knowledge Chat"])


@router.post("")
def chat(body: ChatRequest):
    """Ask the knowledge assistant a question; answers cite their sources.

    The first call is slow (~30s) while the embedding model loads and the
    knowledge base is ingested; subsequent calls are fast.
    """
    result = answer_question(body.question, top_k=body.top_k)
    return {"success": True, **result}


@router.get("/history")
def chat_history(limit: int = Query(50, ge=1, le=200)):
    """Recent Q&A history (newest first)."""
    db = require_db()
    docs = db.chats.find().sort("created_at", -1).limit(limit)
    messages = [serialize(d) for d in docs]
    return {"success": True, "count": len(messages), "messages": messages}
