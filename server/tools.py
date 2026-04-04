"""Tool definitions and registry for FinanceOpsEnv (25 tools)."""

from __future__ import annotations

from typing import Any

try:
    from .world import WorldState
except ImportError:
    from world import WorldState


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "acc_create_invoice",
        "description": "Create an AR invoice for a customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "amount": {"type": "number"},
                "due_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "line_items": {"type": "array"},
            },
            "required": ["customer_id", "amount", "due_date"],
        },
    },
    {
        "name": "acc_record_payment",
        "description": "Record a customer payment against an invoice.",
        "parameters": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["invoice_id", "amount"],
        },
    },
    {
        "name": "acc_create_bill",
        "description": "Create an AP bill from a vendor.",
        "parameters": {
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string"},
                "amount": {"type": "number"},
                "due_date": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["vendor_id", "amount", "due_date", "description"],
        },
    },
    {
        "name": "acc_pay_bill",
        "description": "Pay an open bill from operating cash.",
        "parameters": {
            "type": "object",
            "properties": {"bill_id": {"type": "string"}},
            "required": ["bill_id"],
        },
    },
    {
        "name": "acc_get_ledger",
        "description": "Fetch AR, AP, or combined ledger.",
        "parameters": {
            "type": "object",
            "properties": {
                "ledger_type": {
                    "type": "string",
                    "enum": ["ar", "ap", "all"],
                    "description": "Which ledger to return",
                }
            },
            "required": ["ledger_type"],
        },
    },
    {
        "name": "acc_generate_financials",
        "description": "Generate P&L, balance sheet, or cashflow summary.",
        "parameters": {
            "type": "object",
            "properties": {
                "report_type": {"type": "string", "enum": ["pnl", "balance_sheet", "cashflow"]}
            },
            "required": ["report_type"],
        },
    },
    {
        "name": "exp_submit",
        "description": "Submit an employee expense report. The parameter name is 'category' (not 'expense_category'). Valid categories: travel, marketing, software, consulting, facilities, logistics, other.",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string"},
                "amount": {"type": "number"},
                "category": {
                    "type": "string",
                    "enum": ["travel", "marketing", "software", "consulting", "facilities", "logistics", "other"],
                },
                "description": {"type": "string"},
            },
            "required": ["employee_id", "amount", "category", "description"],
        },
    },
    {
        "name": "exp_approve",
        "description": "Approve a submitted expense.",
        "parameters": {
            "type": "object",
            "properties": {"expense_id": {"type": "string"}},
            "required": ["expense_id"],
        },
    },
    {
        "name": "exp_reject",
        "description": "Reject an expense with a reason.",
        "parameters": {
            "type": "object",
            "properties": {
                "expense_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["expense_id"],
        },
    },
    {
        "name": "exp_reimburse",
        "description": "Reimburse an approved expense from operating cash.",
        "parameters": {
            "type": "object",
            "properties": {"expense_id": {"type": "string"}},
            "required": ["expense_id"],
        },
    },
    {
        "name": "exp_check_policy",
        "description": "Check an expense amount against policy limits for its category. Required params: 'category' and 'amount'. Valid categories: travel, marketing, software, consulting, facilities, logistics, other.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["travel", "marketing", "software", "consulting", "facilities", "logistics", "other"],
                },
                "amount": {"type": "number"},
            },
            "required": ["category", "amount"],
        },
    },
    {
        "name": "pay_initiate",
        "description": "Initiate a vendor payment.",
        "parameters": {
            "type": "object",
            "properties": {
                "vendor_id": {"type": "string"},
                "amount": {"type": "number"},
                "reference": {"type": "string"},
            },
            "required": ["vendor_id", "amount"],
        },
    },
    {
        "name": "pay_schedule",
        "description": "Schedule a pending payment and settle from operating cash.",
        "parameters": {
            "type": "object",
            "properties": {
                "payment_id": {"type": "string"},
                "schedule_date": {"type": "string"},
            },
            "required": ["payment_id", "schedule_date"],
        },
    },
    {
        "name": "pay_cancel",
        "description": "Cancel a pending vendor payment.",
        "parameters": {
            "type": "object",
            "properties": {"payment_id": {"type": "string"}},
            "required": ["payment_id"],
        },
    },
    {
        "name": "pay_status",
        "description": "Get status of a payment.",
        "parameters": {
            "type": "object",
            "properties": {"payment_id": {"type": "string"}},
            "required": ["payment_id"],
        },
    },
    {
        "name": "payroll_run",
        "description": "Run aggregate payroll validation for a period (YYYY-MM).",
        "parameters": {
            "type": "object",
            "properties": {"period": {"type": "string"}},
            "required": ["period"],
        },
    },
    {
        "name": "payroll_calculate",
        "description": "Calculate net pay for one employee.",
        "parameters": {
            "type": "object",
            "properties": {"employee_id": {"type": "string"}},
            "required": ["employee_id"],
        },
    },
    {
        "name": "payroll_disburse",
        "description": "Disburse payroll for one employee from the payroll account.",
        "parameters": {
            "type": "object",
            "properties": {"employee_id": {"type": "string"}},
            "required": ["employee_id"],
        },
    },
    {
        "name": "bank_get_balance",
        "description": "Get balance for a bank account. Valid account_id values: acc_operating, acc_payroll, acc_reserve, acc_fx.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "enum": ["acc_operating", "acc_payroll", "acc_reserve", "acc_fx"],
                }
            },
            "required": ["account_id"],
        },
    },
    {
        "name": "bank_get_transactions",
        "description": "List recent transactions, optionally filtered by account. Valid account_id values: acc_operating, acc_payroll, acc_reserve, acc_fx.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_id": {
                    "type": "string",
                    "enum": ["acc_operating", "acc_payroll", "acc_reserve", "acc_fx"],
                },
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "bank_transfer",
        "description": "Transfer cash between two accounts. Valid account IDs: acc_operating, acc_payroll, acc_reserve, acc_fx.",
        "parameters": {
            "type": "object",
            "properties": {
                "from_account_id": {
                    "type": "string",
                    "enum": ["acc_operating", "acc_payroll", "acc_reserve", "acc_fx"],
                },
                "to_account_id": {
                    "type": "string",
                    "enum": ["acc_operating", "acc_payroll", "acc_reserve", "acc_fx"],
                },
                "amount": {"type": "number"},
            },
            "required": ["from_account_id", "to_account_id", "amount"],
        },
    },
    {
        "name": "bank_reconcile",
        "description": "Run bank reconciliation / close checklist step.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "fpna_create_budget",
        "description": "Create or overwrite department budget for a period.",
        "parameters": {
            "type": "object",
            "properties": {
                "dept": {"type": "string"},
                "amount": {"type": "number"},
                "period": {"type": "string"},
            },
            "required": ["dept", "amount", "period"],
        },
    },
    {
        "name": "fpna_update_forecast",
        "description": "Update a named forecast metric.",
        "parameters": {
            "type": "object",
            "properties": {
                "metric": {"type": "string"},
                "value": {"type": "number"},
                "period": {"type": "string"},
            },
            "required": ["metric", "value", "period"],
        },
    },
    {
        "name": "fpna_compare_actuals",
        "description": "Compare budget vs YTD actuals by department.",
        "parameters": {"type": "object", "properties": {}},
    },
]


class ToolRegistry:
    """Dispatches tool calls to WorldState and logs actions."""

    def __init__(self, world: WorldState):
        self.world = world

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        w = self.world
        try:
            if tool_name == "acc_create_invoice":
                r = w.acc_create_invoice(
                    arguments["customer_id"],
                    float(arguments["amount"]),
                    str(arguments["due_date"]),
                    arguments.get("line_items"),
                )
            elif tool_name == "acc_record_payment":
                r = w.acc_record_payment(str(arguments["invoice_id"]), float(arguments["amount"]))
            elif tool_name == "acc_create_bill":
                r = w.acc_create_bill(
                    str(arguments["vendor_id"]),
                    float(arguments["amount"]),
                    str(arguments["due_date"]),
                    str(arguments.get("description", "")),
                )
            elif tool_name == "acc_pay_bill":
                r = w.acc_pay_bill(str(arguments["bill_id"]))
            elif tool_name == "acc_get_ledger":
                r = w.acc_get_ledger(str(arguments["ledger_type"]))
            elif tool_name == "acc_generate_financials":
                r = w.acc_generate_financials(str(arguments["report_type"]))
            elif tool_name == "exp_submit":
                r = w.exp_submit(
                    str(arguments["employee_id"]),
                    float(arguments["amount"]),
                    str(arguments["category"]),
                    str(arguments.get("description", "")),
                )
            elif tool_name == "exp_approve":
                r = w.exp_approve(str(arguments["expense_id"]))
            elif tool_name == "exp_reject":
                r = w.exp_reject(str(arguments["expense_id"]), str(arguments.get("reason", "")))
            elif tool_name == "exp_reimburse":
                r = w.exp_reimburse(str(arguments["expense_id"]))
            elif tool_name == "exp_check_policy":
                r = w.exp_check_policy(str(arguments["category"]), float(arguments["amount"]))
            elif tool_name == "pay_initiate":
                r = w.pay_initiate(
                    str(arguments["vendor_id"]),
                    float(arguments["amount"]),
                    str(arguments.get("reference", "")),
                )
            elif tool_name == "pay_schedule":
                r = w.pay_schedule(str(arguments["payment_id"]), str(arguments["schedule_date"]))
            elif tool_name == "pay_cancel":
                r = w.pay_cancel(str(arguments["payment_id"]))
            elif tool_name == "pay_status":
                r = w.pay_status(str(arguments["payment_id"]))
            elif tool_name == "payroll_run":
                r = w.payroll_run(str(arguments["period"]))
            elif tool_name == "payroll_calculate":
                r = w.payroll_calculate(str(arguments["employee_id"]))
            elif tool_name == "payroll_disburse":
                r = w.payroll_disburse(str(arguments["employee_id"]))
            elif tool_name == "bank_get_balance":
                r = w.bank_get_balance(str(arguments["account_id"]))
            elif tool_name == "bank_get_transactions":
                r = w.bank_get_transactions(arguments.get("account_id"), int(arguments.get("limit", 50)))
            elif tool_name == "bank_transfer":
                r = w.bank_transfer(
                    str(arguments["from_account_id"]),
                    str(arguments["to_account_id"]),
                    float(arguments["amount"]),
                )
            elif tool_name == "bank_reconcile":
                r = w.bank_reconcile()
            elif tool_name == "fpna_create_budget":
                r = w.fpna_create_budget(
                    str(arguments["dept"]), float(arguments["amount"]), str(arguments["period"])
                )
            elif tool_name == "fpna_update_forecast":
                r = w.fpna_update_forecast(
                    str(arguments["metric"]),
                    float(arguments["value"]),
                    str(arguments["period"]),
                )
            elif tool_name == "fpna_compare_actuals":
                r = w.fpna_compare_actuals()
            else:
                r = {"success": False, "error": f"unknown_tool:{tool_name}"}
        except Exception as e:
            r = {"success": False, "error": str(e)}

        w.log_action(tool_name, arguments, r)
        return r
