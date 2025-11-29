import asyncio
import os
import asyncpg
from app.auth import get_password_hash

async def create_admin():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        return

    print(f"Connecting to {db_url}...")
    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"Failed to connect to DB: {e}")
        return

    email = "admin@example.com"
    password = "password"
    hashed_password = get_password_hash(password)
    
    try:
        await conn.execute("""
            INSERT INTO users (email, password_hash, role)
            VALUES ($1, $2, 'admin')
            ON CONFLICT (email) DO UPDATE 
            SET password_hash = $2, role = 'admin'
        """, email, hashed_password)
        print(f"Admin user {email} created/updated successfully.")
    except Exception as e:
        print(f"Error creating admin user: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(create_admin())
