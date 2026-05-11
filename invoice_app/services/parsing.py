"""Upload validation and parser orchestration."""

from __future__ import annotations

from parser import FIELDNAMES, process_pdf_bytes
from werkzeug.datastructures import FileStorage

from services.records import DEFAULT_STATUS, ensure_status, is_pdf_file, record_identity


def empty_record(filename: str, remark: str) -> dict:
    record = {field: "" for field in FIELDNAMES}
    record["文件名"] = filename
    record["备注"] = remark
    return ensure_status(record)


def parse_upload(file: FileStorage, store=None) -> dict:
    """Validate and parse one uploaded PDF file."""
    filename = file.filename or "未命名文件"
    if not is_pdf_file(filename):
        raise ValueError("仅支持 PDF 文件")

    pdf_bytes = file.read()
    if not pdf_bytes:
        return empty_record(filename, "空文件，未解析")

    record = ensure_status(process_pdf_bytes(pdf_bytes, filename), DEFAULT_STATUS)
    key = record_identity(record)
    if store and key:
        record = store.save_record(record)
    return record
