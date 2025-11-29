import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMWorker:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
        self.system_prompt = (
            "Analyze the document and extract ALL distinct transactions. Return a JSON Object containing a key 'transactions' which is an ARRAY of objects. Each object must have: {vendor, amount, date, account_number, ifsc_code, remarks}."
        )

    async def get_action(self, user_instruction: str, context: str = "") -> dict:
        """
        Validates the invoice text and extracts details.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Context: {context}\nInput: {user_instruction}"}
        ]

        try:
            response = await self.client.chat.completions.create(
                model="meta-llama/llama-3.1-70b-instruct", # Running on Groq via OpenRouter
                messages=messages,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            # Clean markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content.strip())
        except Exception as e:
            print(f"Error calling LLM: {e}")
            return {"error": str(e)}
