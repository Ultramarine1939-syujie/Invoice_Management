from repositories.invoice_store import InvoiceStore


def test_store_persists_record_and_reimbursement_status(tmp_path):
    store = InvoiceStore(tmp_path / "invoices.sqlite3")
    record = {
        "文件名": "a.pdf",
        "发票号码": "123456",
        "订单号": "",
        "开票日期": "2026-02-22",
        "销售方名称": "销售方",
        "购买方名称": "购买方",
        "价税合计": "99.11",
        "报销状态": "未报销",
    }

    saved = store.save_record(record)
    assert saved["报销状态"] == "未报销"

    assert store.update_status("123456", "已报销") is True
    records = store.list_records()

    assert records[0]["发票号码"] == "123456"
    assert records[0]["报销状态"] == "已报销"


def test_store_reuses_existing_status_on_reparse(tmp_path):
    store = InvoiceStore(tmp_path / "invoices.sqlite3")
    store.save_record({"文件名": "a.pdf", "发票号码": "123456", "报销状态": "未报销"})
    store.update_status("123456", "已报销")

    saved = store.save_record({"文件名": "a.pdf", "发票号码": "123456", "报销状态": "未报销"})

    assert saved["报销状态"] == "已报销"


def test_store_replaces_filename_identity_after_better_reparse(tmp_path):
    store = InvoiceStore(tmp_path / "invoices.sqlite3")
    store.save_record({
        "文件名": "book.pdf",
        "发票号码": "",
        "项目类别": "89",
        "报销状态": "已报销",
    })

    saved = store.save_record({
        "文件名": "book.pdf",
        "发票号码": "18000001",
        "项目类别": "印刷品",
        "报销状态": "未报销",
    })
    records = store.list_records()

    assert saved["报销状态"] == "已报销"
    assert len(records) == 1
    assert records[0]["发票号码"] == "18000001"
    assert records[0]["项目类别"] == "印刷品"
