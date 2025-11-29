import requests
import time
import os

BASE_URL = "http://localhost:8000"

def test_flow():
    print("🚀 Starting End-to-End Test...")
    
    # 1. Create a dummy invoice file
    with open("test_invoice.txt", "w") as f:
        f.write("Vendor: Test Corp\nAmount: 1500\nAccount: 1234567890\nIFSC: HDFC0001234")
        
    # 2. Upload File
    print("📤 Uploading file...")
    with open("test_invoice.txt", "rb") as f:
        files = {'file': ('test_invoice.txt', f, 'text/plain')}
        # Note: The portal upload endpoint doesn't require auth for simplicity in this test
        response = requests.post(f"{BASE_URL}/api/upload", files=files)
        
    if response.status_code != 200:
        print(f"❌ Upload Failed: {response.text}")
        return
        
    invoice_id = response.json().get("invoice_id")
    print(f"✅ Uploaded. Invoice ID: {invoice_id}")
    
    # 3. Poll for Status in Portal
    print("⏳ Waiting for processing...")
    for _ in range(30): # Wait up to 30 seconds
        response = requests.get(f"{BASE_URL}/api/invoices/{invoice_id}")
        if response.status_code == 200:
            data = response.json()
            state = data.get("state")
            print(f"   Current State: {state}")
            
            if state == "needs_approval":
                print("✅ Processing Complete! Invoice is ready for approval.")
                
                # 4. Verify Data
                amount = data.get("amount")
                print(f"   Extracted Amount: {amount}")
                return
                
        time.sleep(1)
        
    print("❌ Timeout waiting for processing.")

if __name__ == "__main__":
    test_flow()
