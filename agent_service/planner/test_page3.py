# -*- coding: utf-8 -*-
"""Analyze aside DOM structure and check if it updates on button click."""
import json
from playwright.sync_api import sync_playwright

TEST_URL = "https://musclewiki.com/zh-cn/workout/full-body-bodybuilding-workout-day-one"

def extract_aside_data(page):
    """Extract structured key-value data from aside panel."""
    return page.evaluate("""
    () => {
        const aside = document.querySelector('aside > div');
        if (!aside) return {};

        const result = {};

        // Find all label+value pairs - look for dt/dd or heading+content patterns
        // Collect all text nodes in a structured way
        const allEls = Array.from(aside.querySelectorAll('*'));
        const pairs = [];

        // Find specific data items - each has a small label and a larger value
        // Look for divs that contain a small label and larger text
        const rows = aside.querySelectorAll('div');
        rows.forEach(div => {
            const children = Array.from(div.children);
            if (children.length === 0) return;
            const texts = children.map(c => c.innerText?.trim()).filter(t => t);
            if (texts.length === 2) {
                // Possibly a label-value pair
                pairs.push([texts[0], texts[1]]);
            }
        });

        result['pairs'] = pairs.slice(0, 20);
        result['raw'] = aside.innerText?.trim().split('\\n').map(s => s.trim()).filter(s => s);
        return result;
    }
    """)

def get_muscle_map(page):
    return page.evaluate("""
    () => {
        function extractMap(id) {
            const svg = document.getElementById(id);
            if (!svg) return {};
            const result = {};
            svg.querySelectorAll('[class*="text-mw"]').forEach(el => {
                const cls = el.className?.baseVal || el.getAttribute('class') || '';
                const elId = el.id || '';
                cls.split(' ').forEach(c => {
                    if (c.startsWith('text-mw-')) {
                        if (!result[c]) result[c] = [];
                        if (elId) result[c].push(elId);
                    }
                });
            });
            return result;
        }
        return {
            frontBodyMap: extractMap('frontBodyMap'),
            backBodyMap: extractMap('backBodyMap')
        };
    }
    """)

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

        sticky = page.query_selector("div.sticky.inset-x-0.z-10")
        ex_btns = [b for b in (sticky.query_selector_all("button") if sticky else []) if b.inner_text().strip()]

        print(f"Exercises: {[b.inner_text().strip() for b in ex_btns]}\n")

        # For each exercise: click, wait, extract
        steps_sel = "div.sm\\:pb-0.mt-5.relative.lg\\:px-0.flex.flex-col"
        for i, btn in enumerate(ex_btns):
            name = btn.inner_text().strip()
            btn.click()
            page.wait_for_timeout(1500)

            # Steps
            steps_el = page.query_selector(steps_sel)
            steps = steps_el.inner_text().strip() if steps_el else ""

            # Aside data
            aside_data = extract_aside_data(page)
            muscles = get_muscle_map(page)

            print(f"=== Exercise {i+1}: {name} ===")
            print(f"Steps: {steps[:200]}")
            print(f"Aside pairs: {aside_data.get('pairs', [])[:8]}")
            print(f"Aside raw: {aside_data.get('raw', [])[:12]}")
            print(f"Muscles: {json.dumps(muscles, ensure_ascii=False)}")
            print()

        browser.close()

if __name__ == "__main__":
    main()
