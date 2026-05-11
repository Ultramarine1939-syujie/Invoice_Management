"""Shared record helpers used by API, export, and storage layers."""

from __future__ import annotations

from parser import FIELDNAMES

STATUS_FIELD = "报销状态"
DEFAULT_STATUS = "未报销"
DONE_STATUS = "已报销"
FIELDNAMES_EXT = FIELDNAMES + [STATUS_FIELD]
NUMERIC_FIELDS = {"金额", "税额", "价税合计"}


def is_pdf_file(filename: str | None) -> bool:
    """Return whether the provided filename looks like a PDF."""
    return bool(filename) and filename.lower().endswith(".pdf")


def amount_value(value) -> float:
    """Convert common money strings to float without raising."""
    if value in (None, ""):
        return 0.0
    try:
        return float(str(value).replace(",", "").replace("￥", "").replace("¥", "").strip())
    except (TypeError, ValueError):
        return 0.0


def record_identity(record: dict) -> str:
    """Build a stable key for local status persistence and de-duplication."""
    return (
        record.get("发票号码")
        or record.get("订单号")
        or record.get("文件名")
        or ""
    ).strip()


def ensure_status(record: dict, status: str | None = None) -> dict:
    """Guarantee a reimbursement status field on the record."""
    record[STATUS_FIELD] = status or record.get(STATUS_FIELD) or DEFAULT_STATUS
    return record
