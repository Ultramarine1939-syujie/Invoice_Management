# 发票报销信息整理系统

用于批量整理电子发票 PDF：上传文件后自动提取发票号码、开票日期、项目、金额、购销方等字段，并支持筛选、报销状态标记、CSV/Excel 导出、图表汇总和本地历史记录保存。

## 项目结构

```text
.
├── invoice_app/
│   ├── app.py                    # Flask 应用入口
│   ├── config.py                 # 环境变量配置
│   ├── parser.py                 # PDF 文本提取与发票字段解析
│   ├── repositories/             # SQLite 持久化
│   ├── routes/                   # Flask API 蓝图
│   ├── services/                 # 解析、导出和通用业务逻辑
│   ├── static/css/app.css        # 前端样式
│   ├── static/js/app.js          # 前端交互
│   ├── templates/index.html      # 页面模板
│   ├── tests/                    # 自动化测试
│   └── tools/                    # 本地辅助脚本
├── pyproject.toml                # 测试与代码检查配置
└── .env.example                  # 可选环境变量示例
```

## 快速启动

```powershell
cd .\invoice_app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

浏览器访问：

```text
http://127.0.0.1:8080
```

## 配置

可参考根目录 `.env.example` 设置环境变量：

```text
APP_HOST=127.0.0.1
PORT=8080
FLASK_DEBUG=0
MAX_UPLOAD_FILES=100
MAX_CONTENT_LENGTH_MB=100
DATABASE_PATH=data/invoices.sqlite3
```

默认 SQLite 数据库位于 `invoice_app/data/invoices.sqlite3`，会自动创建。

## 数据安全

仓库不包含真实发票、真实税号、真实订单号或运行数据库。请把个人样本 PDF 放在 `invoice_example/` 或 `private_samples/` 下，这些目录已被 `.gitignore` 排除。

上传 GitHub 前建议检查：

```powershell
git status --short
rg -n "真实公司名|真实税号|真实订单号"
```

## 测试与检查

```powershell
cd .\invoice_app
python -m pip install -r requirements-dev.txt
python -m pytest ..\invoice_app\tests
python -m ruff check .
```

也可以在仓库根目录执行：

```powershell
python -m pytest
```

## 当前能力

- 批量上传 PDF 发票并逐个解析
- 提取发票基础字段、购销方、金额、税额、价税合计
- 返回解析状态、置信度和商品明细，便于人工复核
- 自动识别部分订单号
- 前端筛选、排序、查看详情和图表汇总
- 报销状态保存到 SQLite，并保留浏览器本地缓存作为兜底
- 导出 CSV 和多 Sheet Excel

## 后续建议

- 为私有 PDF 样本建立本地回归测试，不提交真实样本
- 增加 OCR，用于图片型 PDF
- 支持更多数电票、专票、普票和平台发票版式
- 增加人工编辑字段并回写数据库
- 根据公司报销模板定制 Excel 导出格式
