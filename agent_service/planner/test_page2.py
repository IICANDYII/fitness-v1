# -*- coding: utf-8 -*-
"""Deep analysis: aside structure, clicking buttons, steps content."""
import json
from playwright.sync_api import sync_playwright

TEST_URL = "https://musclewiki.com/zh-cn/workout/full-body-bodybuilding-workout-day-one"

def get_muscle_map(svg_el):
    """Extract muscles by color class from a body-map SVG."""
    result = {}
    if not svg_el:
        return result
    colored = svg_el.query_selector_all("[class*='text-mw']")
    for el in colored:
        cls = el.get_attribute("class") or ""
        el_id = el.get_attribute("id") or ""
        # Extract color class, e.g. "text-mw-red"
        for part in cls.split():
            if part.startswith("text-mw-"):
                if part not in result:
                    result[part] = []
                if el_id:
                    result[part].append(el_id)
    return result

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            locale="zh-CN",
        )
        page = ctx.new_page()
        page.goto(TEST_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # ---- Aside: basic data ----
        aside = page.query_selector("aside")
        aside_html = aside.inner_html() if aside else ""

        # Extract structured data from aside
        aside_data = {}
        if aside:
            # Find all label-value pairs (dt/dd or similar)
            items = aside.query_selector_all("div, li, span, p")
            aside_text = aside.inner_text()
            print("ASIDE TEXT:")
            print(aside_text)
            print()

        # ---- Muscle maps ----
        front = page.query_selector("#frontBodyMap")
        back  = page.query_selector("#backBodyMap")
        muscles = {
            "frontBodyMap": get_muscle_map(front),
            "backBodyMap":  get_muscle_map(back),
        }
        print("MUSCLES:", json.dumps(muscles, ensure_ascii=False, indent=2))

        # ---- Exercise buttons ----
        # Buttons with text-center class inside the sticky panel
        sticky = page.query_selector("div.sticky.inset-x-0.z-10")
        exercise_btns = sticky.query_selector_all("button") if sticky else []

        # Filter to exercise buttons (skip nav/icon buttons)
        ex_btns = [b for b in exercise_btns if b.inner_text().strip()]
        print(f"\nExercise buttons: {[b.inner_text().strip() for b in ex_btns]}")

        # ---- For each button: click + get steps ----
        steps_sel = "div.sm\\:pb-0.mt-5.relative.lg\\:px-0.flex.flex-col"

        for i, btn in enumerate(ex_btns):
            name = btn.inner_text().strip()
            btn.click()
            page.wait_for_timeout(1000)

            steps_el = page.query_selector(steps_sel)
            steps_text = steps_el.inner_text().strip() if steps_el else ""
            print(f"\n--- Button {i+1}: {name} ---")
            print(f"Steps: {steps_text[:300]}")

        browser.close()

if __name__ == "__main__":
    main()
