"""
Ejar tenancy-contract schema.

Designed against a real (redacted) Ejar contract. Two layers:
  1. Extraction layer  -> structured facts pulled from the document.
  2. Insight layer      -> the judgment a tenant actually cares about
                           (deadlines, total cost, the renewal trap, exit penalty).

PII fields are explicitly marked. The redaction step strips them before the
document is sent to the model, and the output layer must never echo them.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Parties
# --------------------------------------------------------------------------
class PartyRole(str, Enum):
    lessor = "lessor"      # المؤجِّر
    tenant = "tenant"      # المستأجر
    broker = "broker"      # الوسيط العقاري


class Party(BaseModel):
    role: PartyRole
    name: Optional[str] = Field(None, description="PII — do not output")
    nationality: Optional[str] = None            # e.g. السعودية / باكستان
    id_type: Optional[str] = None                # هوية وطنية | هوية مقيم
    id_number: Optional[str] = Field(None, description="PII — do not output")
    email: Optional[str] = Field(None, description="PII — do not output")
    mobile: Optional[str] = Field(None, description="PII — do not output")


# --------------------------------------------------------------------------
# Property
# --------------------------------------------------------------------------
class PropertyInfo(BaseModel):
    property_type: Optional[str] = None          # عمارة (building)
    property_usage: Optional[str] = None         # سكن عائلات (family housing)
    city: Optional[str] = None                   # الرياض
    national_address: Optional[str] = Field(None, description="PII-sensitive — mask exact address")
    number_of_units: Optional[int] = None        # 36
    number_of_floors: Optional[int] = None       # 3
    # the specific rented unit
    unit_number: Optional[str] = None            # 02
    unit_type: Optional[str] = None              # شقة (apartment)
    unit_area_sqm: Optional[float] = None        # 150.0
    floor_number: Optional[str] = None           # 0
    furnished: Optional[bool] = None


# --------------------------------------------------------------------------
# Money
# --------------------------------------------------------------------------
class PaymentInstallment(BaseModel):
    sequence: int                                # 1, 2, ...
    due_date_gregorian: Optional[date] = None    # 2025-12-19
    due_date_hijri: Optional[str] = None         # 1447-06-28
    payment_deadline_gregorian: Optional[date] = None   # 2025-12-29
    payment_deadline_hijri: Optional[str] = None
    rental_period: Optional[str] = None
    amount_sar: Optional[float] = None           # 19750.00


class Financials(BaseModel):
    total_contract_value_sar: Optional[float] = None   # 39500.00
    annual_rent_sar: Optional[float] = None            # 39500.00
    regular_payment_sar: Optional[float] = None        # 19750.00
    payment_cycle: Optional[str] = None                # نصف سنوي (semi-annual)
    number_of_payments: Optional[int] = None           # 2
    security_deposit_sar: Optional[float] = None       # may be None / 0
    electricity_annual_sar: Optional[float] = None
    water_annual_sar: Optional[float] = None
    gas_annual_sar: Optional[float] = None
    parking_annual_sar: Optional[float] = None


# --------------------------------------------------------------------------
# Key contractual terms (parsed from the legal articles, not just the tables)
# --------------------------------------------------------------------------
class KeyTerms(BaseModel):
    contract_duration_days: Optional[int] = None       # 364
    tenancy_start: Optional[date] = None               # 2025-12-19
    tenancy_end: Optional[date] = None                 # 2026-12-18
    auto_renews: Optional[bool] = None                 # True (renews unless notified)
    renewal_notice_days: Optional[int] = None          # 60 (notice before expiry to stop renewal)
    late_payment_grace_days: Optional[int] = None      # 15 or 30 depending on cycle
    holdover_daily_penalty_sar: Optional[float] = None # 500 / day if tenant doesn't vacate
    governing_law: Optional[str] = None                # Saudi law
    jurisdiction: Optional[str] = None                 # competent Saudi judicial body


# --------------------------------------------------------------------------
# Top-level extraction object
# --------------------------------------------------------------------------
class EjarContract(BaseModel):
    main_contract_no: Optional[str] = Field(None, description="PII-sensitive identifier")
    contract_registry_no: Optional[str] = Field(None, description="PII-sensitive identifier")
    contract_type: Optional[str] = None                # جديد (new)
    sealing_location: Optional[str] = None             # الرياض
    sealing_date: Optional[date] = None                # 2025-11-17

    lessor: Optional[Party] = None
    tenant: Optional[Party] = None
    broker: Optional[Party] = None
    brokerage_entity_name: Optional[str] = None        # مكتب ... للعقارات
    brokerage_cr_no: Optional[str] = Field(None, description="PII-sensitive identifier")

    title_deed_no: Optional[str] = Field(None, description="PII-sensitive identifier")
    title_deed_issuer: Optional[str] = None            # الرياض
    title_deed_issue_date: Optional[date] = None       # 2015-02-01

    property: Optional[PropertyInfo] = None
    financials: Optional[Financials] = None
    payment_schedule: list[PaymentInstallment] = Field(default_factory=list)
    key_terms: Optional[KeyTerms] = None


# --------------------------------------------------------------------------
# Insight layer — the judgment, rendered bilingually for the user
# --------------------------------------------------------------------------
class Severity(str, Enum):
    info = "info"
    important = "important"
    warning = "warning"


class DerivedInsight(BaseModel):
    code: str                                   # RENEWAL_NOTICE | EXIT_PENALTY | TOTAL_COST | PAYMENT_DUE ...
    severity: Severity
    title: str
    detail: str
    action_deadline: Optional[date] = None      # when the user must act, if any
    source_clause: Optional[str] = None         # grounding ref, e.g. "Article 3/3" — never invented


class ContractAnalysis(BaseModel):
    """The full result returned to the UI."""
    extracted: EjarContract
    insights: list[DerivedInsight] = Field(default_factory=list)
