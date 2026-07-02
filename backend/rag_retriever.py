"""Minimal runbook retrieval from local ChromaDB."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import chromadb

from .rag_ingest import COLLECTION_NAME, LocalEmbedder, VECTOR_STORE_DIR


INDEX_FILE = VECTOR_STORE_DIR / "index.json"


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5 or 1.0
    right_norm = sum(b * b for b in right) ** 0.5 or 1.0
    return numerator / (left_norm * right_norm)


def _search_index_fallback(query: str, top_k: int) -> dict:
    if not INDEX_FILE.exists():
        return {"query": query, "results": [], "status": "vector_store_missing"}

    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    embedder = LocalEmbedder()
    query_embedding = embedder.encode([query])[0]
    scored = []
    for document, metadata, embedding in zip(index.get("documents", []), index.get("metadatas", []), index.get("embeddings", [])):
        score = _cosine_similarity(query_embedding, embedding)
        item = {
            "source_file": metadata.get("source_file"),
            "section": metadata.get("section"),
            "content": document,
            "score": round(max(0.0, score), 4),
        }
        if "chunk_index" in metadata:
            item["chunk_index"] = metadata["chunk_index"]
        scored.append(item)
    scored.sort(key=lambda item: item["score"], reverse=True)
    return {"query": query, "results": scored[:top_k], "status": "fallback"}


def search_runbooks(query: str, top_k: int = 3) -> dict:
    query = (query or "").strip()
    if not query:
        return {"query": query, "results": [], "status": "empty_query"}
    # don't short-circuit when vector_store dir is missing — allow JSON fallback

    try:
        client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
        collection = client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
        embedder = LocalEmbedder()
        query_embedding = embedder.encode([query])[0]
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"],
        )

        results = []
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        for document, metadata, distance in zip(documents, metadatas, distances):
            item = {
                "source_file": metadata.get("source_file"),
                "section": metadata.get("section"),
                "content": document,
                "score": round(max(0.0, 1.0 - float(distance)), 4),
            }
            if "chunk_index" in metadata:
                item["chunk_index"] = metadata["chunk_index"]
            results.append(item)

        return {"query": query, "results": results}
    except Exception:
        return _search_index_fallback(query, top_k)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search the local runbook store.")
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args(argv)
    print(json.dumps(search_runbooks(args.query, args.top_k), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
