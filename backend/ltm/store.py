"""Long-term memory store: per-user facts retrieved by semantic search and
written to over time. Backed by Postgres + pgvector — the same database
already used for LangGraph checkpointing (see chatbot.py), just a second
table.

Seeded ahead of time via `python -m ltm.seed` (see seed_data.py), and read
and written during chat through the `search_memory` / `save_memory` tools
(see chatbot.py) — the latter gated behind human approval, same as the
web-search and document-retrieval tools.
"""

from typing import TypedDict

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pgvector import Vector
from pgvector.psycopg import register_vector_async
from psycopg_pool import AsyncConnectionPool

from . import config

_embeddings: GoogleGenerativeAIEmbeddings | None = None


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(model=config.EMBEDDING_MODEL)
    return _embeddings


async def ensure_schema(pool: AsyncConnectionPool) -> None:
    """Create the pgvector extension and memories table if missing.

    The vector column's dimensionality is derived from a live embedding call
    rather than hardcoded, since it depends on the embedding model in use.
    Safe to call on every startup — a no-op once the table exists.
    """
    dim = len(await get_embeddings().aembed_query("dimension probe"))
    async with pool.connection() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {config.TABLE_NAME} (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'fact',
                content TEXT NOT NULL,
                embedding VECTOR({dim}) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        # Backfills updated_at onto tables created before it existed.
        await conn.execute(
            f"ALTER TABLE {config.TABLE_NAME} ADD COLUMN IF NOT EXISTS "
            f"updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        )
        await conn.execute(
            f"CREATE INDEX IF NOT EXISTS {config.TABLE_NAME}_user_id_idx "
            f"ON {config.TABLE_NAME} (user_id)"
        )


class MemoryRecord(TypedDict):
    id: int
    category: str
    content: str
    score: float  # cosine distance — lower is more similar


class UpsertResult(TypedDict):
    id: int
    action: str  # "inserted" | "updated"


async def upsert_memory(
    pool: AsyncConnectionPool, user_id: str, content: str, category: str = "fact"
) -> UpsertResult:
    """Save a memory, updating an existing near-duplicate instead of adding a
    new row when one is found (cosine distance below config.DEDUPE_THRESHOLD,
    among that user's rows in the same category). Matching is scoped to
    `category` because plain topical similarity is too coarse on its own —
    e.g. a "name" fact and an unrelated "note" can land close together in
    embedding space just for sharing a subject. This is still a similarity
    heuristic, not true conflict detection: it can miss a contradicting fact
    worded very differently, or merge two same-category rows that are close
    but distinct. Used by the save_memory tool (chatbot.py) and available to
    the seed script for idempotent re-seeding.
    """
    embedding = await get_embeddings().aembed_query(content)
    async with pool.connection() as conn:
        await register_vector_async(conn)
        match = await (
            await conn.execute(
                f"""
                SELECT id, embedding <=> %s AS score
                FROM {config.TABLE_NAME}
                WHERE user_id = %s AND category = %s
                ORDER BY embedding <=> %s
                LIMIT 1
                """,
                (Vector(embedding), user_id, category, Vector(embedding)),
            )
        ).fetchone()

        if match and match["score"] <= config.DEDUPE_THRESHOLD:
            await conn.execute(
                f"""
                UPDATE {config.TABLE_NAME}
                SET content = %s, category = %s, embedding = %s, updated_at = now()
                WHERE id = %s
                """,
                (content, category, Vector(embedding), match["id"]),
            )
            return {"id": match["id"], "action": "updated"}

        row = await (
            await conn.execute(
                f"""
                INSERT INTO {config.TABLE_NAME} (user_id, category, content, embedding)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, category, content, Vector(embedding)),
            )
        ).fetchone()
        return {"id": row["id"], "action": "inserted"}


async def search_memory(
    pool: AsyncConnectionPool, user_id: str, query: str, k: int = config.RETRIEVAL_K
) -> list[MemoryRecord]:
    """Semantic search over one user's memories, nearest first."""
    query_embedding = await get_embeddings().aembed_query(query)
    async with pool.connection() as conn:
        await register_vector_async(conn)
        rows = await (
            await conn.execute(
                f"""
                SELECT id, category, content, embedding <=> %s AS score
                FROM {config.TABLE_NAME}
                WHERE user_id = %s
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (Vector(query_embedding), user_id, Vector(query_embedding), k),
            )
        ).fetchall()
        return [
            {"id": r["id"], "category": r["category"], "content": r["content"], "score": r["score"]}
            for r in rows
        ]


async def list_memories(pool: AsyncConnectionPool, user_id: str) -> list[MemoryRecord]:
    async with pool.connection() as conn:
        rows = await (
            await conn.execute(
                f"SELECT id, category, content, 0.0 AS score FROM {config.TABLE_NAME} "
                f"WHERE user_id = %s ORDER BY id",
                (user_id,),
            )
        ).fetchall()
        return [
            {"id": r["id"], "category": r["category"], "content": r["content"], "score": r["score"]}
            for r in rows
        ]
