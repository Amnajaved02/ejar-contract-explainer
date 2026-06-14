EXTRACTION_INSTRUCTIONS = """You extract structured data from a Saudi EJAR tenancy contract \
(عقد إيجار). You are given the page images of one contract.

Rules:
- Extract ONLY information actually present. If a field is absent, use null. Never guess.
- Keep Arabic values exactly as written (e.g. نصف سنوي, شقة, عمارة). Do not translate them here.
- Dates: Gregorian as ISO (YYYY-MM-DD). Keep Hijri dates as strings in their own fields.
- PRIVACY: never output personal identifiers. Set name, id_number, email, mobile,
  national_address, and any *_no identifier fields to null even if they appear in the image.
- Read the legal articles (الالتزامات / المواد) to fill key_terms: contract_duration_days,
  renewal_notice_days, auto_renews, late_payment_grace_days, holdover_daily_penalty_sar.
- Build payment_schedule from the 'Rent Payments Schedule / جدول سداد الدفعات' table.
- Return a single object matching the provided schema. No prose, no markdown."""
