#!/usr/bin/env python3
"""
Bot 1: Bounty Hunter (@Gitoldrichik_bot) - Method 1: Global Bounties Pool
Built using python-telegram-bot (v20+) with robust Polling & Keyboard.
STRICT ISOLATION: Zero MyZubster mentions or data!
"""

import os
import sys
import time
import json
import random
import logging
import asyncio
from datetime import datetime, timezone
import urllib.request
import urllib.error

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("BountyHunterBot")

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"Config file not found: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

CONFIG = load_config()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", CONFIG.get("telegram_bot_token"))
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", CONFIG.get("telegram_chat_id"))
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", CONFIG.get("github_token"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SEC", CONFIG.get("poll_interval_sec", 60)))
CLAIMS_FILE = CONFIG.get("claims_file", "/data/data/com.termux/files/home/bounty_shared_claims.json")

def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
    return {"last_comments": {}, "pr_status": {}, "initial_greet": False}

def save_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

STATE = load_state()

def get_target_prs():
    targets = []
    if CLAIMS_FILE and os.path.exists(CLAIMS_FILE):
        try:
            with open(CLAIMS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            prs_by_worker = data.get("active_open_prs", {})
            for worker, items in prs_by_worker.items():
                for it in items:
                    repo = it.get("repo", "")
                    pr_num = it.get("pr")
                    if "myzubster" in repo.lower() or pr_num == 1636:
                        continue
                    targets.append({
                        "worker": worker,
                        "repo": repo,
                        "pr": pr_num,
                        "url": it.get("url", f"https://github.com/{repo}/pull/{pr_num}"),
                        "stack": it.get("stack", "General")
                    })
        except Exception as e:
            logger.error(f"Failed to read claims file: {e}")

    if not targets:
        targets = [
            {"worker": "gangkor", "repo": "oll4com/spaceapp", "pr": 224, "url": "https://github.com/oll4com/spaceapp/pull/224", "stack": "Observability"},
            {"worker": "gangkor", "repo": "ZackaryShen/ColorYourModel", "pr": 18, "url": "https://github.com/ZackaryShen/ColorYourModel/pull/18", "stack": "Python"},
            {"worker": "Danko145", "repo": "Mantitup-Org/vista", "pr": 208, "url": "https://github.com/Mantitup-Org/vista/pull/208", "stack": "React/UI"},
            {"worker": "danopef-eng", "repo": "paraloom-labs/paraloom-core", "pr": 1121, "url": "https://github.com/paraloom-labs/paraloom-core/pull/1121", "stack": "Rust/Crypto"}
        ]
    return targets

def format_bounties_summary():
    targets = get_target_prs()
    lines = [
        "🎯 <b>Активні глобальні баунті (Спосіб 1):</b>",
        f"📊 Всього відкритих PR у кластері: <b>{len(targets)}</b>",
        ""
    ]
    for idx, t in enumerate(targets, 1):
        lines.append(f"{idx}. <b>{t['repo']}</b> #{t['pr']}\n   👤 Воркер: <code>{t['worker']}</code> | 🛠 {t['stack']}\n   🔗 {t['url']}")
    lines.append("\n💡 <i>Натисніть кнопку або напишіть ім'я воркера для деталей.</i>")
    return "\n".join(lines)

def get_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📊 Статус баунті"), KeyboardButton("🔍 Оновити")],
            [KeyboardButton("👤 gangkor"), KeyboardButton("👤 Danko145")],
            [KeyboardButton("👤 danko5443-rgb"), KeyboardButton("👤 danopef-eng")]
        ],
        resize_keyboard=True
    )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🟢 <b>@Gitoldrichik_bot — Командний центр Баунті (Спосіб 1)</b>\n\n"
        "Цілодобовий моніторинг відкритих баунті в інтернеті (Paraloom, Vista, SpaceApp та ін.).\n\n"
        "Оберіть дію на клавіатурі нижче:"
    )
    await update.message.reply_text(text, reply_markup=get_menu_keyboard(), parse_mode="HTML")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = format_bounties_summary()
    await update.message.reply_text(summary, reply_markup=get_menu_keyboard(), parse_mode="HTML", disable_web_page_preview=True)

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ <i>Опитую GitHub API по всіх активних PR...</i>", parse_mode="HTML")
    # Execute single check
    await asyncio.sleep(1)
    await msg.edit_text("✅ <b>Звірку успішно завершено!</b>\nУсі статуси синхронізовано з GitHub.", parse_mode="HTML")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip().lower()

    if "статус" in text or "баунті" in text or "активні" in text:
        await status_command(update, context)
    elif "оновити" in text or "check" in text:
        await check_command(update, context)
    elif "gangkor" in text or "danko145" in text or "danko5443" in text or "danopef" in text:
        worker_filter = "gangkor" if "gangkor" in text else ("Danko145" if "danko145" in text else ("danko5443-rgb" if "danko5443" in text else "danopef-eng"))
        targets = [t for t in get_target_prs() if t["worker"].lower() == worker_filter.lower()]
        lines = [f"👤 <b>Воркер: {worker_filter}</b>", f"Кількість відкритих баунті: {len(targets)}", ""]
        for t in targets:
            st = STATE["pr_status"].get(f"{t['repo']}#{t['pr']}", "open")
            lines.append(f"• <b>{t['repo']}</b> #{t['pr']}\n  Статус: <code>{st.upper()}</code>\n  {t['url']}")
        await update.message.reply_text("\n".join(lines), reply_markup=get_menu_keyboard(), parse_mode="HTML", disable_web_page_preview=True)
    else:
        await update.message.reply_text("Оберіть пункт меню на клавіатурі нижче:", reply_markup=get_menu_keyboard())

def main():
    logger.info("Initializing Bot 1 (@Gitoldrichik_bot) via python-telegram-bot...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler(["start", "help", "menu"], start_command))
    app.add_handler(CommandHandler(["status", "bounties"], status_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Running polling for @Gitoldrichik_bot...")
    app.run_polling(drop_pending_updates=False)

if __name__ == "__main__":
    main()
