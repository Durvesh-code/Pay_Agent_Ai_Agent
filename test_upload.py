import requests
import os

BASE_URL = "http://localhost:8000"
TEST_FILE = r"c:\Users\patil\Desktop\Hacks_project_fintechh\test_data\uploaded_image_0.jpg"

def upload_invoice():
    # 1. Login
    print("Logging in...")
    resp = requests.post(f"{BASE_URL}/token", data={"username": "admin@example.com", "password": "password"})
    if resp.status_code != 200:
        print(f"Login Failed: {resp.text}")
        return
    
    token = resp.json()["access_token"]
    print(f"Got token: {token[:10]}...")

    # 2. Upload
    print(f"Uploading {TEST_FILE}...")
    with open(TEST_FILE, "rb") as f:
        files = {"file": f}
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(f"{BASE_URL}/upload", files=files, headers=headers)
        
    if resp.status_code == 200:
        print(f"Upload Success: {resp.json()}")
    else:
        print(f"Upload Failed: {resp.text}")

if __name__ == "__main__":
    upload_invoice()
