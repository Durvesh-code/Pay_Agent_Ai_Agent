import requests
import time
import os

API_URL = "http://localhost:8000"

def create_test_invoice():
    content = """
    INVOICE
    Vendor: Acme Corp
    Date: 2023-10-27
    Invoice #: INV-001
    
    Items:
    - Consulting Services: $500.00
    
    Total: $500.00
    
    Bank Details:
    Account Number: 1234567890
    IFSC Code: TEST0001
    Remarks: Project Alpha
    """
    with open("test_invoice.txt", "w") as f:
        f.write(content)
    return "test_invoice.txt"

def login():
    print("Logging in...")
    try:
        response = requests.post(f"{API_URL}/token", data={"username": "admin@example.com", "password": "password"})
        if response.status_code == 200:
            token = response.json().get("access_token")
            print("Login successful.")
            return token
        else:
            print(f"Login failed: {response.text}")
            return None
    except Exception as e:
        print(f"Login error: {e}")
        return None

def test_gemini_flow():
    token = login()
    if not token:
        return
    
    headers = {"Authorization": f"Bearer {token}"}

    print("Creating test invoice...")
    filename = create_test_invoice()
    
    # 1. Upload Invoice
    print("Uploading invoice...")
    with open(filename, "rb") as f:
        files = {"file": (filename, f, "text/plain")}
        try:
            response = requests.post(f"{API_URL}/upload", files=files, headers=headers)
            print(f"Upload response: {response.status_code} {response.text}")
            if response.status_code != 200:
                print("Upload failed.")
                return
            data = response.json()
            invoice_id = data.get("invoice_id")
            print(f"Invoice ID: {invoice_id}")
        except Exception as e:
            print(f"Upload failed with error: {e}")
            return

    # 2. Poll for Extraction (NEEDS_APPROVAL)
    print("Waiting for extraction (NEEDS_APPROVAL)...")
    transaction_id = None
    start_time = time.time()
    while time.time() - start_time < 60:
        try:
            response = requests.get(f"{API_URL}/transactions/pending", headers=headers)
            transactions = response.json()
            # Find our transaction (assuming batch_id matches invoice_id)
            for tx in transactions:
                if tx.get("batch_id") == invoice_id:
                    transaction_id = tx.get("id")
                    print(f"Transaction found: {transaction_id}")
                    break
            if transaction_id:
                break
        except Exception as e:
            print(f"Polling error: {e}")
        time.sleep(2)
    
    if not transaction_id:
        print("Timeout waiting for extraction.")
        return

    # 3. Approve Transaction
    print(f"Approving transaction {transaction_id}...")
    requests.post(f"{API_URL}/transactions/{transaction_id}/approve", headers=headers)
    
    # 4. Poll for WAITING_FOR_PIN
    print("Waiting for WAITING_FOR_PIN...")
    start_time = time.time()
    while time.time() - start_time < 120:
        response = requests.get(f"{API_URL}/transactions/{transaction_id}", headers=headers)
        status = response.json().get("status")
        print(f"Status: {status}")
        if status == "WAITING_FOR_PIN":
            break
        if status == "FAILED":
            print("Transaction Failed.")
            return
        time.sleep(2)
    else:
        print("Timeout waiting for PIN status.")
        return

    # 5. Provide PIN
    print("Providing PIN...")
    requests.post(f"{API_URL}/transactions/{transaction_id}/provide_pin", json={"pin": "123456"}, headers=headers)
    
    # 6. Poll for PAID
    print("Waiting for PAID...")
    start_time = time.time()
    while time.time() - start_time < 60:
        response = requests.get(f"{API_URL}/transactions/{transaction_id}", headers=headers)
        status = response.json().get("status")
        print(f"Status: {status}")
        if status == "PAID":
            print("SUCCESS: Transaction PAID!")
            return
        time.sleep(2)
    
    print("Timeout waiting for PAID.")

if __name__ == "__main__":
    test_gemini_flow()
