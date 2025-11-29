import asyncio
import os
import redis
from playwright.async_api import async_playwright, Page, Browser, Playwright

class BrowserAgent:
    def __init__(self):
        self.playwright: Playwright = None
        self.browser: Browser = None
        self.page: Page = None
        self.redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))

    async def start(self):
        """Initializes the Playwright instance and browser."""
        self.playwright = await async_playwright().start()
        # Launch headless for Docker environment
        self.browser = await self.playwright.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        self.page = await self.browser.new_page()

    async def stop(self):
        """Cleans up resources."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def execute_step(self, command: dict) -> any:
        """
        Executes a single step based on the provided JSON command.
        """
        if not self.page:
            await self.start()

        action = command.get("action")
        result = None
        
        if action == "navigate":
            url = command.get("url")
            if url:
                await self.page.goto(url)
                result = f"Navigated to {url}"
            else:
                raise ValueError("URL is required for navigate action")

        elif action == "fill":
            selector = command.get("selector")
            text = command.get("text")
            if selector and text is not None:
                await self.page.fill(selector, text)
                result = f"Filled {selector} with {text}"
            else:
                raise ValueError("Selector and text are required for fill action")

        elif action == "click":
            selector = command.get("selector")
            if selector:
                await self.page.click(selector)
                result = f"Clicked {selector}"
            else:
                raise ValueError("Selector is required for click action")

        elif action == "read":
            selector = command.get("selector")
            if selector:
                result = await self.page.inner_text(selector)
            else:
                raise ValueError("Selector is required for read action")
        
        elif action == "screenshot":
            path = command.get("path", "screenshot.png")
            await self.page.screenshot(path=path)
            result = f"Screenshot saved to {path}"

        elif action == "wait":
            selector = command.get("selector")
            state = command.get("state", "visible")
            if selector:
                await self.page.wait_for_selector(selector, state=state)
                result = f"Waited for {selector} to be {state}"
            else:
                raise ValueError("Selector is required for wait action")

        else:
            raise ValueError(f"Unknown action: {action}")

        # LIVE FEED: Save screenshot after every action
        try:
            # Ensure directory exists. In container, /app/static maps to ./static on host
            os.makedirs("/app/static", exist_ok=True)
            await self.page.screenshot(path="/app/static/live_feed.png")
        except Exception as e:
            print(f"Failed to save live feed screenshot: {e}")

        return result

    async def wait_for_pin(self, transaction_id: str) -> str:
        """
        Waits for a PIN to be set in Redis for the given transaction ID.
        """
        print(f"Waiting for PIN for transaction {transaction_id}...")
        # Poll every 1 second for 2 minutes
        for _ in range(120):
            pin = self.redis_client.get(f"transaction:{transaction_id}:pin")
            if pin:
                print(f"PIN received for {transaction_id}")
                return pin.decode()
            
            # Update live feed while waiting
            try:
                if self.page:
                    await self.page.screenshot(path="/app/static/live_feed.png")
            except Exception as e:
                print(f"Failed to update live feed during wait: {e}")
                
            await asyncio.sleep(1)
        
        raise TimeoutError(f"Timed out waiting for PIN for transaction {transaction_id}")
