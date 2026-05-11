"""SQLite persistence for parsed invoice records and reimbursement status."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from services.records import (
    DEFAULT_STATUS,
    STATUS_FIELD,
    amount_value,
    ensure_status,
    record_identity,
)


class InvoiceStore:
    """Small SQLite repository for the local single-user app."""

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identity_key TEXT NOT NULL UNIQUE,
                    filename TEXT,
                    invoice_number TEXT,
                    order_number TEXT,
                    invoice_date TEXT,
                    seller_name TEXT,
                    buyer_name TEXT,
                    total REAL DEFAULT 0,
                    reimbursement_status TEXT NOT NULL DEFAULT '未报销',
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS invoices_updated_at
                AFTER UPDATE ON invoices
                BEGIN
                    UPDATE invoices SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END
                """
            )

    def get_status(self, identity_key: str) -> str | None:
        if not identity_key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT reimbursement_status FROM invoices WHERE identity_key = ?",
                (identity_key,),
            ).fetchone()
        return row["reimbursement_status"] if row else None

    def save_record(self, record: dict) -> dict:
        record = ensure_status(dict(record))
        key = record_identity(record)
        if not key:
            return record

        filename = record.get("文件名", "")
        saved_status = self.get_status(key) or self.get_status(filename)
        if saved_status:
            record[STATUS_FIELD] = saved_status

        payload_json = json.dumps(record, ensure_ascii=False)
        params = {
            "identity_key": key,
            "filename": record.get("文件名", ""),
            "invoice_number": record.get("发票号码", ""),
            "order_number": record.get("订单号", ""),
            "invoice_date": record.get("开票日期", ""),
            "seller_name": record.get("销售方名称", ""),
            "buyer_name": record.get("购买方名称", ""),
            "total": amount_value(record.get("价税合计")),
            "reimbursement_status": record.get(STATUS_FIELD) or DEFAULT_STATUS,
            "payload_json": payload_json,
        }

        with self._connect() as conn:
            if filename and filename != key:
                conn.execute(
                    """
                    DELETE FROM invoices
                    WHERE filename = ?
                      AND identity_key != ?
                    """,
                    (filename, key),
                )
            conn.execute(
                """
                INSERT INTO invoices (
                    identity_key, filename, invoice_number, order_number, invoice_date,
                    seller_name, buyer_name, total, reimbursement_status, payload_json
                )
                VALUES (
                    :identity_key, :filename, :invoice_number, :order_number, :invoice_date,
                    :seller_name, :buyer_name, :total, :reimbursement_status, :payload_json
                )
                ON CONFLICT(identity_key) DO UPDATE SET
                    filename = excluded.filename,
                    invoice_number = excluded.invoice_number,
                    order_number = excluded.order_number,
                    invoice_date = excluded.invoice_date,
                    seller_name = excluded.seller_name,
                    buyer_name = excluded.buyer_name,
                    total = excluded.total,
                    reimbursement_status = invoices.reimbursement_status,
                    payload_json = excluded.payload_json
                """,
                params,
            )
        return record

    def remove_stale_filename_records(self) -> int:
        """Delete old rows that used filename as identity after a better parse exists."""
        with self._connect() as conn:
            result = conn.execute(
                """
                DELETE FROM invoices
                WHERE identity_key = filename
                  AND EXISTS (
                    SELECT 1
                    FROM invoices newer
                    WHERE newer.filename = invoices.filename
                      AND newer.identity_key != invoices.identity_key
                      AND newer.invoice_number != ''
                  )
                """
            )
        return result.rowcount

    def update_status(self, identity_key: str, status: str) -> bool:
        if not identity_key:
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM invoices WHERE identity_key = ?",
                (identity_key,),
            ).fetchone()
            if not row:
                return False
            payload = json.loads(row["payload_json"])
            payload[STATUS_FIELD] = status
            conn.execute(
                """
                UPDATE invoices
                SET reimbursement_status = ?,
                    payload_json = ?
                WHERE identity_key = ?
                """,
                (status, json.dumps(payload, ensure_ascii=False), identity_key),
            )
        return True

    def list_records(self, limit: int = 500) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload_json, reimbursement_status
                FROM invoices
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        records = []
        for row in rows:
            record = json.loads(row["payload_json"])
            record[STATUS_FIELD] = row["reimbursement_status"]
            records.append(record)
        return records
