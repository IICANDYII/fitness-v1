# -*- coding: utf-8 -*-
"""
Retry the 6 workout plans that had 'No exercise buttons found' during the main run.
Merges the results into the existing workout_details.xlsx.
"""
import json
import openpyxl
from pathlib import Path
from playwright.sync_api import sync_playwright
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE_DIR  = Path("D:/WorkPath/fitness/agent_service/planner")
XLSX_PATH = BASE_DIR / "workout_details.xlsx"

# Plans that reported "No exercise buttons found" in the main run
FAILED = [
    ("新手全身健美 - 第1天",
     "https://musclewiki.com/zh-cn/workout/full-body-bodybuilding-workout-day-one"),
    ("初学科学胸肌训练 - 2",
     "https://musclewiki.com/zh-cn/workout/Beginner-Science-Based-Chest-Workout-2"),
    ("进阶科学胸肌训练 - 1",
     "https://musclewiki.com/zh-cn/workout/Advanced-Science-Based-Chest-Workout-1"),
    ("进阶科学背部训练 - 2",
     "https://musclewiki.com/zh-cn/workout/Advanced-Science-Based-Chest-Workout-2"),
    ("进阶科学胸肌训练 - 3",
     "https://musclewiki.com/zh-cn/workout/Advanced-Science-Based-Chest-Workout-3"),
    ("高级腿部训练",
     "https://musclewiki.com/zh-cn/workout/legs-for-advanced-lifters"),
]

JS_GET_MUSCLES = """
() => {
    function extractMap(id) {
        const svg = document.getElementById(id);
        if (!svg) return {};
        const result = {};
        svg.querySelectorAll('[class*="text-mw"]').forEach(el => {
            const raw = el.className;
            const cls = (typeof raw === 'string') ? raw : (raw.baseVal || '');
            const elId = el.id || '';
            cls.split(' ').forEach(c => {
                if (c.startsWith('text-mw-')) {
                    if (!result[c]) result[c] = [];
                    if (elId && !result[c].includes(elId)) result[c].push(elId);
                }
            });
        });
        return result;
    }
    return { frontBodyMap: extractMap('frontBodyMap'), backBodyMap: extractMap('backBodyMap') };
}
"""

JS_GET_ASIDE = """
() => {
    const aside = document.querySelector('aside > div');
    if (!aside) return {};
    const pairs = {};
    aside.querySelectorAll('div').forEach(div => {
        const ch = Array.from(div.children);
        if (ch.length === 2) {
            const k = ch[0].innerText?.trim();
            const v = ch[1].innerText?.trim();
            if (k && v && k.length < 30 && !k.includes('\\n') && !v.includes('\\n')
                && k !== 'Gender Selector') {
                pairs[k] = v;
            }
        }
    });
    return pairs;
}
"""

STEPS_SEL = "div.sm\\:pb-0.mt-5.relative.lg\\:px-0.flex.flex-col"

THIN   = Side(style="thin", color="CBD5E1")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
ALT_FILL = PatternFill("solid", fgColor="EFF6FF")

def get_exercise_buttons(page):
    sticky = page.query_selector("div.sticky.inset-x-0.z-10")
    if not sticky:
        return []
    return [b for b in sticky.query_selector_all("button") if b.inner_text().strip()]

def scrape_one(page, url, plan_name):
    rows = []
    print(f"  Retrying: {url}")

    # Try both original URL and lowercase URL
    urls_to_try = [url, url.lower()]
    loaded = False

    for try_url in urls_to_try:
        try:
            page.goto(try_url, wait_until="domcontentloaded", timeout=40000)
            try:
                page.wait_for_selector("div.sticky.inset-x-0.z-10 button", timeout=15000)
                page.wait_for_timeout(2000)
                loaded = True
                print(f"    Loaded: {try_url}")
                break
            except Exception:
                page.wait_for_timeout(4000)
                btns = get_exercise_buttons(page)
                if btns:
                    loaded = True
                    print(f"    Loaded (fallback): {try_url}")
                    break
        except Exception as e:
            print(f"    Failed: {try_url} — {e}")

    if not loaded:
        print(f"  [!!] Could not load any URL for: {plan_name}")
        return rows

    btns = get_exercise_buttons(page)
    if not btns:
        print(f"  [!] Still no buttons for: {plan_name}")
        return rows

    print(f"  Found {len(btns)} exercises")
    if len(btns) > 1:
        btns[-1].click()
        page.wait_for_timeout(900)

    for btn in btns:
        ex_name = btn.inner_text().strip()
        try:
            btn.click()
            page.wait_for_timeout(1500)
            steps_el = page.query_selector(STEPS_SEL)
            steps = steps_el.inner_text().strip() if steps_el else ""
            if not steps:
                page.wait_for_timeout(1500)
                steps_el = page.query_selector(STEPS_SEL)
                steps = steps_el.inner_text().strip() if steps_el else ""
            muscles  = page.evaluate(JS_GET_MUSCLES)
            aside_kv = page.evaluate(JS_GET_ASIDE)
            details  = {"basic_info": aside_kv, "muscles": muscles}
            rows.append({
                "plan": plan_name, "name": ex_name,
                "steps": steps,
                "details": json.dumps(details, ensure_ascii=False),
            })
            print(f"    ✓ {ex_name}")
        except Exception as e:
            print(f"    [!] {ex_name}: {e}")
    return rows

def append_to_xlsx(new_rows):
    wb = openpyxl.load_workbook(XLSX_PATH)
    ws = wb.active
    start_row = ws.max_row + 1
    for i, row in enumerate(new_rows):
        r = start_row + i
        vals = [row["plan"], row["name"], row["steps"], row["details"]]
        for c, val in enumerate(vals, 1):
            cell = ws.cell(r, c, val)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border    = BORDER
            if r % 2 == 0:
                cell.fill  = ALT_FILL
    wb.save(XLSX_PATH)
    print(f"  Appended {len(new_rows)} rows → {XLSX_PATH}")

def main():
    all_new = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        page = ctx.new_page()

        for plan_name, url in FAILED:
            rows = scrape_one(page, url, plan_name)
            all_new.extend(rows)
            print(f"  → {len(rows)} exercises\n")

        browser.close()

    if all_new:
        append_to_xlsx(all_new)
        print(f"\nTotal new rows added: {len(all_new)}")
    else:
        print("No new rows to add.")

if __name__ == "__main__":
    main()
