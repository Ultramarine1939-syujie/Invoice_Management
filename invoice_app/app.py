"""
发票报销信息整理系统 - Flask 后端
运行: python app.py
访问: http://127.0.0.1:8080
"""

from __future__ import annotations

from config import CONFIG, AppConfig
from flask import Flask, render_template
from repositories.invoice_store import InvoiceStore
from routes.api import api_bp


def create_app(config: AppConfig = CONFIG) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = config.max_content_length
    app.config["APP_CONFIG"] = config
    store = InvoiceStore(config.database_path)
    store.remove_stale_filename_records()
    app.extensions["invoice_store"] = store
    app.register_blueprint(api_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=CONFIG.debug, port=CONFIG.port, host=CONFIG.host)
