import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parser import parse_invoice


def test_parse_invoice_extracts_core_fields_and_order_number():
    text = """
    电子发票（普通发票）
    发票号码：26660000000000000004
    开票日期：2026年02月22日
    购 名称：示例采购有限公司 销
    纳税人识别号：91110000DEMO000004
    销 名称：示例旅行服务有限公司
    纳税人识别号：91310000DEMO000004
    *旅游服务*代订住宿 1 93.50 93.50 6% 5.61
    费
    （大写）玖拾玖圆壹角壹分 （小写）¥99.11
    开票人：示例开票员
    备注：订单号: 900000004
    """

    rec = parse_invoice(text, "平台订单900000004电子发票.pdf")

    assert rec["发票号码"] == "26660000000000000004"
    assert rec["开票日期"] == "2026年02月22日"
    assert rec["项目类别"] == "旅游服务"
    assert rec["项目名称"] == "代订住宿费"
    assert rec["数量"] == "1"
    assert rec["金额"] == "93.50"
    assert rec["税率"] == "6%"
    assert rec["税额"] == "5.61"
    assert rec["价税合计"] == "99.11"
    assert rec["订单号"] == "900000004"
    assert rec["销售方名称"] == "示例旅行服务有限公司"


def test_parse_invoice_falls_back_to_filename_order_number():
    text = """
    增值税普通发票
    发票号码：12345678901234567890
    开票日期：2026-02-22
    *旅游服务*旅游服务费 1205.66 205.66 6% 12.34
    （小写）¥218.00
    """

    rec = parse_invoice(text, "平台订单987654321电子发票.pdf")

    assert rec["发票类型"] == "增值税普通发票"
    assert rec["订单号"] == "987654321"
    assert rec["单价"] == "1205.66"
    assert rec["金额"] == "205.66"


def test_parse_invoice_returns_line_items_and_review_metadata():
    text = """
    电子发票（普通发票）
    发票号码：1234567890
    开票日期：2026-02-22
    销 名称：上海示例服务有限公司
    （小写）¥218.00
    *旅游服务*服务费 1205.66 205.66 6% 12.34
    *交通运输服务*车费 1 10.00 10.00 3% 0.30
    """

    rec = parse_invoice(text, "示例发票.pdf")

    assert rec["解析状态"] in {"已解析", "需复核"}
    assert rec["置信度"] > 0
    assert len(rec["商品明细"]) == 2
    assert rec["商品明细"][1]["项目类别"] == "交通运输服务"
