"""Minimal runbook ingestion into local ChromaDB."""

from __future__ import annotations

import argparse
import json
import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
import chromadb


RUNBOOKS_DIR = Path(__file__).resolve().parents[1] / "runbooks"
VECTOR_STORE_DIR = Path(__file__).resolve().parents[1] / "vector_store"
COLLECTION_NAME = "runbooks"
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MANIFEST_FILE = VECTOR_STORE_DIR / "manifest.json"
INDEX_FILE = VECTOR_STORE_DIR / "index.json"


@dataclass
class RunbookChunk:
    source_file: str
    section: str
    content: str


class LocalEmbedder:
    _shared_model: Any = None
    _shared_dimension: int = 384

    def __init__(self) -> None:
        self._model = self.__class__._shared_model
        self._dimension = self.__class__._shared_dimension
        if self._model is None and self.__class__._shared_model is None:
            self._load_model()
            self.__class__._shared_model = self._model
            self.__class__._shared_dimension = self._dimension

    def _load_model(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(DEFAULT_MODEL)
            dimension_getter = getattr(self._model, "get_embedding_dimension", None)
            if dimension_getter is None:
                dimension_getter = getattr(self._model, "get_sentence_embedding_dimension", None)
            dim_value = None
            try:
                if callable(dimension_getter):
                    dim_value = dimension_getter()
            except Exception:
                dim_value = None
            if dim_value is None:
                # keep the default/shared dimension if the model does not provide one
                self._dimension = int(self.__class__._shared_dimension)
            else:
                # only convert safe types to int; fall back on shared default on error
                if isinstance(dim_value, int):
                    self._dimension = dim_value
                else:
                    try:
                        self._dimension = int(cast(Any, dim_value))  # may accept numeric strings
                    except Exception:
                        self._dimension = int(self.__class__._shared_dimension)
        except Exception:
            self._model = None

    def _fallback_vector(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimension
            vector[index] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

    def encode(self, texts: list[str]) -> list[list[float]]:
        if self._model is not None:
            embeddings = self._model.encode(texts, normalize_embeddings=True)
            return embeddings.tolist()
        return [self._fallback_vector(text) for text in texts]


def _read_runbook_chunks(path: Path) -> list[RunbookChunk]:
    lines = path.read_text(encoding="utf-8").splitlines()
    chunks: list[RunbookChunk] = []
    current_section = "overview"
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines, current_section
        content = "\n".join(line for line in current_lines if line.strip()).strip()
        if content:
            chunks.append(RunbookChunk(path.name, current_section, content))
        current_lines = []

    for line in lines:
        if line.startswith("## "):
            flush()
            current_section = line[3:].strip().lower().replace(" ", "_")
            continue
        if line.startswith("# "):
            continue
        current_lines.append(line)

    flush()
    return chunks


def load_runbook_chunks() -> list[RunbookChunk]:
    chunks: list[RunbookChunk] = []
    for path in sorted(RUNBOOKS_DIR.glob("*.md")):
        chunks.extend(_read_runbook_chunks(path))
    return chunks


def _build_manifest(chunks: list[RunbookChunk]) -> dict:
    return {
        "runbooks": sorted(
            [
                {
                    "source_file": chunk.source_file,
                    "section": chunk.section,
                    "content_hash": hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                }
                for chunk in chunks
            ],
            key=lambda item: (item["source_file"], item["section"], item["content_hash"]),
        )
    }


def _read_manifest() -> dict | None:
    if not MANIFEST_FILE.exists():
        return None
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))


def _write_manifest(manifest: dict) -> None:
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_index(documents: list[str], metadatas: list[dict], embeddings: list[list[float]]) -> None:
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(
        json.dumps(
            {
                "documents": documents,
                "metadatas": metadatas,
                "embeddings": embeddings,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _clear_vector_store(preserve: list[str] | None = None) -> None:
    preserve = preserve or []
    if not VECTOR_STORE_DIR.exists():
        return
    for child in VECTOR_STORE_DIR.iterdir():
        if child.name in preserve:
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except Exception:
                pass


def ingest_runbooks() -> dict:
    chunks = load_runbook_chunks()
    manifest = _build_manifest(chunks)
    current_manifest = _read_manifest()
    if VECTOR_STORE_DIR.exists() and current_manifest == manifest:
        return {"status": "ok", "runbooks": len({chunk.source_file for chunk in chunks}), "chunks": len(chunks), "reused": True}

    if not chunks:
        # ensure vector_store exists and write empty index/manifest
        VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
        _write_index([], [], [])
        _write_manifest(manifest)
        return {"status": "ok", "runbooks": 0, "chunks": 0, "reused": False, "note": "no_runbooks_found"}

    documents = [chunk.content for chunk in chunks]
    ids = [f"{chunk.source_file}:{chunk.section}:{i}" for i, chunk in enumerate(chunks)]
    metadatas = [
        {"source_file": chunk.source_file, "section": chunk.section, "chunk_index": i}
        for i, chunk in enumerate(chunks)
    ]
    embeddings = LocalEmbedder().encode(documents)
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    _write_index(documents, metadatas, embeddings)

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            # clear existing store but preserve index/manifest so fallback remains available
            VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
            _clear_vector_store(preserve=[INDEX_FILE.name, MANIFEST_FILE.name])

            client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
            collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=cast(Any, metadatas),
                embeddings=cast(Any, embeddings),
            )
            try:
                _write_manifest(manifest)
            except Exception:
                # don't treat manifest write failure as a chroma failure
                pass
            return {"status": "ok", "runbooks": len({chunk.source_file for chunk in chunks}), "chunks": len(chunks), "reused": False}
        except Exception as exc:
            last_error = exc
            # on failure, try to clean chroma files but keep JSON fallback
            _clear_vector_store(preserve=[INDEX_FILE.name, MANIFEST_FILE.name])

    _write_manifest(manifest)
    if last_error is not None:
        return {
            "status": "ok",
            "runbooks": len({chunk.source_file for chunk in chunks}),
            "chunks": len(chunks),
            "reused": False,
            "backend": "json",
            "warning": str(last_error),
        }
    return {"status": "ok", "runbooks": len({chunk.source_file for chunk in chunks}), "chunks": len(chunks), "reused": False, "backend": "json"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest markdown runbooks into local ChromaDB.")
    parser.parse_args(argv)
    print(json.dumps(ingest_runbooks(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
