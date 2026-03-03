"""
RAG Vector Store Module

Provides semantic retrieval for conversation history using FAISS + HuggingFace Embeddings.
"""

import os
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Lazy imports to avoid loading heavy models at startup
_faiss = None
_embeddings = None

VECTOR_STORE_DIR = "memory/vector_store"
INDEX_FILE = "faiss_index"
METADATA_FILE = "metadata.json"


def _get_embeddings():
    """Lazy load embeddings model."""
    global _embeddings
    if _embeddings is None:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from app.core.config import settings
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.RAG_EMBEDDING_MODEL,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
    return _embeddings


def _get_faiss():
    """Lazy load FAISS."""
    global _faiss
    if _faiss is None:
        from langchain_community.vectorstores import FAISS
        _faiss = FAISS
    return _faiss


class ConversationVectorStore:
    """
    Vector store for conversation history.
    Supports semantic retrieval across sessions.
    """

    def __init__(self, task_id: Optional[str] = None):
        self.task_id = task_id or "default"
        self.store_path = os.path.join(VECTOR_STORE_DIR, self.task_id)
        self.index_path = os.path.join(self.store_path, INDEX_FILE)
        self.metadata_path = os.path.join(self.store_path, METADATA_FILE)
        self.vector_store = None
        self.metadata: Dict[str, Dict] = {}  # doc_id -> metadata

    def _ensure_dir(self):
        """Ensure vector store directory exists."""
        os.makedirs(self.store_path, exist_ok=True)

    def _doc_id(self, session_id: str, msg_idx: int) -> str:
        """Generate unique document ID."""
        return f"{session_id}_{msg_idx}"

    def _hash_content(self, content: str) -> str:
        """Generate hash for content deduplication."""
        return hashlib.md5(content.encode()).hexdigest()[:8]

    def load(self) -> bool:
        """Load existing vector store from disk."""
        if not os.path.exists(self.index_path):
            return False

        try:
            FAISS = _get_faiss()
            embeddings = _get_embeddings()
            self.vector_store = FAISS.load_local(
                self.store_path,
                embeddings,
                index_name=INDEX_FILE,
                allow_dangerous_deserialization=True
            )

            # Load metadata
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)

            return True
        except Exception as e:
            print(f"[VectorStore] Failed to load: {e}")
            return False

    def save(self):
        """Save vector store to disk."""
        if self.vector_store is None:
            return

        self._ensure_dir()
        try:
            self.vector_store.save_local(self.store_path, index_name=INDEX_FILE)

            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[VectorStore] Failed to save: {e}")

    def add_conversation_pair(
        self,
        session_id: str,
        user_msg: str,
        assistant_msg: str,
        msg_idx: int,
        topic: Optional[str] = None
    ):
        """
        Add a conversation pair to vector store.

        Args:
            session_id: Session identifier
            user_msg: User message content
            assistant_msg: Assistant message content
            msg_idx: Message index in session
            topic: Optional topic for context
        """
        if not user_msg.strip() and not assistant_msg.strip():
            return

        doc_id = self._doc_id(session_id, msg_idx)

        # Check for duplicates
        if doc_id in self.metadata:
            return

        # Combine user + assistant for better context
        combined_text = f"User: {user_msg}\nAssistant: {assistant_msg}"

        # Create document with metadata
        metadata = {
            "session_id": session_id,
            "msg_idx": msg_idx,
            "user_msg": user_msg[:500],  # Truncate for metadata
            "assistant_msg": assistant_msg[:500],
            "topic": topic or "General",
            "created_at": datetime.now().isoformat(),
            "content_hash": self._hash_content(combined_text)
        }

        try:
            FAISS = _get_faiss()
            embeddings = _get_embeddings()

            if self.vector_store is None:
                # Create new store
                self.vector_store = FAISS.from_texts(
                    [combined_text],
                    embeddings,
                    metadatas=[metadata]
                )
            else:
                # Add to existing store
                self.vector_store.add_texts([combined_text], metadatas=[metadata])

            self.metadata[doc_id] = metadata

        except Exception as e:
            print(f"[VectorStore] Failed to add document: {e}")

    def add_session_messages(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        topic: Optional[str] = None
    ):
        """
        Add all conversation pairs from a session.

        Args:
            session_id: Session identifier
            messages: List of message dicts with 'role' and 'content'
            topic: Optional topic for context
        """
        i = 0
        while i < len(messages) - 1:
            # Find user message
            if messages[i].get("role") == "user":
                user_msg = messages[i].get("content", "")

                # Find next assistant message
                assistant_msg = ""
                if i + 1 < len(messages) and messages[i + 1].get("role") == "assistant":
                    assistant_msg = messages[i + 1].get("content", "")

                if user_msg.strip() or assistant_msg.strip():
                    self.add_conversation_pair(
                        session_id,
                        user_msg,
                        assistant_msg,
                        msg_idx=i,
                        topic=topic
                    )
            i += 1

        # Save after batch add
        self.save()

    def search(
        self,
        query: str,
        top_k: int = 3,
        exclude_session: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search for relevant conversation pairs.

        Args:
            query: Search query
            top_k: Number of results to return
            exclude_session: Optional session ID to exclude from results

        Returns:
            List of matching conversation pairs with scores
        """
        if self.vector_store is None:
            if not self.load():
                return []

        try:
            results = self.vector_store.similarity_search_with_score(
                query,
                k=top_k * 2  # Get more to allow filtering
            )

            formatted_results = []
            seen = set()

            for doc, score in results:
                meta = doc.metadata
                session_id = meta.get("session_id", "")

                # Filter out current session if specified
                if exclude_session and session_id == exclude_session:
                    continue

                # Deduplicate by content hash
                content_hash = meta.get("content_hash", "")
                if content_hash in seen:
                    continue
                seen.add(content_hash)

                formatted_results.append({
                    "content": doc.page_content,
                    "score": float(score),
                    "session_id": session_id,
                    "topic": meta.get("topic", "General"),
                    "user_msg": meta.get("user_msg", ""),
                    "assistant_msg": meta.get("assistant_msg", "")
                })

                if len(formatted_results) >= top_k:
                    break

            return formatted_results

        except Exception as e:
            print(f"[VectorStore] Search failed: {e}")
            return []

    def clear(self):
        """Clear the vector store."""
        self.vector_store = None
        self.metadata = {}

        # Remove files
        if os.path.exists(self.store_path):
            import shutil
            shutil.rmtree(self.store_path, ignore_errors=True)


# Global cache for vector stores
_store_cache: Dict[str, ConversationVectorStore] = {}


def get_vector_store(task_id: str) -> ConversationVectorStore:
    """Get or create a vector store for a task."""
    if task_id not in _store_cache:
        store = ConversationVectorStore(task_id)
        store.load()
        _store_cache[task_id] = store
    return _store_cache[task_id]


def rag_retrieve(
    query: str,
    task_id: str,
    top_k: int = 3,
    exclude_session: Optional[str] = None
) -> str:
    """
    High-level RAG retrieval function.
    Returns formatted context string for LLM.

    Args:
        query: User's query
        task_id: Task identifier
        top_k: Number of results
        exclude_session: Session to exclude

    Returns:
        Formatted context string
    """
    store = get_vector_store(task_id)
    results = store.search(query, top_k=top_k, exclude_session=exclude_session)

    if not results:
        return ""

    output_lines = []
    for idx, result in enumerate(results, 1):
        score = result.get("score", 0)
        content = result.get("content", "")
        topic = result.get("topic", "")

        # Convert FAISS distance to similarity score (lower distance = higher similarity)
        # FAISS L2 distance: 0 = identical, higher = more different
        similarity = max(0, 1 - score / 2)  # Rough normalization

        output_lines.append(
            f"--- 相关片段 {idx} (相关度: {similarity:.2f}, 主题: {topic}) ---\n{content}\n"
        )

    return "\n".join(output_lines)


def index_session(
    session_id: str,
    task_id: str,
    messages: List[Dict[str, Any]],
    topic: Optional[str] = None
):
    """
    Index a session's messages into vector store.

    Args:
        session_id: Session identifier
        task_id: Task identifier
        messages: List of message dicts
        topic: Optional topic
    """
    store = get_vector_store(task_id)
    store.add_session_messages(session_id, messages, topic)