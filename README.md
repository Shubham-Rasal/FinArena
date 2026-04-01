---
title: FinArena
emoji: 💰
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# FinArena — FinanceOps OpenEnv

An enterprise finance operations environment for training and evaluating AI agents on real-world financial workflows.

## Overview

FinanceOps simulates the day-to-day work of a finance operations team at a mid-size company. Agents must navigate **25 tools** across accounting, payroll, payments, and FP&A to complete **70 benchmark tasks** ranging from simple balance lookups to complex multi-step workflows.

## Task Categories

| Category | Count | Difficulty |
|---|---|---|
| Simple Lookup | 10 | Easy |
| Expense Workflow | 14 | Medium |
| Accounts Payable | 10 | Medium |
| Accounts Receivable | 10 | Medium |
| Payroll | 10 | Hard |
| Financial Close | 10 | Hard |
| Edge Cases | 6 | Hard |

## Tools Available

**Banking:** `bank_get_balance`, `bank_get_transactions`, `bank_transfer`, `bank_reconcile`

**Accounting:** `acc_create_invoice`, `acc_record_payment`, `acc_create_bill`, `acc_pay_bill`, `acc_get_ledger`, `acc_generate_financials`

**Expenses:** `exp_submit`, `exp_approve`, `exp_reject`, `exp_reimburse`, `exp_check_policy`

**Payments:** `pay_initiate`, `pay_schedule`, `pay_cancel`, `pay_status`

**Payroll:** `payroll_calculate`, `payroll_run`, `payroll_disburse`

**FP&A:** `fpna_create_budget`, `fpna_update_forecast`, `fpna_compare_actuals`

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/reset` | POST | Start a new episode |
| `/step` | POST | Take an action |
| `/state` | GET | Get current environment state |
| `/health` | GET | Health check |

## Reward Function

- **Partial credit** at every step: incremental reward for each newly satisfied rubric criterion
- **Terminal reward** (0.0–1.0): weighted score including financial penalties
  - `-0.3` for negative cash balance
  - `-0.4` for missed payroll
  - `-0.05` per policy violation (up to 4)
  - `-0.5` for undetected fraud
  - `+0.1` efficiency bonus for completing in minimal steps

## OpenEnv Interface

```python
from openenv.core import EnvClient
from finance_ops_env.models import FinanceAction, FinanceObservation

env = FinanceOpsEnv(base_url="http://localhost:7860").sync()
with env:
    result = env.reset()
    result = env.step(FinanceAction(
        tool_name="bank_get_balance",
        arguments={"account_id": "acc_operating"}
    ))
```
