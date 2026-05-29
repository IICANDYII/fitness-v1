# -*- coding: utf-8 -*-
"""Debug the legs-for-advanced-lifters page structure."""
from playwright.sync_api import sync_playwright

URL = "https://musclewiki.com/zh-cn/workout/legs-for-advanced-lifters"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        locale="zh-CN",
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=40000)

    # Try waiting longer
    try:
        page.wait_for_selector("div.sticky.inset-x-0.z-10 button", timeout=20000)
        print("Selector found!")
    except Exception as e:
        print(f"Selector timeout: {e}")

    page.wait_for_timeout(3000)

    # Check page title
    print("Title:", page.title())

    # All buttons
    all_btns = page.query_selector_all("button")
    print(f"Total buttons: {len(all_btns)}")
    for b in all_btns[:10]:
        t = b.inner_text().strip().replace("\n", " ")[:60]
        c = (b.get_attribute("class") or "")[:40]
        print(f"  [{c}] {t}")

    # Check sticky
    sticky = page.query_selector("div.sticky.inset-x-0")
    print(f"\nSticky panel: {'found' if sticky else 'NOT found'}")
    if sticky:
        stk_btns = sticky.query_selector_all("button")
        print(f"Sticky buttons: {len(stk_btns)}")
        for b in stk_btns:
            t = b.inner_text().strip()[:60]
            if t:
                print(f"  {t}")

    # Check if page has any workout content
    print("\nBody text snippet:")
    print(page.inner_text("body")[:400])

    browser.close()
