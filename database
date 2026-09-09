import aiosqlite
from config import DB_PATH


async def init_db():
    """Bazani va jadvalni yaratadi (agar mavjud bo'lmasa)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                code TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                title TEXT,
                added_by INTEGER,
                views INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def add_movie(code: str, file_id: str, title: str, admin_id: int) -> bool:
    """Yangi kino qo'shadi. Kod band bo'lsa False qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT code FROM movies WHERE code = ?", (code,))
        if await cursor.fetchone():
            return False
        await db.execute(
            "INSERT INTO movies (code, file_id, title, added_by) VALUES (?, ?, ?, ?)",
            (code, file_id, title, admin_id),
        )
        await db.commit()
        return True


async def get_movie(code: str):
    """Kod bo'yicha kinoni topadi va ko'rishlar sonini +1 qiladi."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT code, file_id, title, views FROM movies WHERE code = ?", (code,)
        )
        row = await cursor.fetchone()
        if row:
            await db.execute(
                "UPDATE movies SET views = views + 1 WHERE code = ?", (code,)
            )
            await db.commit()
        return row


async def delete_movie(code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM movies WHERE code = ?", (code,))
        await db.commit()
        return cursor.rowcount > 0


async def movie_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM movies")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def add_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
        )
        await db.commit()


async def user_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def top_movies(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT code, title, views FROM movies ORDER BY views DESC LIMIT ?",
            (limit,),
        )
        return await cursor.fetchall()
