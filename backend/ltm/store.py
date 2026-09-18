"""Long-term memory store: prefilled, per-user facts retrieved by semantic
search. Backed by Postgres + pgvector — the same database already used for
LangGraph checkpointing (see chatbot.py), just a second table.

This store is read (and seeded) by the app; the chatbot itself only ever
reads from it via the `search_memory` tool (see chatbot.py) — nothing in the
running chat flow writes to it. Seeding is done via `python -m ltm.seed`.
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
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
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


async def add_memory(pool: AsyncConnectionPool, user_id: str, content: str, category: str = "fact") -> int:
    """Embed and insert one memory row. Used by the seed script."""
    embedding = await get_embeddings().aembed_query(content)
    async with pool.connection() as conn:
        await register_vector_async(conn)
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
        return row["id"]


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
