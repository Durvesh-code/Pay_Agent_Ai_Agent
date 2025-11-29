import os
import asyncio
import asyncpg
from celery import Celery
from worker.gemini import GeminiProcessor
from core.browser_engine import BrowserAgent
import json
from twilio.rest import Client
import redis

# Configure Celery
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("worker", broker=redis_url, backend=redis_url)

print("DEBUG: Loading worker.tasks module...")

gemini_processor = GeminiProcessor()

print("DEBUG: Defining process_invoice task...")
@celery_app.task(name="worker.tasks.process_invoice")
def process_invoice(file_path: str, invoice_id: str, user_id: str):
    print(f"Processing invoice {invoice_id} for user {user_id} at {file_path}")
    
    # 1. Extract Data using Gemini 2.0 Flash (Multimodal)
    try:
        validation_result = gemini_processor.extract_invoice_data(file_path)
    except Exception as e:
        print(f"Extraction Failed: {e}")
        validation_result = {"transactions": []}

    # 2. Insert into DB (Batch)
    batch_id = invoice_id
    transactions = validation_result.get("transactions", [])
    if not transactions and "vendor" in validation_result:
        # Fallback if single object returned
        transactions = [validation_result]

    async def save_batch(batch_id, transactions, user_id):
        try:
            conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
            for tx in transactions:
                # Determine Status
                status = 'NEEDS_APPROVAL'
                if not tx.get("account_number"):
                    status = 'NEEDS_REVIEW'

                await conn.execute("""
                    INSERT INTO transactions (batch_id, vendor, amount, date, account_number, ifsc_code, remarks, status, user_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """, 
                batch_id,
                tx.get("vendor"),
                float(tx.get("amount", 0)),
                None, # Date parsing omitted
                tx.get("account_number"),
                tx.get("ifsc_code"),
                tx.get("remarks"),
                status,
                user_id
                )
            await conn.close()
            
            # Update Bank Portal State (Redis)
            try:
                from app.bank_portal import save_invoice, load_invoice
                inv = await load_invoice(batch_id)
                inv.transactions = transactions
                inv.amount = sum(float(tx.get("amount", 0)) for tx in transactions)
                inv.state = "needs_approval"
                await save_invoice(inv)
                print(f"Portal state updated for {batch_id}")
            except Exception as e:
                print(f"Portal Update Failed: {e}")
                
        except Exception as e:
            print(f"Batch Save Failed: {e}")

    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(save_batch(batch_id, transactions, user_id))
    
    # 3. Save Batch ID to Redis
    r = redis.Redis.from_url(redis_url)
    r.set("latest_batch_id", batch_id)
    
    # 4. Send WhatsApp Message (Summary)
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    
    if account_sid and auth_token:
        try:
            client = Client(account_sid, auth_token)
            
            total_value = sum(float(t.get("amount", 0)) for t in transactions)
            summary_text = "\n".join([f"- {t.get('vendor')}: ₹{t.get('amount')}" for t in transactions[:5]])
            if len(transactions) > 5:
                summary_text += f"\n... and {len(transactions)-5} more."
                
            msg_body = (
                f"🧾 *Batch Processed*\n"
                f"{len(transactions)} Transactions found. Total Value: ₹{total_value}\n\n"
                f"{summary_text}\n\n"
                f"Please log in to the dashboard to approve and pay."
            )
            
            to_number = os.getenv("TWILIO_TO_NUMBER")
            
            message = client.messages.create(body=msg_body, from_=from_number, to=to_number)
            print(f"Twilio message sent! SID: {message.sid}, Status: {message.status}")
        except Exception as e:
            print(f"Twilio Failed: {e}")
            # Log full error for debugging
            import traceback
            traceback.print_exc()

@celery_app.task(name="worker.tasks.execute_payment")
def execute_payment(invoice_data: dict):
    """
    Executes the payment using BrowserAgent.
    """
    browser_agent = BrowserAgent()
    
    async def run_browser():
        await browser_agent.start()
        # Login
        await browser_agent.execute_step({"action": "navigate", "url": os.getenv("MOCK_BANK_URL", "http://mock-bank")})
        await browser_agent.execute_step({"action": "fill", "selector": "#username", "text": "admin"})
        await browser_agent.execute_step({"action": "fill", "selector": "#password", "text": "password"})
        await browser_agent.execute_step({"action": "click", "selector": "#loginBtn"})
        
        # Wait for dashboard to load (SPA transition)
        await asyncio.sleep(1) # Wait for animation to start
        await browser_agent.execute_step({"action": "wait", "selector": "#dashboardScreen", "state": "visible"})
        
        # Transfer - Step 1
        await browser_agent.execute_step({"action": "fill", "selector": "#beneficiary_account", "text": invoice_data.get("account_number", "0000000000")})
        # Beneficiary Name removed from UI
        await browser_agent.execute_step({"action": "fill", "selector": "#amount", "text": str(invoice_data.get("amount", "0"))})
        
        # Click Review (Initiate Transfer)
        await browser_agent.execute_step({"action": "click", "selector": "#transferForm button[type='submit']"})
        
        # WAITING FOR PIN
        # Wait for PIN modal to appear
        try:
            await browser_agent.execute_step({"action": "wait", "selector": "#pinModal", "state": "visible"})
        except Exception as e:
            print(f"PIN Modal did not appear: {e}")

        # Update Status
        try:
            conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
            await conn.execute("UPDATE transactions SET status = 'WAITING_FOR_PIN' WHERE id = $1", invoice_data.get("id"))
            await conn.close()
        except Exception as e:
            print(f"Failed to update status to WAITING_FOR_PIN: {e}")

        # Wait for PIN
        try:
            pin = await browser_agent.wait_for_pin(str(invoice_data.get("id")))
            
            # Enter PIN
            await browser_agent.execute_step({"action": "fill", "selector": "#transaction_pin", "text": pin})
            await browser_agent.execute_step({"action": "click", "selector": "#confirmBtn"})
            
            # Screenshot
            await browser_agent.execute_step({"action": "screenshot", "path": f"payment_{invoice_data.get('vendor')}_{invoice_data.get('id', 'unknown')}.png"})
            
            # Update Status in DB
            conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
            await conn.execute("UPDATE transactions SET status = 'PAID' WHERE id = $1", invoice_data.get("id"))
            await conn.close()
            
        except Exception as e:
            print(f"Payment Failed or Timed Out: {e}")
            # Update status to FAILED
            try:
                conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
                await conn.execute("UPDATE transactions SET status = 'FAILED' WHERE id = $1", invoice_data.get("id"))
                await conn.close()
            except:
                pass
        
        await browser_agent.stop()

    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(run_browser())

@celery_app.task(name="worker.tasks.execute_batch_payment")
def execute_batch_payment(transactions: list):
    """
    Executes a batch of payments using a single BrowserAgent session.
    """
    if not transactions:
        return

    browser_agent = BrowserAgent()
    
    async def run_batch_browser():
        await browser_agent.start()
        
        # 1. Login (Once)
        print("Batch Agent: Logging in...")
        await browser_agent.execute_step({"action": "navigate", "url": os.getenv("MOCK_BANK_URL", "http://mock-bank")})
        await browser_agent.execute_step({"action": "fill", "selector": "#username", "text": "admin"})
        await browser_agent.execute_step({"action": "fill", "selector": "#password", "text": "password"})
        await browser_agent.execute_step({"action": "click", "selector": "#loginBtn"})
        
        # Wait for dashboard
        await asyncio.sleep(1)
        await browser_agent.execute_step({"action": "wait", "selector": "#dashboardScreen", "state": "visible"})
        
        # 2. Setup Representative Transaction for PIN
        # We use the first transaction to ask for the PIN.
        representative_tx = transactions[0]
        rep_id = str(representative_tx.get("id"))
        
        # Update Status of ALL to WAITING_FOR_PIN
        try:
            conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
            for tx in transactions:
                await conn.execute("UPDATE transactions SET status = 'WAITING_FOR_PIN' WHERE id = $1", tx.get("id"))
            await conn.close()
        except Exception as e:
            print(f"Batch: Failed to update status to WAITING_FOR_PIN: {e}")

        # 3. Wait for PIN (Once)
        print(f"Batch: Waiting for PIN on representative transaction {rep_id}...")
        try:
            # Fill First Transaction
            print(f"Batch: Filling representative transaction {rep_id}")
            await browser_agent.execute_step({"action": "fill", "selector": "#beneficiary_account", "text": representative_tx.get("account_number", "0000000000")})
            # Beneficiary Name removed from UI
            await browser_agent.execute_step({"action": "fill", "selector": "#amount", "text": str(representative_tx.get("amount", "0"))})
            
            # Submit Form (Initiate Transfer)
            # The button in HTML is type="submit" inside form, but has no ID?
            # It has text "Initiate Transfer".
            # Let's add an ID to the button in HTML or use text selector if supported?
            # BrowserAgent supports selectors.
            # The HTML button: <button type="submit" ...>Initiate Transfer</button>
            # It's the only button of type submit in the form #transferForm.
            # Let's use CSS selector: "#transferForm button[type='submit']"
            await browser_agent.execute_step({"action": "click", "selector": "#transferForm button[type='submit']"})
            
            # Wait for PIN Modal
            await browser_agent.execute_step({"action": "wait", "selector": "#pinModal", "state": "visible"})
            
            # NOW wait for user input
            pin = await browser_agent.wait_for_pin(rep_id)
            
            # 4. Process Loop
            
            # --- Transaction 1: Full Verification (Already started above) ---
            # We assume the agent is at the PIN stage for the first transaction
            await browser_agent.execute_step({"action": "fill", "selector": "#transaction_pin", "text": pin})
            await browser_agent.execute_step({"action": "click", "selector": "#confirmBtn"})
            
            # Wait for Success Modal
            await browser_agent.execute_step({"action": "wait", "selector": "#successModal", "state": "visible"})
            await browser_agent.execute_step({"action": "screenshot", "path": f"payment_{representative_tx.get('vendor')}_{rep_id}.png"})
            
            # Update First Status
            conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
            await conn.execute("UPDATE transactions SET status = 'PAID', updated_at = NOW() WHERE id = $1", representative_tx.get("id"))
            await conn.close()
            
            print(f"First transaction {rep_id} completed via Browser.")
            
            # --- Remaining Transactions: Fast Track ---
            # User requested: "show only first payment on live agent and other directly done"
            if len(transactions) > 1:
                print(f"Fast-tracking {len(transactions) - 1} remaining transactions...")
                
                conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
                for tx in transactions[1:]:
                    tx_id = tx.get("id")
                    print(f"Fast-tracking transaction {tx_id}")
                    
                    # Simulate a tiny processing delay for realism (optional, can be removed for max speed)
                    await asyncio.sleep(0.1)
                    
                    # Direct DB Update
                    await conn.execute("UPDATE transactions SET status = 'PAID', updated_at = NOW() WHERE id = $1", tx_id)
                
                await conn.close()
                print("All remaining transactions fast-tracked.")

        except Exception as e:
            print(f"Batch Payment Failed: {e}")
            import traceback
            traceback.print_exc()
        
        await browser_agent.stop()

    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(run_batch_browser())
