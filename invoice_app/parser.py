"""
电子发票（普通发票）PDF 解析模块
用 pdfplumber 提取文本，正则匹配提取字段。
"""

import io
import re

import pdfplumber

FIELDNAMES = [
    "文件名",
    "发票号码",
    "开票日期",
    "发票类型",
    "项目名称",
    "项目类别",
    "数量",
    "单价",
    "金额",
    "税率",
    "税额",
    "价税合计",
    "合计大写",
    "购买方名称",
    "购买方税号",
    "销售方名称",
    "销售方税号",
    "开票人",
    "订单号",
    "备注",
]

LINE_ITEM_FIELDS = ["项目类别", "项目名称", "规格型号", "单位", "数量", "单价", "金额", "税率", "税额"]
COMMON_UNITS = {
    "本",
    "支",
    "块",
    "台",
    "个",
    "次",
    "册",
    "件",
    "项",
    "套",
    "张",
    "辆",
    "人",
    "天",
    "晚",
    "份",
}


def blank_record(filename: str, remark: str = "") -> dict:
    """Create a record with all public fields initialized."""
    rec = {f: "" for f in FIELDNAMES}
    rec["文件名"] = filename
    rec["商品明细"] = []
    rec["解析状态"] = "待解析"
    rec["置信度"] = 0
    rec["解析备注"] = remark
    if remark:
        rec["备注"] = remark
    return rec


def normalize_text(text: str) -> str:
    """归一化 PDF 文本中的常见空白和符号差异。"""
    text = text.replace("\u3000", " ")
    text = text.replace("￥", "¥")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_value(value: str) -> str:
    """清理字段尾部常见干扰字符。"""
    return re.sub(r"\s+", " ", value or "").strip(" :：")


def money(value: str) -> str:
    """规范金额字符串。"""
    return clean_value(value).replace(",", "").replace("¥", "")


def first_match(patterns, text: str, group: int = 1) -> str:
    """按顺序尝试多个正则，返回第一个命中的分组。"""
    for pattern in patterns:
        m = re.search(pattern, text, re.MULTILINE)
        if m:
            return clean_value(m.group(group))
    return ""


def normalize_date_parts(year: str, month: str, day: str) -> str:
    return f"{year}年{int(month):02d}月{int(day):02d}日"


def extract_invoice_date(text: str) -> str:
    patterns = [
        r"开票日期[：:]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        r"开票日期[：:]\s*(\d{4})[-/]\s*(\d{1,2})[-/]\s*(\d{1,2})",
        r"国家税务总局\s*章\s*(\d{4})\s+(\d{1,2})\s+(\d{1,2})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.MULTILINE)
        if m:
            return normalize_date_parts(m.group(1), m.group(2), m.group(3))
    return ""


def parse_invoice_type(text: str) -> str:
    """Recognize common invoice type names from extracted text."""
    if "电子发票（普通发票）" in text:
        return "电子发票（普通发票）"
    if "增值税电子普通发票" in text:
        return "增值税电子普通发票"
    if "电子发票" in text:
        return "电子发票"
    if "增值税专用发票" in text:
        return "增值税专用发票"
    if "增值税普通发票" in text:
        return "增值税普通发票"
    return "未知类型"


def _looks_like_continuation(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    blocked = ("合 计", "价税合计", "备", "注", "开票人", "收款人", "复核", "名 称", "纳税人识别号")
    if any(token in line for token in blocked):
        return False
    if "¥" in line or re.search(r"\d+(?:\.\d+)?%", line):
        return False
    return bool(re.search(r"[\u4e00-\u9fa5A-Za-z]", line))


def _looks_like_spec(token: str) -> bool:
    if token == "无":
        return True
    return bool(re.search(r"\d", token) and re.search(r"[A-Za-z0-9]", token))


def parse_line_item(line: str, next_line: str = "") -> dict | None:
    """Parse one starred invoice item line such as '*旅游服务*住宿 1 93.50 93.50 6% 5.61'."""
    m = re.search(r"\*([^*]+)\*\s*(.+?)\s+(\d+(?:\.\d+)?)%\s+([\d,]+(?:\.\d+)?)\s*$", line)
    if not m:
        return None

    item = {field: "" for field in LINE_ITEM_FIELDS}
    item["项目类别"] = m.group(1).strip()
    item["税率"] = m.group(3) + "%"
    item["税额"] = money(m.group(4))

    prefix_tokens = m.group(2).strip().split()
    numeric_tail = []
    while prefix_tokens and re.fullmatch(r"\d+(?:\.\d+)?", prefix_tokens[-1]):
        numeric_tail.insert(0, prefix_tokens.pop())

    if len(numeric_tail) >= 3:
        item["数量"] = numeric_tail[-3]
        item["单价"] = money(numeric_tail[-2])
        item["金额"] = money(numeric_tail[-1])
    elif len(numeric_tail) >= 2:
        item["单价"] = money(numeric_tail[-2])
        item["金额"] = money(numeric_tail[-1])
    else:
        return None

    if prefix_tokens and prefix_tokens[-1] in COMMON_UNITS:
        item["单位"] = prefix_tokens.pop()
    if prefix_tokens and _looks_like_spec(prefix_tokens[-1]):
        item["规格型号"] = prefix_tokens.pop()

    name_tokens = prefix_tokens
    if next_line and _looks_like_continuation(next_line):
        continuation = next_line.strip()
        if re.fullmatch(r"[\u4e00-\u9fa5]{1,10}", continuation) and name_tokens:
            name_tokens[-1] += continuation
        else:
            name_tokens.extend(continuation.split())
    item["项目名称"] = clean_value(" ".join(name_tokens))

    return item


def extract_line_items(text: str) -> list[dict]:
    """Extract all recognizable invoice item rows."""
    lines = text.split("\n")
    items = []
    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        item = parse_line_item(line, next_line)
        if item:
            items.append(item)
    return items


def finalize_record(rec: dict) -> dict:
    """Attach parser metadata that downstream screens can use for review."""
    important_fields = ["发票号码", "开票日期", "价税合计", "销售方名称", "购买方名称"]
    filled = sum(1 for field in important_fields if rec.get(field))
    if rec.get("项目名称"):
        filled += 1
    confidence = round(filled / (len(important_fields) + 1), 2)
    rec["置信度"] = confidence
    rec["解析状态"] = "已解析" if confidence >= 0.5 else "需复核"
    if not rec.get("解析备注"):
        rec["解析备注"] = "关键字段完整" if confidence >= 0.8 else "部分关键字段缺失，建议人工复核"
    return rec


def extract_tax_numbers(text: str) -> tuple[str, str]:
    """Return buyer and seller tax numbers while preserving empty buyer tax fields."""
    for line in text.splitlines():
        if "统一社会信用代码/纳税人识别号" in line and line.count("统一社会信用代码/纳税人识别号") >= 2:
            parts = line.split("统一社会信用代码/纳税人识别号：")
            if len(parts) < 3:
                parts = line.split("统一社会信用代码/纳税人识别号:")
            if len(parts) >= 3:
                buyer_match = re.search(r"[0-9A-Z]{6,}", parts[1])
                seller_match = re.search(r"[0-9A-Z]{6,}", parts[2])
                return (
                    buyer_match.group(0) if buyer_match else "",
                    seller_match.group(0) if seller_match else "",
                )

    matches = re.findall(r"(?:纳税人识别号|统一社会信用代码)[：:][ \t]*([0-9A-Z]{6,})", text)
    if not matches:
        matches = [
            match
            for match in re.findall(r"\b[0-9A-Z]{15,20}\b", text)
            if any(char.isalpha() for char in match)
        ]
    if matches:
        return matches[0], matches[1] if len(matches) >= 2 else ""
    return "", ""


def clean_name_line(value: str) -> str:
    value = clean_value(value)
    value = re.sub(r"\s+[0-9A-Z<>/+*-]{6,}.*$", "", value)
    return clean_value(value)


def extract_party_names(text: str, buyer_tax: str = "", seller_tax: str = "") -> tuple[str, str]:
    same_line = re.search(r"购\s*名称[：:]\s*(.+?)\s+销\s*名称[：:]\s*(.+)", text)
    if same_line:
        return clean_name_line(same_line.group(1)), clean_name_line(same_line.group(2))

    names = [
        clean_name_line(match)
        for match in re.findall(r"名\s*称[：:][ \t]*([^\n]*)", text)
        if clean_name_line(match) and clean_name_line(match) not in {"销 备", "密"}
    ]
    if len(names) >= 2:
        return names[0], names[1]

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    buyer_name = names[0] if names else ""
    seller_name = ""
    for index, line in enumerate(lines):
        if buyer_tax and buyer_tax in line and not buyer_name and index > 0:
            buyer_name = clean_name_line(lines[index - 1])
        if seller_tax and seller_tax in line and not seller_name and index > 0:
            seller_name = clean_name_line(lines[index - 1])
    return buyer_name, seller_name


def extract_legacy_invoice_number(text: str) -> str:
    number = first_match([
        r"发票号码[：:]\s*(\d+)",
        r"发票代码.*?号码[：:]\s*(\d+)",
        r"统一发票监\s*(\d{8})",
        r"Invoice\s*No\.?[：:\s]*(\d+)",
    ], text)
    if number:
        return number
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if "增值税电子普通发票" in line and index + 1 < len(lines):
            m = re.search(r"\b(\d{8})\b", lines[index + 1])
            if m:
                return m.group(1)
    return ""


def extract_total_amounts(text: str) -> tuple[str, str]:
    small = ""
    big = ""
    m = re.search(r"[（(]大写[）)]\s*([零壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元角整分]+)\s*[（(]小写[）)]\s*¥?\s*([\d,]+\.?\d*)", text)
    if m:
        return money(m.group(2)), m.group(1).strip()

    m = re.search(r"[（(]小写[）)]\s*¥?\s*([\d,]+\.?\d*)", text)
    if m:
        small = money(m.group(1))

    m = re.search(r"[（(]大写[）)]\s*([零壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元角整分]+)", text)
    if m:
        big = m.group(1).strip()

    if not small or not big:
        fallback = re.search(r"([零壹贰叁肆伍陆柒捌玖拾佰仟万亿圆元角整分]+)\s*¥\s*([\d,]+\.?\d*)", text)
        if fallback:
            big = big or fallback.group(1).strip()
            small = small or money(fallback.group(2))
    return small, big


def extract_drawer(text: str) -> str:
    matches = re.findall(r"开\s*票\s*人[：:]\s*([^\s]+)", text)
    for match in matches:
        value = clean_value(match)
        if value and not value.startswith("销售方"):
            return value
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        tail_names = re.findall(r"[\u4e00-\u9fa5]{2,4}", lines[-1])
        if len(tail_names) >= 3:
            return tail_names[-1]
    return ""


def extract_text_from_bytes(pdf_bytes: bytes) -> str:
    """从 PDF 字节流提取全文（合并所有页）。"""
    texts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                texts.append(t)
    return "\n".join(texts)


def parse_invoice(text: str, filename: str) -> dict:
    """从电子发票（普通发票）文本中解析各字段。"""
    text = normalize_text(text)
    rec = blank_record(filename)

    # 发票类型
    rec["发票类型"] = parse_invoice_type(text)

    # 发票号码
    rec["发票号码"] = extract_legacy_invoice_number(text)

    # 开票日期
    rec["开票日期"] = extract_invoice_date(text)

    rec["购买方税号"], rec["销售方税号"] = extract_tax_numbers(text)
    rec["购买方名称"], rec["销售方名称"] = extract_party_names(
        text,
        rec["购买方税号"],
        rec["销售方税号"],
    )

    # 项目名称 — *类别*名称 格式，如 *旅游服务*旅游服务费
    # PDF排版可能导致名称末尾被挤到下一行，需要拼接
    items = extract_line_items(text)
    rec["商品明细"] = items
    lines = text.split('\n')
    for i, line in enumerate(lines):
        item = parse_line_item(line, lines[i + 1] if i + 1 < len(lines) else "")
        if item:
            for field in LINE_ITEM_FIELDS:
                rec[field] = item.get(field, "")
            break
    if not rec["项目名称"]:
        m = re.search(r"项目名称\s*(.+)", text)
        if m:
            rec["项目名称"] = m.group(1).strip()

    # 更精确的匹配：在项目行中找数量
    # 尝试匹配形如 "1 93.5 93.50 6% 5.61" 或 "1205.66 205.66 6% 12.34"
    # 根据提取的3张发票，格式为：项目名称 单价 金额 税率 税额（无数量列时数量为空）
    m_qty = re.search(r"\*[^*]+\*\s*\S+\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)%\s+(\d+\.?\d*)", text)
    if m_qty:
        rec["单价"] = rec["单价"] or money(m_qty.group(1))
        rec["金额"] = rec["金额"] or money(m_qty.group(2))
        rec["税率"] = rec["税率"] or m_qty.group(3) + "%"
        rec["税额"] = rec["税额"] or money(m_qty.group(4))
    else:
        # 带数量的格式：项目名称 数量 单价 金额 税率 税额
        m_qty2 = re.search(r"\*[^*]+\*\s*\S+\s+(\d+)\s+(\d+\.?\d*)\s+(\d+\.?\d*)\s+(\d+\.?\d*)%\s+(\d+\.?\d*)", text)
        if m_qty2:
            rec["数量"] = rec["数量"] or m_qty2.group(1)
            rec["单价"] = rec["单价"] or money(m_qty2.group(2))
            rec["金额"] = rec["金额"] or money(m_qty2.group(3))
            rec["税率"] = rec["税率"] or m_qty2.group(4) + "%"
            rec["税额"] = rec["税额"] or money(m_qty2.group(5))

    rec["价税合计"], rec["合计大写"] = extract_total_amounts(text)

    # 开票人
    rec["开票人"] = extract_drawer(text)

    # 订单号：优先识别正文，其次从文件名中抓取常见平台订单号。
    rec["订单号"] = first_match([
        r"订单号[：:\s]*(\d{6,})",
        r"订单编号[：:\s]*(\d{6,})",
        r"Order\s*No\.?[：:\s]*(\d{6,})",
    ], text)
    if not rec["订单号"]:
        m = re.search(r"订单(\d{6,})", filename)
        if m:
            rec["订单号"] = m.group(1)

    if len(items) > 1 and not rec["备注"]:
        rec["备注"] = f"识别到 {len(items)} 条商品明细，首条用于表格汇总"

    return finalize_record(rec)


def process_pdf_bytes(pdf_bytes: bytes, filename: str) -> dict:
    """从 PDF 字节流解析，返回一条记录。"""
    try:
        text = extract_text_from_bytes(pdf_bytes)
        if not text.strip():
            rec = blank_record(filename, "图片型PDF，需OCR，暂跳过")
            rec["解析状态"] = "需OCR"
            return rec
        if any(k in text for k in ["发票号码", "电子发票", "增值税"]):
            return parse_invoice(text, filename)
        rec = blank_record(filename, "未识别的发票格式")
        rec["解析状态"] = "未识别"
        return rec
    except Exception as e:
        rec = blank_record(filename, f"解析错误: {e}")
        rec["解析状态"] = "解析错误"
        return rec
