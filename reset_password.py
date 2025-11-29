import asyncio
import os
import asyncpg
from app.auth import get_password_hash

async def reset_password():
    database_url = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(database_url)
    try:
        new_hash = get_password_hash("password")
        await conn.execute("UPDATE users SET password_hash = $1 WHERE email = 'admin@example.com'", new_hash)
        print("Password reset successfully for admin@example.com")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(reset_password())
