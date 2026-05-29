# -*- coding: utf-8 -*-
"""Quick test: run scraper on first 3 plans only."""
import sys
sys.path.insert(0, "D:/WorkPath/fitness/agent_service/planner")

# Monkey-patch to limit plans
import scrape_workouts as sw
from pathlib import Path

orig_load = sw.load_plans
sw.load_plans = lambda: orig_load()[:3]
sw.XLSX_PATH = Path("D:/WorkPath/fitness/agent_service/planner/workout_details_test.xlsx")

sw.main()
