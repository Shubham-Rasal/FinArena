"""Mutable company financial state and entity data for FinanceOpsEnv."""

from __future__ import annotations

import copy
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

_DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_json(name: str) -> Any:
    path = _DATA_DIR / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class WorldState:
    """Enterprise finance state: accounts, AR/AP, expenses, payroll, FP&A."""

    def __init__(self, seed: int = 0) -> None:
        self._employees: list[dict] = _load_json("employees.json")
        self._vendors: list[dict] = _load_json("vendors.json")
        self._customers: list[dict] = _load_json("customers.json")
        self._policies: dict = _load_json("policies.json")
        self._tax_rates: dict = _load_json("tax_rates.json")
        self._budgets_template: dict = copy.deepcopy(_load_json("budgets.json"))

        self._accounts_snapshot: list[dict] = copy.deepcopy(_load_json("accounts.json"))
        self._episode_seed: int = seed
        self._episode_rng = __import__("random").Random(seed)

        self._action_log: list[dict] = []
        self._counter_invoice = 1
        self._counter_bill = 1
        self._counter_expense = 1
        self._counter_payment = 1
        self._counter_tx = 1

        # Ephemeral (reset each episode)
        self.accounts: dict[str, dict] = {}
        self.invoices: list[dict] = []
        self.bills: list[dict] = []
        self.expenses: list[dict] = []
        self.payments: list[dict] = []
        self.payroll_runs: list[dict] = []
        self.transactions: list[dict] = []
        self.forecasts: dict[str, Any] = {}
        self.budgets: dict = {}
        self.policy_violations: list[str] = []
        self.payroll_missed: bool = False
        self._reconciliation_done: bool = False

        self._reset_ephemeral()

    def _reset_ephemeral(self) -> None:
        # Apply ±20% balance variance per episode so agents cannot memorise exact values
        accounts: dict[str, dict] = {}
        for a in self._accounts_snapshot:
            acc = copy.deepcopy(a)
            jitter = self._episode_rng.uniform(0.80, 1.20)
            acc["balance"] = round(acc["balance"] * jitter, 2)
            accounts[acc["id"]] = acc
        self.accounts = accounts
        self.invoices = []
        self.bills = []
        self.expenses = []
        self.payments = []
        self.payroll_runs = []
        self.transactions = []
        self.forecasts = {}
        self.budgets = copy.deepcopy(self._budgets_template)
        self.policy_violations = []
        self.payroll_missed = False
        self._reconciliation_done = False

    def reset(self, episode_seed: Optional[int] = None) -> None:
        """Reset transactional state for a new episode."""
        if episode_seed is not None:
            self._episode_rng = __import__("random").Random(episode_seed)
        self._action_log = []
        self._counter_invoice = 1
        self._counter_bill = 1
        self._counter_expense = 1
        self._counter_payment = 1
        self._counter_tx = 1
        self._reset_ephemeral()

    def log_action(self, tool_name: str, params: dict, result: Any) -> None:
        self._action_log.append(
            {
                "tool": tool_name,
                "params": params,
                "result": result if isinstance(result, dict) else {"value": result},
                "timestamp": datetime.now().isoformat(),
            }
        )

    @property
    def action_log(self) -> list[dict]:
        return list(self._action_log)

    @property
    def cash(self) -> float:
        return float(sum(a["balance"] for a in self.accounts.values()))

    @property
    def state(self) -> dict:
        """Expose read-only snapshot for debugging."""
        return {
            "employees": self._employees,
            "vendors": self._vendors,
            "customers": self._customers,
        }

    # ---- Lookups ----
    def get_employee(self, emp_id: str) -> Optional[dict]:
        for e in self._employees:
            if e["id"] == emp_id:
                return e
        return None

    def get_vendor(self, vid: str) -> Optional[dict]:
        for v in self._vendors:
            if v["id"] == vid:
                return v
        return None

    def get_customer(self, cid: str) -> Optional[dict]:
        for c in self._customers:
            if c["id"] == cid:
                return c
        return None

    def _append_tx(self, kind: str, amount: float, account_id: str, memo: str) -> None:
        tid = f"tx_{self._counter_tx:06d}"
        self._counter_tx += 1
        self.transactions.append(
            {"id": tid, "kind": kind, "amount": amount, "account_id": account_id, "memo": memo}
        )

    def _debit_account(self, account_id: str, amount: float, memo: str) -> bool:
        if account_id not in self.accounts:
            return False
        self.accounts[account_id]["balance"] -= amount
        self._append_tx("debit", amount, account_id, memo)
        return True

    def _credit_account(self, account_id: str, amount: float, memo: str) -> bool:
        if account_id not in self.accounts:
            return False
        self.accounts[account_id]["balance"] += amount
        self._append_tx("credit", amount, account_id, memo)
        return True

    # ---- Accounting ----
    def acc_create_invoice(
        self, customer_id: str, amount: float, due_date: str, line_items: Optional[list] = None
    ) -> dict:
        if not self.get_customer(customer_id):
            return {"success": False, "error": "unknown_customer"}
        iid = f"inv_{self._counter_invoice:05d}"
        self._counter_invoice += 1
        inv = {
            "id": iid,
            "customer_id": customer_id,
            "amount": amount,
            "due_date": due_date,
            "status": "open",
            "line_items": line_items or [],
        }
        self.invoices.append(inv)
        return {"success": True, "invoice_id": iid, "invoice": inv}

    def acc_record_payment(self, invoice_id: str, amount: float) -> dict:
        inv = next((i for i in self.invoices if i["id"] == invoice_id), None)
        if not inv:
            return {"success": False, "error": "invoice_not_found"}
        self._credit_account("acc_operating", amount, f"AR payment {invoice_id}")
        inv["paid"] = inv.get("paid", 0) + amount
        if inv.get("paid", 0) >= inv["amount"] * 0.99:
            inv["status"] = "paid"
        else:
            inv["status"] = "partial"
        return {"success": True, "invoice_id": invoice_id, "invoice_status": inv["status"]}

    def acc_create_bill(self, vendor_id: str, amount: float, due_date: str, description: str) -> dict:
        if not self.get_vendor(vendor_id):
            return {"success": False, "error": "unknown_vendor"}
        bid = f"bill_{self._counter_bill:05d}"
        self._counter_bill += 1
        bill = {
            "id": bid,
            "vendor_id": vendor_id,
            "amount": amount,
            "due_date": due_date,
            "description": description,
            "status": "open",
        }
        self.bills.append(bill)
        return {"success": True, "bill_id": bid, "bill": bill}

    def acc_pay_bill(self, bill_id: str) -> dict:
        bill = next((b for b in self.bills if b["id"] == bill_id), None)
        if not bill:
            return {"success": False, "error": "bill_not_found"}
        if bill["status"] == "paid":
            return {"success": False, "error": "already_paid"}
        amt = bill["amount"]
        if self.accounts["acc_operating"]["balance"] < amt:
            self.policy_violations.append("insufficient_cash_for_bill")
            return {"success": False, "error": "insufficient_cash"}
        self._debit_account("acc_operating", amt, f"AP bill {bill_id}")
        bill["status"] = "paid"
        return {"success": True, "bill_id": bill_id}

    def acc_get_ledger(self, ledger_type: str) -> dict:
        if ledger_type == "ar":
            return {"success": True, "ledger": "ar", "invoices": self.invoices}
        if ledger_type == "ap":
            return {"success": True, "ledger": "ap", "bills": self.bills}
        return {
            "success": True,
            "ledger": "all",
            "invoices": self.invoices,
            "bills": self.bills,
        }

    def acc_generate_financials(self, report_type: str) -> dict:
        if report_type not in ("pnl", "balance_sheet", "cashflow"):
            return {"success": False, "error": "invalid_report_type"}
        total_assets = sum(a["balance"] for a in self.accounts.values())
        return {
            "success": True,
            "report_type": report_type,
            "cash_total": self.cash,
            "total_assets": total_assets,
            "accounts": copy.deepcopy(list(self.accounts.values())),
        }

    # ---- Expenses ----
    def exp_check_policy(self, category: str, amount: float) -> dict:
        pol = self._policies.get(category, self._policies.get("other", {}))
        max_amt = pol.get("max_amount", 0)
        compliant = amount <= max_amt
        return {
            "success": True,
            "compliant": compliant,
            "limit": max_amt,
            "requires_approval_above": pol.get("requires_approval_above", 0),
            "category": category,
        }

    def exp_submit(
        self, employee_id: str, amount: float, category: str, description: str
    ) -> dict:
        if not self.get_employee(employee_id):
            return {"success": False, "error": "unknown_employee"}
        eid = f"exp_{self._counter_expense:05d}"
        self._counter_expense += 1
        expense = {
            "id": eid,
            "employee_id": employee_id,
            "amount": amount,
            "category": category,
            "description": description,
            "status": "submitted",
        }
        self.expenses.append(expense)
        return {"success": True, "expense_id": eid, "expense": expense}

    def exp_approve(self, expense_id: str) -> dict:
        exp = next((e for e in self.expenses if e["id"] == expense_id), None)
        if not exp:
            return {"success": False, "error": "expense_not_found"}
        cat = exp.get("category", "other")
        chk = self.exp_check_policy(cat, exp["amount"])
        if not chk.get("compliant", True):
            self.policy_violations.append(f"approved_over_limit:{expense_id}")
        exp["status"] = "approved"
        return {"success": True, "expense_id": expense_id}

    def exp_reject(self, expense_id: str, reason: str = "") -> dict:
        exp = next((e for e in self.expenses if e["id"] == expense_id), None)
        if not exp:
            return {"success": False, "error": "expense_not_found"}
        exp["status"] = "rejected"
        exp["reject_reason"] = reason
        return {"success": True, "expense_id": expense_id}

    def exp_reimburse(self, expense_id: str) -> dict:
        exp = next((e for e in self.expenses if e["id"] == expense_id), None)
        if not exp:
            return {"success": False, "error": "expense_not_found"}
        if exp["status"] != "approved":
            return {"success": False, "error": "not_approved"}
        amt = exp["amount"]
        if self.accounts["acc_operating"]["balance"] < amt:
            return {"success": False, "error": "insufficient_cash"}
        self._debit_account("acc_operating", amt, f"reimburse {expense_id}")
        exp["status"] = "reimbursed"
        return {"success": True, "expense_id": expense_id}

    # ---- Payments (vendor) ----
    def pay_initiate(self, vendor_id: str, amount: float, reference: str = "") -> dict:
        v = self.get_vendor(vendor_id)
        if not v:
            return {"success": False, "error": "unknown_vendor"}
        if v.get("blacklisted"):
            return {"success": False, "error": "vendor_blacklisted"}
        pid = f"pay_{self._counter_payment:05d}"
        self._counter_payment += 1
        p = {
            "id": pid,
            "vendor_id": vendor_id,
            "amount": amount,
            "reference": reference,
            "status": "pending",
        }
        self.payments.append(p)
        return {"success": True, "payment_id": pid, "payment": p}

    def pay_schedule(self, payment_id: str, schedule_date: str) -> dict:
        p = next((x for x in self.payments if x["id"] == payment_id), None)
        if not p:
            return {"success": False, "error": "payment_not_found"}
        p["scheduled_date"] = schedule_date
        p["status"] = "scheduled"
        # Execute settlement: deduct operating cash
        amt = p["amount"]
        if self.accounts["acc_operating"]["balance"] < amt:
            self.policy_violations.append("insufficient_cash_for_payment")
            p["status"] = "failed_insufficient_cash"
            return {"success": False, "error": "insufficient_cash", "payment_id": payment_id}
        self._debit_account("acc_operating", amt, f"payment {payment_id}")
        p["status"] = "completed"
        return {"success": True, "payment_id": payment_id, "scheduled_date": schedule_date}

    def pay_cancel(self, payment_id: str) -> dict:
        p = next((x for x in self.payments if x["id"] == payment_id), None)
        if not p:
            return {"success": False, "error": "payment_not_found"}
        if p.get("status") == "completed":
            return {"success": False, "error": "already_settled"}
        p["status"] = "cancelled"
        return {"success": True, "payment_id": payment_id}

    def pay_status(self, payment_id: str) -> dict:
        p = next((x for x in self.payments if x["id"] == payment_id), None)
        if not p:
            return {"success": False, "error": "payment_not_found"}
        return {"success": True, "payment": p}

    # ---- Payroll ----
    def payroll_calculate(self, employee_id: str) -> dict:
        emp = self.get_employee(employee_id)
        if not emp:
            return {"success": False, "error": "unknown_employee"}
        gross = float(emp["salary_monthly"])
        deductions = gross * 0.05
        net = gross - deductions
        return {
            "success": True,
            "employee_id": employee_id,
            "gross": gross,
            "deductions": deductions,
            "net": net,
        }

    def payroll_run(self, period: str) -> dict:
        total_net = 0.0
        breakdown = []
        for emp in self._employees:
            if emp.get("status") != "active":
                continue
            pc = self.payroll_calculate(emp["id"])
            if pc.get("success"):
                total_net += float(pc["net"])
                breakdown.append({"employee_id": emp["id"], "net": pc["net"]})
        payroll_need = total_net
        if self.accounts["acc_payroll"]["balance"] < payroll_need:
            self.payroll_missed = True
            return {
                "success": False,
                "error": "insufficient_payroll_account",
                "required": payroll_need,
                "available": self.accounts["acc_payroll"]["balance"],
            }
        run = {
            "period": period,
            "total_net": total_net,
            "employee_count": len(breakdown),
            "breakdown": breakdown[:20],
            "truncated": len(breakdown) > 20,
        }
        self.payroll_runs.append(run)
        return {"success": True, "payroll_run": run}

    def payroll_disburse(self, employee_id: str) -> dict:
        emp = self.get_employee(employee_id)
        if not emp:
            return {"success": False, "error": "unknown_employee"}
        pc = self.payroll_calculate(employee_id)
        net = float(pc["net"])
        if self.accounts["acc_payroll"]["balance"] < net:
            self.payroll_missed = True
            return {"success": False, "error": "insufficient_payroll_funds"}
        self._debit_account("acc_payroll", net, f"payroll {employee_id}")
        return {"success": True, "employee_id": employee_id, "net_paid": net}

    # ---- Banking ----
    def bank_get_balance(self, account_id: str) -> dict:
        acc = self.accounts.get(account_id)
        if not acc:
            return {"success": False, "error": "unknown_account"}
        return {"success": True, "account_id": account_id, "balance": acc["balance"]}

    def bank_get_transactions(self, account_id: Optional[str] = None, limit: int = 50) -> dict:
        txs = self.transactions
        if account_id:
            txs = [t for t in txs if t["account_id"] == account_id]
        return {"success": True, "transactions": txs[-limit:]}

    def bank_transfer(self, from_account_id: str, to_account_id: str, amount: float) -> dict:
        if from_account_id not in self.accounts or to_account_id not in self.accounts:
            return {"success": False, "error": "unknown_account"}
        if self.accounts[from_account_id]["balance"] < amount:
            return {"success": False, "error": "insufficient_balance"}
        self._debit_account(from_account_id, amount, f"transfer to {to_account_id}")
        self._credit_account(to_account_id, amount, f"transfer from {from_account_id}")
        return {"success": True, "amount": amount}

    def bank_reconcile(self) -> dict:
        self._reconciliation_done = True
        return {
            "success": True,
            "reconciled": True,
            "cash_total": self.cash,
            "statement_date": date.today().isoformat(),
        }

    # ---- FP&A ----
    def fpna_create_budget(self, dept: str, amount: float, period: str) -> dict:
        self.budgets[dept] = {"annual_budget": amount, "period": period, "ytd_actual": 0}
        return {"success": True, "department": dept, "budget": self.budgets[dept]}

    def fpna_update_forecast(self, metric: str, value: float, period: str) -> dict:
        self.forecasts[metric] = {"value": value, "period": period}
        return {"success": True, "forecast": self.forecasts[metric]}

    def fpna_compare_actuals(self) -> dict:
        return {"success": True, "budgets": copy.deepcopy(self.budgets)}
