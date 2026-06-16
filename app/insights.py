"""
Deterministic insight engine: turns an extracted EjarContract into the things a
tenant actually needs to know — deadlines, the auto-renewal trap, the holdover
penalty, total cost, the next payment. Pure functions, no model, no hallucination.
Each insight references the contract article it derives from.
"""
from datetime import date, timedelta
from typing import List, Optional

from app.models import EjarContract, DerivedInsight, Severity

SEV_ORDER = {Severity.warning: 0, Severity.important: 1, Severity.info: 2}


def _sar(n: float) -> str:
    return f"{n:,.0f}"


def derive_insights(c: EjarContract, today: Optional[date] = None) -> List[DerivedInsight]:
    today = today or date.today()
    out: List[DerivedInsight] = []
    kt = c.key_terms
    fin = c.financials

    # 1) Auto-renewal trap — the action deadline the contract never spells out.
    if kt and kt.auto_renews and kt.tenancy_end and kt.renewal_notice_days:
        act = kt.tenancy_end - timedelta(days=kt.renewal_notice_days)
        out.append(DerivedInsight(
            code="RENEWAL_NOTICE", severity=Severity.warning,
            title="This contract renews itself automatically",
            detail=(f"To stop it renewing, you must give notice by {act.isoformat()} — "
                    f"{kt.renewal_notice_days} days before it ends on {kt.tenancy_end.isoformat()}. "
                    f"Miss that date and you're locked into another term."),
            action_deadline=act, source_clause="Article 3"))

    # 2) Holdover penalty — buried late in the contract.
    if kt and kt.holdover_daily_penalty_sar:
        out.append(DerivedInsight(
            code="EXIT_PENALTY", severity=Severity.warning,
            title="Daily penalty if you don't move out on time",
            detail=(f"If you stay past the end date without agreement, you'll be charged "
                    f"SAR {_sar(kt.holdover_daily_penalty_sar)} for every day."),
            source_clause="Article 12"))

    # 3) Late-payment termination risk.
    if kt and kt.late_payment_grace_days:
        out.append(DerivedInsight(
            code="LATE_PAYMENT", severity=Severity.important,
            title="Pay on time or risk losing the lease",
            detail=(f"If a rent payment is more than {kt.late_payment_grace_days} days late, "
                    f"the landlord may terminate the contract."),
            source_clause="Article 10"))

    # 4) Total cost for the contract.
    if fin and fin.total_contract_value_sar:
        tail = f", paid in {fin.number_of_payments} installments." if fin.number_of_payments else "."
        out.append(DerivedInsight(
            code="TOTAL_COST", severity=Severity.info,
            title="Total cost for the contract",
            detail=f"Your total rent for the period is SAR {_sar(fin.total_contract_value_sar)}{tail}",
            source_clause="Article 4"))

    # 5) Next payment due (relative to today).
    up = [p for p in c.payment_schedule if p.payment_deadline_gregorian and p.payment_deadline_gregorian >= today]
    up.sort(key=lambda p: p.payment_deadline_gregorian)
    if up:
        nxt = up[0]
        days = (nxt.payment_deadline_gregorian - today).days
        amt = f"SAR {_sar(nxt.amount_sar)}" if nxt.amount_sar else "Your next payment"
        out.append(DerivedInsight(
            code="NEXT_PAYMENT", severity=Severity.important if days <= 14 else Severity.info,
            title="Next payment due",
            detail=f"{amt} must be paid by {nxt.payment_deadline_gregorian.isoformat()} — in {days} days.",
            action_deadline=nxt.payment_deadline_gregorian, source_clause="Article 12"))

    out.sort(key=lambda i: SEV_ORDER[i.severity])
    return out
