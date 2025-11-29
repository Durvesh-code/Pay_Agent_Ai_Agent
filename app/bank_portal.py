# app/bank_portal.py
import os
import uuid
import json
from fastapi import APIRouter, FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
import asyncio
import redis.asyncio as redis
from typing import Optional, List

router = APIRouter(prefix="/api")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = None

# invoice model stored in redis as JSON
class Invoice(BaseModel):
    id: str
    filename: str
    uploader: Optional[str] = None
    state: str  # uploaded, processing, needs_approval, approved, paid, pin_required, completed
    amount: float = 0.0
    transactions: Optional[list] = []
    created_at: float = 0.0

async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client

# helper to store / get invoice
async def save_invoice(inv: Invoice):
    r = await get_redis()
    await r.hset("invoices", inv.id, inv.json())

async def load_invoice(invoice_id: str) -> Invoice:
    r = await get_redis()
    raw = await r.hget("invoices", invoice_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return Invoice.parse_raw(raw)

async def list_pending():
    r = await get_redis()
    all_vals = await r.hvals("invoices")
    results = []
    for raw in all_vals:
        inv = Invoice.parse_raw(raw)
        if inv.state in ("needs_approval", "uploaded", "processing"):
            results.append(inv)
    return results

# 1. Upload endpoint
@router.post("/upload")
async def upload_file(file: UploadFile = File(...), uploader: Optional[str] = None):
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty file")

    invoice_id = str(uuid.uuid4())
    save_path = f"./uploads/{invoice_id}_{file.filename}"
    os.makedirs("./uploads", exist_ok=True)
    with open(save_path, "wb") as f:
        f.write(contents)

    inv = Invoice(
        id=invoice_id,
        filename=os.path.basename(save_path),
        uploader=uploader,
        state="uploaded",
        amount=0.0,
        transactions=[],
        created_at=asyncio.get_event_loop().time(),
    )
    await save_invoice(inv)

    # enqueue Celery extraction, passing file path and invoice_id
    # We import here to avoid circular imports if any
    from worker.tasks import process_invoice
    # Note: process_invoice signature in worker/tasks.py is (file_path, invoice_id, user_id)
    # We pass uploader as user_id or a default if None
    user_id = uploader if uploader else "portal_user"
    process_invoice.delay(save_path, invoice_id, user_id)
    
    return JSONResponse({"invoice_id": invoice_id})

# 2. List pending for portal
@router.get("/invoices/pending")
async def get_pending():
    items = await list_pending()
    return [i.dict() for i in items]

# 3. Approve endpoint (single or bulk)
class ApproveRequest(BaseModel):
    mode: str  # "single" or "bulk"
    transaction_ids: Optional[List[str]] = None  # for bulk, list of txn ids
    amount: Optional[float] = None

@router.post("/invoices/{invoice_id}/approve")
async def approve_invoice(invoice_id: str, req: ApproveRequest):
    inv = await load_invoice(invoice_id)
    # simple handling: mark approved and prepare mockbank payload
    inv.state = "approved"
    if req.amount:
        inv.amount = req.amount
    # For bulk, you can record transaction_ids. For our simplified flow we proceed to payment.
    await save_invoice(inv)
    # optionally return payment URL (in single host, this will be a local route)
    payment_url = f"/api/mockbank/pay?invoice_id={invoice_id}"
    return {"status": "approved", "payment_url": payment_url}

# 4. Mock bank payment (simulate payment and optionally require pin)
class MockPayReq(BaseModel):
    invoice_id: str
    card_number: Optional[str] = None  # in mock only
    cvv: Optional[str] = None

@router.post("/mockbank/pay")
async def mock_pay(req: MockPayReq):
    inv = await load_invoice(req.invoice_id)
    # simulate call to a mock bank and decide if a PIN is required
    inv.state = "paid"  # or pin_required
    # For demo: if amount > 1000 require PIN
    if inv.amount > 1000:
        inv.state = "pin_required"
    await save_invoice(inv)
    return {"status": inv.state, "invoice_id": inv.id}

# 5. PIN submission
class PinReq(BaseModel):
    invoice_id: str
    pin: str

@router.post("/mockbank/pin")
async def submit_pin(req: PinReq):
    inv = await load_invoice(req.invoice_id)
    # verify pin (mock logic)
    if req.pin == "1234":
        inv.state = "completed"
        await save_invoice(inv)
        # final redirect
        return {"status": "completed", "redirect_url": "http://localhost:3000/success"}
    else:
        raise HTTPException(status_code=400, detail="Invalid PIN")

# a convenience route to fetch an invoice
@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    inv = await load_invoice(invoice_id)
    return inv.dict()

# include router in app main (in your app.main)
def init_app(app: FastAPI):
    app.include_router(router)
