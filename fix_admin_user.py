import asyncio
import asyncpg
from passlib.context import CryptContext
import os

# Setup hashing
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

async def fix_admin():
    # Hash the password
    hashed_pw = pwd_context.hash("password")
    print(f"Generated hash: {hashed_pw}")

    # Connect to DB
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/payment_assistant")
    
    print(f"Connecting to {database_url}...")
    try:
        conn = await asyncpg.connect(database_url)
        
        # Check if user exists
        user = await conn.fetchrow("SELECT * FROM users WHERE email = 'admin@example.com'")
        if user:
            print("User found. Updating password...")
            await conn.execute("UPDATE users SET password_hash = $1 WHERE email = 'admin@example.com'", hashed_pw)
            print("Password updated successfully.")
        else:
            print("User NOT found. Creating user...")
            await conn.execute("INSERT INTO users (email, password_hash, role) VALUES ($1, $2, 'admin')", "admin@example.com", hashed_pw)
            print("User created successfully.")
            
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(fix_admin())
