"""Package core chứa toàn bộ pipeline xử lý RAG của haui-rag-assistant."""

from haui_rag.core.embedding import get_embedding, get_genai_client
from haui_rag.core.generation import build_prompt, generate_answer
from haui_rag.core.rag_pipeline import rag_query
from haui_rag.core.retrieval import retrieve_relevant_contexts

__all__ = [
    "get_embedding",
    "get_genai_client",
    "build_prompt",
    "generate_answer",
    "retrieve_relevant_contexts",
    "rag_query",
]
