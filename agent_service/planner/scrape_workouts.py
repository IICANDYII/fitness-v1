# -*- coding: utf-8 -*-
"""
Scrape all workout plan details from musclewiki.com
For each plan: exercise name, steps, and structured details (aside + muscles)
Output: workout_details.xlsx
"""
import csv
import json
import sys
import time
import traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE_DIR   = Path("D:/WorkPath/fitness/agent_service/planner")
CSV_PATH   = BASE_DIR / "planner.csv"
XLSX_PATH  = BASE_DIR / "workout_details.xlsx"
LOG_PATH   = BASE_DIR / "scrape_errors.log"

STEPS_SEL  = "div.sm\\:pb-0.mt-5.relative.lg\\:px-0.flex.flex-col"

# ──────────────────────────────────────────────
# JS helpers (run inside the browser)
# ──────────────────────────────────────────────
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
    return {
        frontBodyMap: extractMap('frontBodyMap'),
        backBodyMap:  extractMap('backBodyMap')
    };
}
"""

JS_GET_ASIDE = """
() => {
    const aside = document.querySelector('aside > div');
    if (!aside) return {};
    const pairs = {};

    // Walk direct children that contain label/value pairs
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

# ──────────────────────────────────────────────
# Scraping helpers
# ──────────────────────────────────────────────
def get_exercise_buttons(page):
    """Return exercise buttons (skip icon-only buttons)."""
    sticky = page.query_selector("div.sticky.inset-x-0.z-10")
    if not sticky:
        return []
    return [b for b in sticky.query_selector_all("button") if b.inner_text().strip()]

def get_steps(page):
    el = page.query_selector(STEPS_SEL)
    return el.inner_text().strip() if el else ""

def scrape_workout(page, url, plan_name):
    """
    Open a workout URL and return a list of exercise dicts.
    Each dict: {plan, name, steps, details_json}
    """
    exercises = []
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=40000)
        # Wait for React to mount exercise buttons
        try:
            page.wait_for_selector("div.sticky.inset-x-0.z-10 button", timeout=15000)
            page.wait_for_timeout(1500)   # Extra wait for step API call
        except Exception:
            page.wait_for_timeout(4000)

        btns = get_exercise_buttons(page)
        if not btns:
            # Some pages may have a different layout — log and skip
            print(f"  [!] No exercise buttons found: {url}")
            return exercises

        # Prime the state: click the LAST button first so that clicking
        # any button (including the already-selected first one) triggers
        # a proper React re-render / API call.
        if len(btns) > 1:
            btns[-1].click()
            page.wait_for_timeout(900)

        for idx, btn in enumerate(btns):
            ex_name = btn.inner_text().strip()
            try:
                btn.click()
                page.wait_for_timeout(1500)

                # Extra wait if steps container is empty
                steps = get_steps(page)
                if not steps:
                    page.wait_for_timeout(1500)
                steps    = get_steps(page)
                muscles  = page.evaluate(JS_GET_MUSCLES)
                aside_kv = page.evaluate(JS_GET_ASIDE)

                details = {
                    "basic_info": aside_kv,
                    "muscles":    muscles,
                }

                exercises.append({
                    "plan":    plan_name,
                    "name":    ex_name,
                    "steps":   steps,
                    "details": json.dumps(details, ensure_ascii=False),
                })
            except Exception as e:
                print(f"  [!] Error on exercise '{ex_name}': {e}")
                exercises.append({
                    "plan":    plan_name,
                    "name":    ex_name,
                    "steps":   f"ERROR: {e}",
                    "details": "{}",
                })

    except Exception as e:
        print(f"  [!!] Failed to load page {url}: {e}")
        exercises.append({
            "plan":    plan_name,
            "name":    "PAGE_LOAD_ERROR",
            "steps":   str(e),
            "details": "{}",
        })

    return exercises

# ──────────────────────────────────────────────
# Excel writer
# ──────────────────────────────────────────────
HDR_FILL  = PatternFill("solid", fgColor="2563EB")
HDR_FONT  = Font(bold=True, color="FFFFFF", size=11)
ALT_FILL  = PatternFill("solid", fgColor="EFF6FF")
THIN      = Side(style="thin", color="CBD5E1")
BORDER    = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEADERS   = ["计划名称", "动作名称", "动作步骤", "动作详情"]
COL_WIDTHS = [40, 35, 80, 120]

def write_xlsx(all_rows, path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "训练计划动作详情"

    # Header row
    for col, (hdr, w) in enumerate(zip(HEADERS, COL_WIDTHS), 1):
        cell = ws.cell(1, col, hdr)
        cell.font   = HDR_FONT
        cell.fill   = HDR_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(col)].width = w

    ws.row_dimensions[1].height = 22

    # Data rows
    for r_idx, row in enumerate(all_rows, 2):
        fill = ALT_FILL if r_idx % 2 == 0 else PatternFill()
        values = [row["plan"], row["name"], row["steps"], row["details"]]
        for c_idx, val in enumerate(values, 1):
            cell = ws.cell(r_idx, c_idx, val)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border    = BORDER
            if r_idx % 2 == 0:
                cell.fill  = ALT_FILL

    # Freeze header row
    ws.freeze_panes = "A2"

    wb.save(path)
    print(f"\nSaved {len(all_rows)} rows → {path}")

# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def load_plans():
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return [(r["训练计划"], r["url"]) for r in reader]

def main():
    plans = load_plans()
    total = len(plans)
    print(f"Loaded {total} workout plans.\n")

    all_rows = []
    errors   = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
        )
        page = ctx.new_page()

        for i, (plan_name, url) in enumerate(plans, 1):
            # Strip the "View ... workout details" wrapper
            display_name = plan_name.replace("View ", "").replace(" workout details", "").strip()
            pct = i / total * 100
            print(f"[{i:3d}/{total}] ({pct:5.1f}%)  {display_name}")

            rows = scrape_workout(page, url, display_name)
            all_rows.extend(rows)

            ex_count = len(rows)
            ok = sum(1 for r in rows if "ERROR" not in r["steps"] and "PAGE_LOAD" not in r["name"])
            print(f"         → {ok}/{ex_count} exercises scraped")

            if ok < ex_count:
                errors.append(f"[{i}] {url}  ({ex_count - ok} errors)")

            # Save incremental checkpoint every 20 plans
            if i % 20 == 0:
                ckpt = BASE_DIR / f"workout_details_ckpt_{i}.xlsx"
                write_xlsx(all_rows, ckpt)

        browser.close()

    # Final save
    write_xlsx(all_rows, XLSX_PATH)

    if errors:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(errors))
        print(f"\n{len(errors)} plans had errors — see {LOG_PATH}")
    else:
        print("\nAll plans scraped successfully!")

    print(f"\nTotal exercises: {len(all_rows)}")

if __name__ == "__main__":
    main()
