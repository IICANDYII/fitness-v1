# -*- coding: utf-8 -*-
"""Test page structure analysis for one workout plan."""
import json
from playwright.sync_api import sync_playwright

TEST_URL = "https://musclewiki.com/zh-cn/workout/full-body-bodybuilding-workout-day-one"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="zh-CN",
        )
        page = ctx.new_page()
        page.goto(TEST_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # ---- Exercise buttons ----
        btn_container_sel = (
            "div.lg\\:grid.grid-flow-col.mt-6.hidden.text-xs"
        )
        btns = page.query_selector_all(f"{btn_container_sel} button")
        print(f"Buttons found (hidden desktop grid): {len(btns)}")

        # Try broader selector
        # The user says the buttons are inside a specific div
        btns2 = page.query_selector_all("button[aria-label*='workout']")
        print(f"Buttons with aria-label 'workout': {len(btns2)}")

        # Look for exercise name buttons - try any button in the top sticky panel
        sticky = page.query_selector(
            "div.sticky.inset-x-0.z-10.top-12"
        )
        if sticky:
            print("Sticky panel found")
            btns3 = sticky.query_selector_all("button")
            print(f"  Buttons in sticky: {len(btns3)}")
            for b in btns3[:5]:
                print(f"  btn text: {b.inner_text()[:80]}")
        else:
            print("Sticky panel NOT found")

        # Dump aside content
        aside = page.query_selector("aside")
        if aside:
            print("\nAside found, text snippet:")
            print(aside.inner_text()[:500])
        else:
            print("Aside NOT found")

        # Check body maps
        front = page.query_selector("#frontBodyMap")
        back  = page.query_selector("#backBodyMap")
        print(f"\nfrontBodyMap: {'found' if front else 'not found'}")
        print(f"backBodyMap:  {'found' if back  else 'not found'}")

        if front:
            # Get colored elements
            colored = front.query_selector_all("[class*='text-mw']")
            print(f"  colored elements in front: {len(colored)}")
            for el in colored[:5]:
                print(f"    id={el.get_attribute('id')} class={el.get_attribute('class')}")

        # Check steps container
        steps_sel = "div.sm\\:pb-0.mt-5.relative.lg\\:px-0.flex.flex-col"
        steps_el = page.query_selector(steps_sel)
        if steps_el:
            print(f"\nSteps container found, text:")
            print(steps_el.inner_text()[:400])
        else:
            print("\nSteps container NOT found")

        # Raw HTML snippet for exercise section
        print("\n--- Full page link/button analysis ---")
        all_btns = page.query_selector_all("button")
        print(f"Total buttons on page: {len(all_btns)}")
        for b in all_btns[:15]:
            t = b.inner_text().strip().replace("\n", " ")[:80]
            c = b.get_attribute("class") or ""
            print(f"  [{c[:40]}] {t}")

        browser.close()

if __name__ == "__main__":
    main()
