"""Task definitions and generation for FinanceOpsEnv (70 tasks)."""

from __future__ import annotations

import random
from typing import Any, Optional

try:
    from .world import WorldState
except ImportError:
    from world import WorldState


class Task:
    """Single benchmark task."""

    def __init__(
        self,
        task_id: str,
        instruction: str,
        difficulty: str,
        category: str,
        expected_tools: list[str],
        rubric_criteria: list[dict],
        setup_fn: Any = None,
        context: Optional[dict] = None,
    ):
        self.task_id = task_id
        self.instruction = instruction
        self.difficulty = difficulty
        self.category = category
        self.expected_tools = expected_tools
        self.rubric_criteria = rubric_criteria
        self.setup_fn = setup_fn
        self.context = context or {}

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "instruction": self.instruction,
            "difficulty": self.difficulty,
            "category": self.category,
            "expected_tools": self.expected_tools,
            "rubric_criteria": list(self.rubric_criteria),
            "context": self.context,
        }


def _rc(name: str, desc: str, check: str) -> dict:
    return {"name": name, "description": desc, "check": check}


class TaskGenerator:
    """Builds 70 deterministic tasks."""

    def __init__(self, world: WorldState, seed: int = 42):
        self.world = world
        self.rng = random.Random(seed)

    def generate_all_tasks(self) -> list[Task]:
        tasks: list[Task] = []
        tid = 0

        def add(
            instruction: str,
            difficulty: str,
            category: str,
            tools: list[str],
            rubric: list[dict],
            ctx: Optional[dict] = None,
            setup_fn: Any = None,
        ) -> None:
            nonlocal tid
            tid += 1
            tasks.append(
                Task(
                    f"task_{tid:03d}",
                    instruction,
                    difficulty,
                    category,
                    tools,
                    rubric,
                    setup_fn=setup_fn,
                    context=ctx or {},
                )
            )

        # simple_lookup (10)
        simple_specs = [
            (
                "Report the current balance of the operating bank account.",
                ["bank_get_balance"],
                [
                    _rc("check_balance", "Called bank_get_balance", "tool_used:bank_get_balance"),
                    _rc("operating", "Used operating account", "param_value:bank_get_balance.account_id=acc_operating"),
                ],
            ),
            (
                "Show the payroll account balance.",
                ["bank_get_balance"],
                [
                    _rc("payroll_acct", "Checked payroll account", "tool_used:bank_get_balance"),
                    _rc("acc", "Correct account id", "param_value:bank_get_balance.account_id=acc_payroll"),
                ],
            ),
            (
                "List all open AR and AP items.",
                ["acc_get_ledger"],
                [
                    _rc("ledger", "Fetched ledger", "tool_used:acc_get_ledger"),
                    _rc("all", "Used combined ledger", "param_value:acc_get_ledger.ledger_type=all"),
                ],
            ),
            (
                "Pull only accounts receivable invoices.",
                ["acc_get_ledger"],
                [
                    _rc("ar", "Used AR ledger", "tool_used:acc_get_ledger"),
                    _rc("type", "ledger_type=ar", "param_value:acc_get_ledger.ledger_type=ar"),
                ],
            ),
            (
                "Pull only accounts payable bills.",
                ["acc_get_ledger"],
                [
                    _rc("ap", "Used AP ledger", "tool_used:acc_get_ledger"),
                    _rc("type", "ledger_type=ap", "param_value:acc_get_ledger.ledger_type=ap"),
                ],
            ),
            (
                "Compare departmental budgets to actuals.",
                ["fpna_compare_actuals"],
                [_rc("compare", "Ran compare actuals", "tool_used:fpna_compare_actuals")],
            ),
            (
                "Fetch recent bank transactions for the operating account (limit 20).",
                ["bank_get_transactions"],
                [
                    _rc("tx", "Listed transactions", "tool_used:bank_get_transactions"),
                    _rc("acct", "Filtered operating", "param_contains:bank_get_transactions.account_id=acc_operating"),
                ],
            ),
            (
                "Generate a P&L style financial summary.",
                ["acc_generate_financials"],
                [
                    _rc("fin", "Generated financials", "tool_used:acc_generate_financials"),
                    _rc("pnl", "pnl report", "param_value:acc_generate_financials.report_type=pnl"),
                ],
            ),
            (
                "Generate a balance sheet summary.",
                ["acc_generate_financials"],
                [
                    _rc("fin", "Generated financials", "tool_used:acc_generate_financials"),
                    _rc("bs", "balance_sheet", "param_value:acc_generate_financials.report_type=balance_sheet"),
                ],
            ),
            (
                "Check if a ₹60,000 marketing expense complies with policy before approval.",
                ["exp_check_policy"],
                [
                    _rc("policy", "Checked policy", "tool_used:exp_check_policy"),
                    _rc("cat", "marketing category", "param_contains:exp_check_policy.category=marketing"),
                ],
            ),
        ]
        for instr, tools, rub in simple_specs:
            add(instr, "simple", "simple_lookup", tools, rub, {"min_expected_steps": 2})

        # expense_workflow (14) -> running total 24
        for j in range(14):
            amt = 5000 + j * 3000
            eid = f"emp_{(j % 20) + 1:04d}"
            add(
                f"Employee {eid} submitted a ₹{amt} travel expense. "
                f"Verify policy, approve, then reimburse.",
                "medium",
                "expense_workflow",
                ["exp_check_policy", "exp_submit", "exp_approve", "exp_reimburse"],
                [
                    _rc("policy", "Policy checked", "tool_used:exp_check_policy"),
                    _rc("submit", "Expense submitted", "tool_used:exp_submit"),
                    _rc("approve", "Approved", "tool_used:exp_approve"),
                    _rc("pay", "Reimbursed", "tool_used:exp_reimburse"),
                    _rc("order", "approve after submit", "tool_order:exp_submit<exp_approve"),
                ],
                {"min_expected_steps": 5},
            )

        # accounts_payable (10) -> 34
        ap_amounts = [50_000, 75_000, 100_000, 125_000, 150_000, 175_000, 200_000, 225_000, 250_000, 275_000]
        for j in range(10):
            vid = "v_102" if j == 6 else f"v_{(j % 40) + 1:03d}"
            amt = ap_amounts[j]
            add(
                f"Process vendor payment of ₹{amt} to {vid}: check operating balance, "
                f"create bill, initiate payment, schedule for next week.",
                "medium",
                "accounts_payable",
                ["bank_get_balance", "acc_create_bill", "pay_initiate", "pay_schedule"],
                [
                    _rc("bal", "Checked balance", "tool_used:bank_get_balance"),
                    _rc("bill", "Created bill", "tool_used:acc_create_bill"),
                    _rc("order_bill_pay", "bill before pay_initiate", "tool_order:acc_create_bill<pay_initiate"),
                    _rc("pay", "Initiated payment", "tool_used:pay_initiate"),
                    _rc("sched", "Scheduled", "tool_used:pay_schedule"),
                    _rc("amt", "Correct payment amount", f"param_value:pay_initiate.amount={amt}"),
                ],
                {"min_expected_steps": 5},
            )

        # accounts_receivable (10) -> 44
        for j in range(10):
            cid = f"c_{(j % 30) + 1:03d}"
            inv_amt = 100_000 + j * 25_000
            add(
                f"Create an invoice for customer {cid} for ₹{inv_amt} due in 30 days, "
                f"then record a partial payment of ₹{inv_amt // 2}.",
                "medium",
                "accounts_receivable",
                ["acc_create_invoice", "acc_record_payment"],
                [
                    _rc("inv", "Invoice created", "tool_used:acc_create_invoice"),
                    _rc("pay", "Payment recorded", "tool_used:acc_record_payment"),
                    _rc("order", "invoice before payment", "tool_order:acc_create_invoice<acc_record_payment"),
                    _rc("cust", "Correct customer", f"param_value:acc_create_invoice.customer_id={cid}"),
                ],
                {"min_expected_steps": 3},
            )

        # payroll (10) -> 54
        for j in range(10):
            eid = f"emp_{j + 1:04d}"
            period = f"2025-{(j % 12) + 1:02d}"
            add(
                f"For payroll period {period}: calculate net pay for {eid}, run aggregate payroll check, "
                f"and disburse that employee.",
                "complex",
                "payroll",
                ["payroll_calculate", "payroll_run", "payroll_disburse"],
                [
                    _rc("calc", "Calculated pay", "tool_used:payroll_calculate"),
                    _rc("run", "Payroll run", "tool_used:payroll_run"),
                    _rc("disb", "Disbursed", "tool_used:payroll_disburse"),
                    _rc("emp", "Correct employee in calculate", f"param_value:payroll_calculate.employee_id={eid}"),
                ],
                {"min_expected_steps": 4},
            )

        # financial_close (10) -> 64
        for _ in range(10):
            add(
                "Perform month-end close steps: reconcile bank, generate cashflow report, compare budget actuals.",
                "complex",
                "financial_close",
                ["bank_reconcile", "acc_generate_financials", "fpna_compare_actuals"],
                [
                    _rc("rec", "Reconciled", "tool_used:bank_reconcile"),
                    _rc("cf", "Cashflow report", "tool_used:acc_generate_financials"),
                    _rc("cf_type", "cashflow type", "param_value:acc_generate_financials.report_type=cashflow"),
                    _rc("fpna", "Compared actuals", "tool_used:fpna_compare_actuals"),
                ],
                {"min_expected_steps": 4},
            )

        # edge_cases (6) -> 70
        add(
            "Expense ₹600,000 in marketing is above policy. Check policy first; do NOT approve without compliance review.",
            "edge_case",
            "edge_cases",
            ["exp_check_policy", "exp_submit"],
            [
                _rc("policy", "Must check policy", "tool_used:exp_check_policy"),
                _rc("no_appr", "Should not approve blindly", "tool_not_used:exp_approve"),
            ],
            {"min_expected_steps": 2},
        )
        add(
            "Vendor v_017 is blacklisted. Do NOT initiate payment to this vendor.",
            "edge_case",
            "edge_cases",
            [],
            [_rc("no_pay", "No payment to blacklisted", "tool_not_used:pay_initiate")],
            {"min_expected_steps": 1},
        )
        add(
            "Before creating a new invoice for c_005, review existing AR to avoid duplicates.",
            "edge_case",
            "edge_cases",
            ["acc_get_ledger", "acc_create_invoice"],
            [
                _rc("ledger", "Reviewed ledger first", "tool_order:acc_get_ledger<acc_create_invoice"),
                _rc("inv", "Created invoice", "tool_used:acc_create_invoice"),
                _rc("cust", "Customer c_005", "param_value:acc_create_invoice.customer_id=c_005"),
            ],
            {"min_expected_steps": 3},
        )
        def _setup_fraud_expense(world: WorldState) -> None:
            world.expenses.append(
                {
                    "id": "exp_00001",
                    "employee_id": "emp_0001",
                    "amount": 99_999,
                    "category": "travel",
                    "description": "suspected duplicate",
                    "status": "submitted",
                }
            )

        add(
            "Suspected fraudulent duplicate expense — reject expense exp_00001.",
            "edge_case",
            "edge_cases",
            ["exp_reject"],
            [_rc("reject", "Rejected fraud", "tool_used:exp_reject")],
            {"has_fraud": True, "fraud_expense_id": "exp_00001", "min_expected_steps": 1},
            setup_fn=_setup_fraud_expense,
        )
        add(
            "Transfer ₹500,000 from reserve to operating to cover upcoming payables, then confirm operating balance.",
            "edge_case",
            "edge_cases",
            ["bank_transfer", "bank_get_balance"],
            [
                _rc("xfer", "Transferred", "tool_used:bank_transfer"),
                _rc("bal", "Confirmed balance", "tool_used:bank_get_balance"),
                _rc("order", "transfer before balance check", "tool_order:bank_transfer<bank_get_balance"),
            ],
            {"min_expected_steps": 3},
        )
        add(
            "Process ₹200,000 vendor payment to v_102 while ensuring cash headroom stays above ₹1,000,000.",
            "edge_case",
            "edge_cases",
            ["bank_get_balance", "acc_create_bill", "pay_initiate", "pay_schedule"],
            [
                _rc("bal", "Checked balance", "tool_used:bank_get_balance"),
                _rc("cash_ok", "Sufficient cash headroom", "cash_sufficient:1000000"),
                _rc("bill", "Bill created", "tool_used:acc_create_bill"),
                _rc("pay", "Initiated payment", "tool_used:pay_initiate"),
                _rc("sched", "Scheduled payment", "tool_used:pay_schedule"),
                _rc("amt", "Amount 200000", "param_value:pay_initiate.amount=200000"),
            ],
            {"min_expected_steps": 5},
        )

        return tasks
