import requests
import time
import os

# Configuration
API_URL = "http://localhost:8000"
USERNAME = "admin@example.com"
PASSWORD = "password"

def login():
    print(f"Logging in as {USERNAME}...")
    try:
        response = requests.post(f"{API_URL}/token", data={"username": USERNAME, "password": PASSWORD})
        response.raise_for_status()
        token = response.json()["access_token"]
        print("✅ Login Successful")
        return token
    except Exception as e:
        print(f"❌ Login Failed: {e}")
        return None

def upload_file(token, file_path):
    print(f"Uploading {file_path}...")
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return

    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            headers = {'Authorization': f'Bearer {token}'}
            response = requests.post(f"{API_URL}/upload", headers=headers, files=files)
            response.raise_for_status()
            print(f"✅ Upload Successful: {response.json()}")
            return response.json().get("invoice_id")
    except Exception as e:
        print(f"❌ Upload Failed: {e}")
        return None

def check_transactions(token):
    print("Checking for pending transactions...")
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{API_URL}/transactions/pending", headers=headers)
        response.raise_for_status()
        transactions = response.json()
        print(f"Found {len(transactions)} pending transactions:")
        for tx in transactions:
            print(f"  - [{tx['status']}] {tx['vendor']}: ${tx['amount']} (Acct: {tx['account_number']})")
            if tx['status'] == 'NEEDS_REVIEW':
                print("    ⚠️  NEEDS REVIEW - Missing Account Number!")
        return transactions
    except Exception as e:
        print(f"❌ Check Failed: {e}")
        return []

if __name__ == "__main__":
    # Wait for server to be ready
    print("Waiting for server to start...")
    time.sleep(5) 
    
    token = login()
    if token:
        # Upload Test Files
        test_files = [
            "test_data/uploaded_image_0.jpg",
            "test_data/uploaded_image_1.jpg"
        ]
        
        for file_path in test_files:
            if os.path.exists(file_path):
                upload_file(token, file_path)
                time.sleep(2) # Wait for processing
        
        # Poll for results
        for _ in range(5):
            print("\nPolling...")
            txs = check_transactions(token)
            if txs:
                break
            time.sleep(3)
