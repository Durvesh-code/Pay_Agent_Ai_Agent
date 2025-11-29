import requests

url = "http://localhost:8000/token"
data = {
    "username": "admin@example.com",
    "password": "password"
}

try:
    response = requests.post(url, data=data)
    if response.status_code == 200:
        print("Login Successful")
        print(response.json())
    else:
        print(f"Login Failed: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Error: {e}")
