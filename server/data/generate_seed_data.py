#!/usr/bin/env python3
"""Generate deterministic JSON seed files for FinanceOpsEnv."""
from __future__ import annotations

import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
DEPTS = [
    "Engineering",
    "Sales",
    "Marketing",
    "Finance",
    "HR",
    "Operations",
    "Legal",
    "IT",
]
ROLES = ["IC", "Lead", "Manager", "Director"]


def main() -> None:
    rng = random.Random(42)

    employees = []
    for i in range(1, 151):
        eid = f"emp_{i:04d}"
        dept = DEPTS[(i - 1) % len(DEPTS)]
        employees.append(
            {
                "id": eid,
                "name": f"Employee {i}",
                "department": dept,
                "role": rng.choice(ROLES),
                "salary_monthly": int(80_000 + rng.random() * 420_000),
                "bank_account_id": f"ba_{(i % 5) + 1:02d}",
                "status": "active",
            }
        )

    vendors = []
    categories = ["software", "marketing", "logistics", "facilities", "consulting", "travel"]
    for i in range(1, 81):
        vid = f"v_{i:03d}"
        blacklisted = i in (17, 42, 63)
        vendors.append(
            {
                "id": vid,
                "name": f"Vendor {i} Pvt Ltd",
                "category": categories[i % len(categories)],
                "payment_terms_days": [15, 30, 45][i % 3],
                "blacklisted": blacklisted,
                "tax_id": f"GST{i:05d}IN",
            }
        )
    # Ensure v_102 exists for blueprint tasks
    if not any(v["id"] == "v_102" for v in vendors):
        vendors.append(
            {
                "id": "v_102",
                "name": "Marketing Vendor Alpha",
                "category": "marketing",
                "payment_terms_days": 30,
                "blacklisted": False,
                "tax_id": "GST10200IN",
            }
        )

    customers = []
    for i in range(1, 81):
        customers.append(
            {
                "id": f"c_{i:03d}",
                "name": f"Customer {i} Corp",
                "credit_limit": int(500_000 + rng.random() * 5_000_000),
                "outstanding_balance": int(rng.random() * 200_000),
            }
        )

    accounts = [
        {"id": "acc_operating", "name": "Operating", "type": "operating", "balance": 5_000_000},
        # Large pool so aggregate payroll_run succeeds for ~150 employees
        {"id": "acc_payroll", "name": "Payroll", "type": "payroll", "balance": 120_000_000},
        {"id": "acc_reserve", "name": "Reserve", "type": "reserve", "balance": 1_000_000},
        {"id": "acc_fx", "name": "FX", "type": "fx", "balance": 500_000},
    ]

    policies = {
        "travel": {"max_amount": 50_000, "requires_approval_above": 25_000},
        "meals": {"max_amount": 2_000, "requires_approval_above": 1_000},
        "software": {"max_amount": 100_000, "requires_approval_above": 50_000},
        "marketing": {"max_amount": 500_000, "requires_approval_above": 100_000},
        "other": {"max_amount": 25_000, "requires_approval_above": 10_000},
    }

    tax_rates = {
        "travel": {"gst_pct": 0.05, "tds_pct": 0.02},
        "meals": {"gst_pct": 0.05, "tds_pct": 0.0},
        "software": {"gst_pct": 0.18, "tds_pct": 0.1},
        "marketing": {"gst_pct": 0.18, "tds_pct": 0.02},
        "other": {"gst_pct": 0.18, "tds_pct": 0.02},
    }

    budgets = {
        "Engineering": {"annual_budget": 12_000_000, "ytd_actual": 4_200_000},
        "Sales": {"annual_budget": 8_000_000, "ytd_actual": 3_100_000},
        "Marketing": {"annual_budget": 6_000_000, "ytd_actual": 2_400_000},
        "Finance": {"annual_budget": 2_000_000, "ytd_actual": 800_000},
        "HR": {"annual_budget": 3_000_000, "ytd_actual": 1_100_000},
        "Operations": {"annual_budget": 5_000_000, "ytd_actual": 2_000_000},
        "Legal": {"annual_budget": 1_500_000, "ytd_actual": 600_000},
        "IT": {"annual_budget": 4_000_000, "ytd_actual": 1_800_000},
    }

    for name, obj in [
        ("employees.json", employees),
        ("vendors.json", vendors),
        ("customers.json", customers),
        ("accounts.json", accounts),
        ("policies.json", policies),
        ("tax_rates.json", tax_rates),
        ("budgets.json", budgets),
    ]:
        path = DATA_DIR / name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
