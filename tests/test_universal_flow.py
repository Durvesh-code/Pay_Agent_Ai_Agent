import asyncio
import os
import sys
import json
from unittest.mock import MagicMock, patch

# Mock dependencies before import
sys.modules["asyncpg"] = MagicMock()
sys.modules["celery"] = MagicMock()
sys.modules["redis"] = MagicMock()
sys.modules["twilio.rest"] = MagicMock()
sys.modules["core.browser_engine"] = MagicMock()

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worker.tasks import process_invoice
from worker.gemini import GeminiProcessor

# Mock Data
MOCK_SINGLE_TX = {
    "transactions": [
        {
            "vendor": "Single Vendor",
            "amount": 100.0,
            "account_number": "1234567890",
            "ifsc_code": "IFSC001",
            "remarks": "Single Invoice"
        }
    ]
}

MOCK_BULK_TX = {
    "transactions": [
        {
            "vendor": "Bulk Vendor 1",
            "amount": 50.0,
            "account_number": "11111",
            "ifsc_code": "IFSC001",
            "remarks": "Bulk 1"
        },
        {
            "vendor": "Bulk Vendor 2",
            "amount": 75.0,
            "account_number": "22222",
            "ifsc_code": "IFSC002",
            "remarks": "Bulk 2"
        }
    ]
}

MOCK_MISSING_DATA_TX = {
    "transactions": [
        {
            "vendor": "Messy Vendor",
            "amount": 200.0,
            "account_number": None, # Missing!
            "ifsc_code": "IFSC003",
            "remarks": "Handwritten note"
        }
    ]
}

async def test_universal_flow():
    print("--- Starting Universal Flow Test ---")
    
    # Mock Gemini Processor
    with patch('worker.tasks.gemini_processor') as mock_gemini:
        
        # Scenario 1: Single Transaction
        print("\n[Scenario 1] Single Transaction (Standard)")
        mock_gemini.extract_invoice_data.return_value = MOCK_SINGLE_TX
        
        # We mock the DB connection to avoid needing the actual DB running for this logic test
        # But wait, the task uses asyncpg.connect. We should mock that too or run against real DB if available.
        # Since DB might be rebuilding, let's mock asyncpg to verify LOGIC only.
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            # Async mock for execute
            async def async_execute(*args, **kwargs):
                print(f"  DB Execute: {args[0].strip().split()[0]} ... Status={args[-2]}")
                return "INSERT 0 1"
            
            mock_conn.execute.side_effect = async_execute
            mock_conn.close.side_effect = asyncio.Future
            mock_conn.close.return_value = None

            # Run Task
            process_invoice("dummy.pdf", "batch_001", "user_123")
            
        # Scenario 2: Bulk Transactions
        print("\n[Scenario 2] Bulk Transactions (Multiple Rows)")
        mock_gemini.extract_invoice_data.return_value = MOCK_BULK_TX
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            async def async_execute(*args, **kwargs):
                print(f"  DB Execute: {args[0].strip().split()[0]} ... Vendor={args[2]}, Status={args[-2]}")
                return "INSERT 0 1"
            mock_conn.execute.side_effect = async_execute
            mock_conn.close.return_value = None
            
            process_invoice("bulk.pdf", "batch_002", "user_123")

        # Scenario 3: Missing Data (Needs Review)
        print("\n[Scenario 3] Missing Data (Handwritten/Messy)")
        mock_gemini.extract_invoice_data.return_value = MOCK_MISSING_DATA_TX
        
        with patch('asyncpg.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            async def async_execute(*args, **kwargs):
                status = args[-2]
                print(f"  DB Execute: {args[0].strip().split()[0]} ... Vendor={args[2]}, Status={status}")
                if status == 'NEEDS_REVIEW':
                    print("  ✅ CORRECT: Status is NEEDS_REVIEW due to missing account number.")
                else:
                    print(f"  ❌ WRONG STATUS: {status}")
                return "INSERT 0 1"
            mock_conn.execute.side_effect = async_execute
            mock_conn.close.return_value = None
            
            process_invoice("messy_note.jpg", "batch_003", "user_123")

if __name__ == "__main__":
    # Run the async test
    # We need to mock the celery task wrapper since we are calling the function directly
    # But process_invoice is decorated. We can access the original function via .__wrapped__ if needed, 
    # or just call it if Celery isn't eager.
    # Actually, calling the decorated function usually adds it to the queue.
    # Let's import the function logic directly if possible or mock Celery.
    
    # Simpler: Just extract the logic from the task into a helper or run this test assuming the imports work.
    # The imports in worker/tasks.py might fail if celery isn't setup.
    # Let's try running it.
    try:
        asyncio.run(test_universal_flow())
    except Exception as e:
        print(f"Test Failed: {e}")
