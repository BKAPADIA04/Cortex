"""Load ltm.seed_data.SEED_MEMORIES into the LTM store.

Usage:
    python -m ltm.seed            # load the seed data, updating near-duplicates in place
    python -m ltm.seed --reset    # wipe existing rows for these users first, then load

Requires DATABASE_URL and a Google API key (GOOGLE_API_KEY) in the
environment, same as the main app — see backend/.env.
"""

import argparse
import asyncio
import os

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from . import store
from .config import TABLE_NAME
from .seed_data import SEED_MEMORIES

load_dotenv()


async def main(reset: bool) -> None:
    pool = AsyncConnectionPool(
        conninfo=os.environ["DATABASE_URL"],
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    )
    await pool.open()
    try:
        await store.ensure_schema(pool)

        if reset:
            user_ids = {m["user_id"] for m in SEED_MEMORIES}
            async with pool.connection() as conn:
                for user_id in user_ids:
                    await conn.execute(f"DELETE FROM {TABLE_NAME} WHERE user_id = %s", (user_id,))
            print(f"Cleared existing memories for {len(user_ids)} user(s).")

        for memory in SEED_MEMORIES:
            result = await store.upsert_memory(
                pool, memory["user_id"], memory["content"], memory.get("category", "fact")
            )
            print(
                f"[{result['id']}] {result['action']} ({memory['user_id']}/"
                f"{memory.get('category', 'fact')}) {memory['content']}"
            )

        print(f"Seeded {len(SEED_MEMORIES)} memories.")
    finally:
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Delete existing rows for the seeded users first")
    args = parser.parse_args()
    asyncio.run(main(args.reset))
