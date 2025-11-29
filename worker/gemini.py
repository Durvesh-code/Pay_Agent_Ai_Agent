import os
import google.generativeai as genai
import json
import time
from dotenv import load_dotenv

load_dotenv()

class GeminiProcessor:
    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("❌ ERROR: GOOGLE_API_KEY is missing in .env!")
            return
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def extract_invoice_data(self, file_path: str):
        print(f"📂 Uploading {file_path} to Gemini...")
        
        try:
            # Upload
            sample_file = genai.upload_file(path=file_path, display_name="Invoice")
            
            # Wait for processing
            while sample_file.state.name == "PROCESSING":
                time.sleep(1)
                sample_file = genai.get_file(sample_file.name)

            # Robust Prompt for Handwritten/Printed Text
            prompt = """
            Extract payment data from this image. It may contain HANDWRITTEN or printed text.
            Look for a table or list of transactions.
            Return a JSON object with a 'transactions' list.
            Each item MUST have: 'vendor' (or Name), 'amount', 'account_number', 'ifsc_code'.
            If 'account_number' is missing/illegible, set it to null.
            Do NOT use markdown. Return raw JSON only.
            """

            response = self.model.generate_content([sample_file, prompt])
            raw_text = response.text.strip()

            # CLEANUP: Remove ```json and ``` if present
            if "```" in raw_text:
                raw_text = raw_text.replace("```json", "").replace("```", "").strip()

            print(f"🤖 Gemini Raw Response: {raw_text[:500]}...", flush=True) # Debug print with flush

            data = json.loads(raw_text)
            
            # Ensure list structure
            if isinstance(data, list):
                return {"transactions": data}
            if "transactions" not in data:
                return {"transactions": [data]}
                
            return data

        except Exception as e:
            print(f"❌ Extraction Error: {str(e)}")
            return {"transactions": []}
