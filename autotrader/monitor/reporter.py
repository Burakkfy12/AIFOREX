from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List

from jinja2 import Environment, FileSystemLoader
from loguru import logger
from telegram import Bot

TEMPLATE_DIR = Path(__file__).resolve().parent


def _render_template(template_name: str, context: Dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template(template_name)
    return template.render(**context)


def create_report(metrics: Dict[str, float], trades: List[Dict], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    html = _render_template(
        "report.html.j2",
        {"generated": datetime.utcnow().isoformat(), "metrics": metrics, "trades": trades},
    )
    report_path = out_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")
    logger.info("Generated HTML report at %s", report_path)
    return report_path


def send_telegram_update(message: str, config: Dict[str, str]) -> None:
    bot = Bot(token=config["bot_token"])
    bot.send_message(chat_id=config["chat_id"], text=message, disable_web_page_preview=True)
    logger.debug("Sent Telegram update")
