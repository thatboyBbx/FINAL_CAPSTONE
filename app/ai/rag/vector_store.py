"""
RAG Vector Store — wraps ChromaDB for document chunk storage and retrieval.
Uses sentence-transformers/all-MiniLM-L6-v2 for embedding.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton so the heavy SentenceTransformer model is loaded
# once per process rather than on every request.
# ---------------------------------------------------------------------------
_st_model = None


def _get_st_model():
    """Lazily load and cache the SentenceTransformer model."""
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.info("SentenceTransformer all-MiniLM-L6-v2 loaded.")
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for RAG. "
                "Install with: pip install sentence-transformers"
            )
    return _st_model


class VectorStore:
    """
    Wraps ChromaDB for storing and querying document chunk embeddings.
    One instance should be created at app startup and shared.
    """

    def __init__(self, persist_dir: str = "./chroma_db") -> None:
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=persist_dir)
            self._col = self._client.get_or_create_collection(
                name="document_chunks",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB initialised at '%s'.", persist_dir)
        except ImportError:
            raise ImportError(
                "chromadb is required. Install with: pip install chromadb"
            )
        except Exception as exc:
            logger.error(
                "ChromaDB collection could not be loaded from '%s': %s",
                persist_dir,
                exc,
                exc_info=True,
            )
            raise RuntimeError(
                f"VectorStore failed to initialise ChromaDB at '{persist_dir}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------

    def chunk_document(
        self,
        document_id: str,
        full_text: str,
        chunk_size: int = 400,
        overlap: int = 80,
    ) -> List[Dict[str, Any]]:
        """
        Split full_text into overlapping chunks of ~chunk_size characters.
        Tries not to split mid-sentence using period/newline boundaries.
        Returns list of chunk dicts.
        """
        if not full_text or not full_text.strip():
            return []

        chunks: List[Dict[str, Any]] = []
        text = full_text.strip()
        text_len = len(text)
        pos = 0
        chunk_index = 0

        while pos < text_len:
            end = min(pos + chunk_size, text_len)

            if end < text_len:
                # Try to end at a sentence boundary within the last 25% of the window
                boundary = self._find_sentence_boundary(text, pos, end)
                if boundary > pos:
                    end = boundary

            chunk_text = text[pos:end].strip()
            if chunk_text:
                chunk_id = f"{document_id}_chunk_{chunk_index}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "text": chunk_text,
                    "char_start": pos,
                    "char_end": end,
                })
                chunk_index += 1

            # Advance by (chunk_size - overlap) to carry context across chunks
            step = max(1, chunk_size - overlap)
            pos = pos + step

        return chunks

    def _find_sentence_boundary(self, text: str, start: int, end: int) -> int:
        """
        Search backwards from `end` for a sentence/paragraph boundary.
        Looks in the last 25% of the chunk window.
        Returns the position just after the boundary, or `end` if none found.
        """
        search_start = max(start, end - max(50, (end - start) // 4))
        segment = text[search_start:end]

        for pattern in (r"\.\s", r"\n\n", r"\n"):
            matches = list(re.finditer(pattern, segment))
            if matches:
                boundary = search_start + matches[-1].end()
                if boundary > start:
                    return boundary
        return end

    # ------------------------------------------------------------------
    # Embedding + storage
    # ------------------------------------------------------------------

    def embed_and_store(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Embed each chunk with SentenceTransformer and upsert into ChromaDB.
        Returns the number of chunks stored.
        """
        if not chunks:
            return 0

        model = _get_st_model()
        texts = [c["text"] for c in chunks]
        try:
            embeddings = model.encode(texts, show_progress_bar=False)
        except Exception as exc:
            logger.error("Embedding failed: %s", exc)
            raise

        ids = [c["chunk_id"] for c in chunks]
        metadatas = [
            {
                "document_id": c["document_id"],
                "chunk_index": c["chunk_index"],
                "char_start": c["char_start"],
                "char_end": c["char_end"],
            }
            for c in chunks
        ]
        embedding_lists = [e.tolist() for e in embeddings]

        try:
            # Upsert so re-indexing is idempotent
            self._col.upsert(
                ids=ids,
                embeddings=embedding_lists,
                documents=texts,
                metadatas=metadatas,
            )
        except Exception as exc:
            logger.error("ChromaDB upsert failed: %s", exc)
            raise

        return len(chunks)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        document_id: str,
        question: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Embed the question and retrieve top_k most relevant chunks for
        document_id, sorted by distance ascending (most relevant first).
        """
        if not question.strip():
            return []

        model = _get_st_model()
        try:
            q_emb = model.encode([question], show_progress_bar=False)[0].tolist()
        except Exception as exc:
            logger.error("Question embedding failed: %s", exc)
            return []

        try:
            results = self._col.query(
                query_embeddings=[q_emb],
                n_results=top_k,
                where={"document_id": document_id},
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.warning("ChromaDB query failed: %s", exc)
            return []

        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        output = []
        for i in range(len(results["ids"][0])):
            output.append({
                "chunk_id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "chunk_index": results["metadatas"][0][i].get("chunk_index", i),
                "char_start": results["metadatas"][0][i].get("char_start", 0),
                "char_end": results["metadatas"][0][i].get("char_end", 0),
                "distance": results["distances"][0][i],
            })

        output.sort(key=lambda x: x["distance"])
        return output

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_document(self, document_id: str) -> None:
        """Remove all chunks belonging to document_id from ChromaDB."""
        try:
            existing = self._col.get(where={"document_id": document_id}, include=[])
            ids_to_delete = existing.get("ids", [])
            if ids_to_delete:
                self._col.delete(ids=ids_to_delete)
                logger.info(
                    "Deleted %d chunks for document_id=%s",
                    len(ids_to_delete), document_id,
                )
        except Exception as exc:
            logger.error(
                "Failed to delete chunks for document %s: %s", document_id, exc
            )

    # ------------------------------------------------------------------
    # Health check — used by startup lifespan check
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """
        Return True if the ChromaDB collection is reachable, False otherwise.
        Used by the application startup lifespan to verify RAG layer availability.
        """
        try:
            self._col.count()
            return True
        except Exception as exc:
            logger.warning("VectorStore health_check failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Module-level singleton for the VectorStore (shared across all requests)
# ---------------------------------------------------------------------------
_vector_store_instance: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Return the shared VectorStore singleton, creating it on first call."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore(persist_dir="./chroma_db")
    return _vector_store_instance
