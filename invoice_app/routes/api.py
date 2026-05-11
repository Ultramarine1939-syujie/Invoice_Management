"""API routes for parsing, persistence, and export."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, send_file
from parser import FIELDNAMES
from repositories.invoice_store import InvoiceStore
from services.exporter import build_csv, build_excel
from services.parsing import parse_upload
from services.records import DEFAULT_STATUS, DONE_STATUS, STATUS_FIELD, ensure_status, is_pdf_file

api_bp = Blueprint("api", __name__, url_prefix="/api")


def error_response(message: str, status: int = 400, code: str = "bad_request"):
    return jsonify({"error": message, "code": code}), status


def get_store() -> InvoiceStore:
    return current_app.extensions["invoice_store"]


def get_records_payload():
    data = request.get_json(silent=True) or {}
    records = data.get("records", [])
    if not isinstance(records, list):
        return None, error_response("records 必须是数组")
    clean_records = [ensure_status(record) for record in records if isinstance(record, dict)]
    return clean_records, None


@api_bp.get("/health")
def health():
    config = current_app.config["APP_CONFIG"]
    return jsonify({
        "ok": True,
        "fields": FIELDNAMES,
        "max_upload_files": config.max_upload_files,
    })


@api_bp.post("/parse")
def parse_many():
    config = current_app.config["APP_CONFIG"]
    files = request.files.getlist("files")
    if not files:
        return error_response("未收到文件")
    if len(files) > config.max_upload_files:
        return error_response(f"单次最多上传 {config.max_upload_files} 个文件")

    records = []
    skipped = []
    store = get_store()
    for file in files:
        if not is_pdf_file(file.filename):
            skipped.append(file.filename or "未命名文件")
            continue
        records.append(parse_upload(file, store))

    if not records:
        return error_response("未找到可解析的 PDF 文件", skipped and 400 or 422)
    return jsonify({"records": records, "fields": FIELDNAMES, "skipped": skipped})


@api_bp.post("/parse_one")
def parse_one():
    file = request.files.get("file")
    if not file:
        return error_response("未收到文件")
    try:
        record = parse_upload(file, get_store())
    except ValueError as exc:
        return error_response(str(exc))
    return jsonify({"record": record, "fields": FIELDNAMES})


@api_bp.get("/records")
def records():
    limit = request.args.get("limit", "500")
    try:
        limit_value = max(1, min(int(limit), 2000))
    except ValueError:
        limit_value = 500
    return jsonify({"records": get_store().list_records(limit_value), "fields": FIELDNAMES})


@api_bp.patch("/records/status")
def update_status():
    data = request.get_json(silent=True) or {}
    key = str(data.get("key", "")).strip()
    status = str(data.get("status", DEFAULT_STATUS)).strip()
    if status not in {DEFAULT_STATUS, DONE_STATUS}:
        return error_response("报销状态不合法")
    if not key:
        return error_response("缺少记录标识")
    updated = get_store().update_status(key, status)
    if not updated:
        return error_response("未找到对应记录", 404, "not_found")
    return jsonify({"ok": True, "key": key, STATUS_FIELD: status})


@api_bp.post("/download_csv")
def download_csv():
    records_payload, response = get_records_payload()
    if response:
        return response
    return send_file(
        build_csv(records_payload),
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name="发票报销信息.csv",
    )


@api_bp.post("/download_excel")
def download_excel():
    records_payload, response = get_records_payload()
    if response:
        return response
    try:
        output = build_excel(records_payload)
    except RuntimeError as exc:
        return error_response(str(exc), 500, "missing_dependency")
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="发票报销信息.xlsx",
    )
