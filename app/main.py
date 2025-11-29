from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
import asyncpg
from pydantic import BaseModel
import shutil
import os
import uuid
import redis
import json
from worker.tasks import process_invoice
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.auth import verify_password, get_password_hash, create_access_token, decode_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    # Create test user if not exists
    async with app.state.pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE email = 'admin@example.com'")
        if not user:
            hashed_pw = get_password_hash("password")
            await conn.execute("INSERT INTO users (email, password_hash, role) VALUES ($1, $2, 'admin')", "admin@example.com", hashed_pw)
    yield
    # Shutdown
    await app.state.pool.close()

app = FastAPI(title="Agentic Payment Assistant", lifespan=lifespan)

# Mount static files for live feed
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id

class PinRequest(BaseModel):
    pin: str

class Token(BaseModel):
    access_token: str
    token_type: str

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    async with app.state.pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE email = $1", form_data.username)
        if not user or not verify_password(form_data.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user["id"])}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}

@app.post("/upload")
async def upload_invoice(file: UploadFile = File(...), current_user_id: str = Depends(get_current_user)):
    """
    Ingests an invoice PDF, saves it, and triggers the processing task.
    """
    try:
        # Generate unique ID
        invoice_id = str(uuid.uuid4())
        file_location = f"invoices/{invoice_id}_{file.filename}"
        os.makedirs("invoices", exist_ok=True)
        
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Trigger Celery task
        task = process_invoice.delay(file_location, invoice_id, current_user_id)
        
        return {"status": "processing", "invoice_id": invoice_id, "task_id": task.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/audits")
async def get_audits(current_user_id: str = Depends(get_current_user)):
    """
    Fetches real audit logs from Postgres.
    """
    try:
        async with app.state.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM audits ORDER BY created_at DESC LIMIT 50")
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"DB Error: {e}")
        return []

@app.get("/transactions/pending")
async def get_pending_transactions(current_user_id: str = Depends(get_current_user)):
    """
    Fetches transactions that need approval for the current user.
    """
    try:
        async with app.state.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM transactions WHERE (status = 'NEEDS_APPROVAL' OR status = 'NEEDS_REVIEW' OR status = 'QUEUED_FOR_PAYMENT' OR status = 'WAITING_FOR_PIN') AND user_id = $1 ORDER BY created_at DESC", current_user_id)
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"DB Error: {e}")
        return []

@app.get("/transactions/{transaction_id}")
async def get_transaction(transaction_id: int, current_user_id: str = Depends(get_current_user)):
    """
    Fetches a specific transaction by ID, ensuring ownership.
    """
    try:
        async with app.state.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM transactions WHERE id = $1 AND user_id = $2", transaction_id, current_user_id)
            if row:
                return dict(row)
            else:
                raise HTTPException(status_code=404, detail="Transaction not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class TransactionUpdate(BaseModel):
    vendor: str | None = None
    amount: float | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    remarks: str | None = None

@app.put("/transactions/{transaction_id}")
async def update_transaction(transaction_id: int, transaction: TransactionUpdate, current_user_id: str = Depends(get_current_user)):
    """
    Updates transaction details (e.g. adding missing account number).
    """
    try:
        async with app.state.pool.acquire() as conn:
            # Verify ownership
            row = await conn.fetchrow("SELECT * FROM transactions WHERE id = $1 AND user_id = $2", transaction_id, current_user_id)
            if not row:
                raise HTTPException(status_code=404, detail="Transaction not found")
            
            # Update fields
            query = "UPDATE transactions SET "
            params = []
            updates = []
            i = 1
            
            if transaction.vendor is not None:
                updates.append(f"vendor = ${i}")
                params.append(transaction.vendor)
                i += 1
            if transaction.amount is not None:
                updates.append(f"amount = ${i}")
                params.append(transaction.amount)
                i += 1
            if transaction.account_number is not None:
                updates.append(f"account_number = ${i}")
                params.append(transaction.account_number)
                i += 1
            if transaction.ifsc_code is not None:
                updates.append(f"ifsc_code = ${i}")
                params.append(transaction.ifsc_code)
                i += 1
            if transaction.remarks is not None:
                updates.append(f"remarks = ${i}")
                params.append(transaction.remarks)
                i += 1
            
            # If updating account number, we can auto-move from NEEDS_REVIEW to NEEDS_APPROVAL if desired.
            # But let's keep it simple: just update data. User clicks Approve separately.
            
            if not updates:
                return {"status": "no_changes"}
                
            query += ", ".join(updates) + f" WHERE id = ${i} AND user_id = ${i+1}"
            params.append(transaction_id)
            params.append(current_user_id)
            
            await conn.execute(query, *params)
            return {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transactions/{transaction_id}/approve")
async def approve_transaction(transaction_id: int, current_user_id: str = Depends(get_current_user)):
    """
    Approves a specific transaction and triggers payment.
    """
    try:
        async with app.state.pool.acquire() as conn:
            # Update status
            result = await conn.execute("UPDATE transactions SET status = 'QUEUED_FOR_PAYMENT' WHERE id = $1 AND user_id = $2", transaction_id, current_user_id)
            if result == "UPDATE 0":
                 raise HTTPException(status_code=404, detail="Transaction not found or unauthorized")

            # Fetch details
            row = await conn.fetchrow("SELECT * FROM transactions WHERE id = $1", transaction_id)
            
            if row:
                # Trigger payment execution
                from worker.tasks import execute_payment
                execute_payment.delay(dict(row))
                return {"status": "queued", "transaction_id": transaction_id}
            else:
                raise HTTPException(status_code=404, detail="Transaction not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transactions/approve_batch/{batch_id}")
async def approve_batch(batch_id: str, current_user_id: str = Depends(get_current_user)):
    """
    Approves all transactions in a batch for the current user.
    """
    try:
        async with app.state.pool.acquire() as conn:
            # Fetch all NEEDS_APPROVAL for this batch and user
            rows = await conn.fetch("SELECT * FROM transactions WHERE batch_id = $1 AND status = 'NEEDS_APPROVAL' AND user_id = $2", batch_id, current_user_id)
            
            if not rows:
                return {"status": "no_pending_transactions"}
                
            # Update all to QUEUED_FOR_PAYMENT
            await conn.execute("UPDATE transactions SET status = 'QUEUED_FOR_PAYMENT' WHERE batch_id = $1 AND status = 'NEEDS_APPROVAL' AND user_id = $2", batch_id, current_user_id)
            
            # Trigger tasks
            from worker.tasks import execute_payment
            task_ids = []
            for row in rows:
                task = execute_payment.delay(dict(row))
                task_ids.append(task.id)
                
            return {"status": "batch_queued", "count": len(rows), "task_ids": task_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transactions/{transaction_id}/provide_pin")
async def provide_pin(transaction_id: int, request: PinRequest, current_user_id: str = Depends(get_current_user)):
    """
    Receives PIN from user and writes to Redis to unblock the worker.
    """
    try:
        # Verify ownership
        async with app.state.pool.acquire() as conn:
             row = await conn.fetchrow("SELECT * FROM transactions WHERE id = $1 AND user_id = $2", transaction_id, current_user_id)
             if not row:
                 raise HTTPException(status_code=404, detail="Transaction not found or unauthorized")

        r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        r.set(f"transaction:{transaction_id}:pin", request.pin)
        return {"status": "pin_received"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook/twilio")
async def twilio_webhook(Body: str = Form(...), From: str = Form(...)):
    """
    Webhook for Twilio to handle APPROVE/REJECT responses.
    Note: Use Form(...) because Twilio sends data as form-urlencoded, not JSON.
    """
    print(f"Received message from {From}: {Body}")
    
    # Feature Disabled: We no longer support approval via WhatsApp to keep the project free (no ngrok required).
    return {"status": "feature_disabled"}

@app.post("/twilio/status")
async def twilio_status_webhook(
    MessageSid: str = Form(None),
    MessageStatus: str = Form(None),
    To: str = Form(None)
):
    """
    Handle Twilio Status Callback (Delivered, Read, etc.)
    """
    print(f"Twilio Status Update - SID: {MessageSid}, Status: {MessageStatus}, To: {To}")
    return {"status": "ok"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

from app.bank_portal import init_app as init_bank_portal
init_bank_portal(app)
