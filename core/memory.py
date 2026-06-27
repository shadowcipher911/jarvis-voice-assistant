"""
core/memory.py — Persistent two-layer memory system.

Layer 1: ChromaDB vector store for semantic search over conversation history.
Layer 2: SQLite for structured facts, preferences, contacts, and pinned memories.
"""

import os
import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("jarvis.memory")

# ---------------------------------------------------------------------------
# Lazy-import helpers so the module loads even if dependencies are missing
# ---------------------------------------------------------------------------

def _get_chroma():
    import chromadb
    return chromadb

def _get_embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

MEMORY_DIR = Path(__file__).parent.parent / "memory"
CHROMA_DIR = MEMORY_DIR / "chroma_db"
SQLITE_PATH = MEMORY_DIR / "jarvis.db"


class Memory:
    """Unified memory interface for JARVIS."""

    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        # --- Vector store ---
        self._chroma_client = None
        self._collection = None
        self._embedder = None

        # --- SQLite ---
        self._db = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False)
        self._init_sqlite()

        logger.info("Memory system initialised.")

    # -----------------------------------------------------------------------
    # Internal setup
    # -----------------------------------------------------------------------

    def _init_sqlite(self):
        cur = self._db.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS pinned (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                text       TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS preferences (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS contacts (
                name  TEXT PRIMARY KEY,
                email TEXT,
                role  TEXT,
                notes TEXT
            );
            CREATE TABLE IF NOT EXISTS history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        self._db.commit()

    def _ensure_vector_store(self):
        """Lazily initialise ChromaDB + embedder on first use."""
        if self._collection is not None:
            return
        try:
            chroma = _get_chroma()
            self._chroma_client = chroma.PersistentClient(path=str(CHROMA_DIR))
            self._collection = self._chroma_client.get_or_create_collection(
                name="jarvis_memories",
                metadata={"hnsw:space": "cosine"},
            )
            self._embedder = _get_embedder()
            logger.info("ChromaDB vector store ready.")
        except Exception as exc:
            logger.warning("ChromaDB unavailable — vector memory disabled: %s", exc)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def save(self, text: str, importance: int = 3) -> None:
        """Save a memory to the vector store with an importance score (1–5)."""
        self._ensure_vector_store()
        if self._collection is None:
            return

        now = datetime.now(timezone.utc).isoformat()
        doc_id = f"mem_{now}_{hash(text) & 0xFFFFFFFF}"
        embedding = self._embedder.encode(text).tolist()

        self._collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[{"timestamp": now, "importance": importance}],
        )
        logger.debug("Memory saved (importance=%d): %s", importance, text[:80])

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search — returns top_k most relevant memories."""
        self._ensure_vector_store()
        if self._collection is None:
            return []

        embedding = self._embedder.encode(query).tolist()
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, max(1, self._collection.count())),
            include=["documents", "metadatas", "distances"],
        )

        memories = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            memories.append({
                "text": doc,
                "timestamp": meta.get("timestamp", ""),
                "importance": meta.get("importance", 3),
                "relevance": round(1 - dist, 3),
            })
        return memories

    def pin(self, text: str) -> None:
        """Pin a memory permanently (stored in SQLite, never expires)."""
        cur = self._db.cursor()
        cur.execute("INSERT INTO pinned (text) VALUES (?)", (text,))
        self._db.commit()
        logger.info("Pinned memory: %s", text[:80])

    def get_pinned(self) -> list[str]:
        """Return all pinned memories."""
        cur = self._db.cursor()
        cur.execute("SELECT text FROM pinned ORDER BY created_at")
        return [row[0] for row in cur.fetchall()]

    def save_fact(self, key: str, value: str) -> None:
        """Store or update a key-value fact."""
        cur = self._db.cursor()
        cur.execute(
            "INSERT INTO facts (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
            (key.lower().strip(), value),
        )
        self._db.commit()

    def recall_structured(self, key: str) -> Optional[str]:
        """Retrieve a stored fact by key."""
        cur = self._db.cursor()
        cur.execute("SELECT value FROM facts WHERE key = ?", (key.lower().strip(),))
        row = cur.fetchone()
        return row[0] if row else None

    def get_all_facts(self) -> dict:
        """Return all stored facts."""
        cur = self._db.cursor()
        cur.execute("SELECT key, value FROM facts")
        return dict(cur.fetchall())

    def save_preference(self, key: str, value: str) -> None:
        cur = self._db.cursor()
        cur.execute(
            "INSERT INTO preferences (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self._db.commit()

    def get_preference(self, key: str, default: str = "") -> str:
        cur = self._db.cursor()
        cur.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

    def save_contact(self, name: str, email: str = "", role: str = "", notes: str = "") -> None:
        cur = self._db.cursor()
        cur.execute(
            "INSERT INTO contacts (name, email, role, notes) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET email=excluded.email, role=excluded.role, notes=excluded.notes",
            (name, email, role, notes),
        )
        self._db.commit()

    def get_contact(self, name: str) -> Optional[dict]:
        cur = self._db.cursor()
        cur.execute("SELECT name, email, role, notes FROM contacts WHERE name LIKE ?", (f"%{name}%",))
        row = cur.fetchone()
        if row:
            return {"name": row[0], "email": row[1], "role": row[2], "notes": row[3]}
        return None

    def add_history(self, role: str, content: str) -> None:
        """Append a message to conversation history."""
        cur = self._db.cursor()
        cur.execute(
            "INSERT INTO history (role, content) VALUES (?, ?)",
            (role, content),
        )
        self._db.commit()

    def get_history(self, limit: int = 50) -> list[dict]:
        cur = self._db.cursor()
        cur.execute(
            "SELECT role, content, created_at FROM history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
        return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in reversed(rows)]

    def build_context_string(self, query: str, top_k: int = 5) -> str:
        """Build a memory context block to inject into the LLM prompt."""
        lines = []

        # Pinned memories always included
        pinned = self.get_pinned()
        if pinned:
            lines.append("=== Permanent Memories ===")
            lines.extend(f"• {p}" for p in pinned)

        # Semantic search
        hits = self.search(query, top_k=top_k)
        if hits:
            lines.append("=== Relevant Past Memories ===")
            for h in hits:
                ts = h["timestamp"][:10] if h["timestamp"] else "unknown"
                lines.append(f"• [{ts}] {h['text']}")

        # Key facts
        facts = self.get_all_facts()
        if facts:
            lines.append("=== Known Facts ===")
            for k, v in facts.items():
                lines.append(f"• {k}: {v}")

        return "\n".join(lines) if lines else "No prior memories."

    def close(self):
        self._db.close()


# Module-level singleton
_instance: Optional[Memory] = None


def get_memory() -> Memory:
    global _instance
    if _instance is None:
        _instance = Memory()
    return _instance
