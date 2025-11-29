# User Manual: Agentic Payment Assistant

This manual provides a complete guide to setting up, running, and using the Agentic Payment Assistant.

## 1. System Overview
The Agentic Payment Assistant is an AI-powered system that automates invoice processing and payments.
-   **Input**: PDF Invoices (Single or Batch).
-   **AI**: Extracts transaction details (Vendor, Amount, Account No).
-   **Approval**: Hybrid (Web Dashboard or WhatsApp).
-   **Execution**: A Browser Agent logs into a Mock Bank and processes payments sequentially.

## 2. Prerequisites
-   **Docker Desktop**: Must be installed and running.
-   **Twilio Account**: For WhatsApp notifications (SID, Token, Numbers).
-   **Gemini API Key**: For AI extraction.
-   **Ngrok**: For exposing the local server to Twilio webhooks.

## 3. Installation & Setup

### Step 1: Clone & Configure
1.  **Clone the repository** to your local machine.
2.  **Create `.env` file**: Copy `.env.example` to `.env` and fill in your credentials:
    ```ini
    GEMINI_API_KEY=your_key
    TWILIO_ACCOUNT_SID=your_sid
    TWILIO_AUTH_TOKEN=your_token
    TWILIO_FROM_NUMBER=whatsapp:+14155238886
    TWILIO_TO_NUMBER=whatsapp:+919999999999
    DATABASE_URL=postgresql://user:password@db:5432/payment_assistant
    REDIS_URL=redis://redis:6379/0
    MOCK_BANK_URL=http://mock-bank
    ```

### Step 2: Start Services
Run the following command in the project root:
```bash
docker-compose up -d --build
```
This starts:
-   **Frontend**: `http://localhost:3000`
-   **Backend**: `http://localhost:8000`
-   **Mock Bank**: `http://localhost:8080`
-   **Worker**: Background task processor.
-   **Database & Redis**.

### Step 3: Setup Webhooks (Optional)
*Skipped: We have removed the requirement for Ngrok to keep the project completely free. You will receive WhatsApp notifications, but approval must be done via the Dashboard.*

## 4. How to Use (The "Perfect Flow")

### Step 1: Upload Invoice
1.  Open the **Dashboard** at [http://localhost:3000](http://localhost:3000).
2.  Go to the **"Invoices"** tab.
3.  **Upload** a PDF invoice (single or multi-page).
4.  The system will extract data and auto-switch to the **"Verification Queue"**.

### Step 2: Review & Approve
1.  In the **"Verification Queue"**, review the extracted transactions.
2.  **Batch Approval**: Click the **"Approve All"** button at the top right.

### Step 3: Agent Execution (Live Monitor)
1.  Once approved, the **Live Monitor** will open automatically (or click "Processing..." on any transaction).
2.  **Watch the Agent**: You will see a live feed of the browser logging into the bank.
3.  **Enter PIN**:
    *   The agent will pause and ask for a PIN.
    *   Enter the PIN (e.g., `123456`) in the monitor window **ONCE**.
    *   Click **"Authorize"**.
4.  **Sit Back**: The agent will now process **all** transactions in the batch sequentially using that single PIN.

### Step 4: Verification
1.  Watch the status change to **`PAID`** for all items.
2.  Check the **"Audit Logs"** tab for payment screenshots and details.

## 5. Troubleshooting

### Common Issues
-   **Agent Stuck on Login**: Ensure the Mock Bank is running and the "Sign In" button works manually at `http://localhost:8080`.
-   **"Processing..." Forever**: Check worker logs (`docker logs hacks_project_fintechh-worker-1`).
-   **Twilio Error**: Verify `TWILIO_TO_NUMBER` is set in `.env`.

### Resetting the System
To clear all data and start fresh:
1.  **Clear Database**:
    ```bash
    docker-compose exec db psql -U postgres -d payment_assistant -c "DELETE FROM transactions;"
    ```
2.  **Restart Services**:
    ```bash
    docker-compose restart worker
    ```

## 6. Credentials
-   **Mock Bank Login**:
    -   **User**: `admin`
    -   **Password**: `password123`
    -   **PIN**: Any 6-digit number (e.g., `123456`)
