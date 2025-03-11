from playwright.sync_api import sync_playwright
import json

FB_EMAIL = "0853771565"
FB_PASSWORD = "Tuyetnhi98@"

def save_facebook_session():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Set to True if you don't need a UI
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.facebook.com/login", timeout=60000)

        # # Manually log in to Facebook
        # input("After logging in, press Enter to continue...")

        # Save session storage & cookies
        storage = context.storage_state()
        with open("fb_session.json", "w") as f:
            json.dump(storage, f)

        print("✅ Session saved!")
        browser.close()

save_facebook_session()
