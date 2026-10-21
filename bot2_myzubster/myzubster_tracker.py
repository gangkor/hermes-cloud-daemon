#!/usr/bin/env python3
"""
Bot 2: MyZubster & Node Master (@Gankotepux_bot) - Method 2: MyZubster Ecosystem & VPS
Turbo-monitors PR #1636 on MyZubster-Ecosystem/myzubster.
Detects CI status changes, maintainer comments (@danieldirimini-myzubster), and SSH credentials.
Responds to user commands: /start, /status, /vps, /check
STRICT ISOLATION: Zero external bounties (Paraloom/Vista/SpaceApp) here!
"""

import os
import sys
import time
import json
import random
import logging
import threading
from datetime import datetime, timezone
import urllib.request
import urllib.error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("MyZubsterBot")

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
TARGET_REPO = CONFIG.get("target_repo", "MyZubster-Ecosystem/myzubster")
TARGET_PR = int(CONFIG.get("target_pr", 1636))
MAINTAINER = CONFIG.get("maintainer_handle", "danieldirimini-myzubster")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SEC", CONFIG.get("poll_interval_sec", 35)))

def send_telegram(text: str, target_chat: str = None, reply_markup: dict = None) -> bool:
    cid = target_chat if target_chat else CHAT_ID
    if not BOT_TOKEN or not cid:
        logger.warning("Telegram credentials missing, skipping dispatch.")
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload_dict = {
        "chat_id": cid,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload_dict["reply_markup"] = reply_markup
    payload = json.dumps(payload_dict).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "GankotepuxBot/2.0"}
    req = urllib.request.Request(url, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("ok", False)
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False

def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load state: {e}")
    return {
        "last_comment_id": None,
        "pr_state": None,
        "pr_merged": False,
        "ci_status": None,
        "initial_greet": False,
        "last_update_id": 0
    }

def save_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

def github_api_get(endpoint: str):
    url = f"https://api.github.com/{endpoint.lstrip('/')}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Gankotepux-MyZubster-Tracker"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body) if body else None
            return {"status": resp.status, "data": data}
    except urllib.error.HTTPError as he:
        if he.code in (403, 429):
            return {"status": he.code, "rate_limited": True}
        return {"status": he.code, "error": str(he)}
    except Exception as e:
        return {"status": 500, "error": str(e)}

def format_myzubster_summary(state):
    st = state.get("pr_state", "open").upper()
    ci = state.get("ci_status", "pending")
    ci_emoji = "✅" if ci == "success" else ("❌" if ci == "failure" else "⏳")
    lines = [
        "🤝 <b>[СПОСІБ 2] MyZubster Ecosystem & Партнерська Нода</b>\n",
        f"📁 Репозиторій: <code>{TARGET_REPO}</code>",
        f"🔗 Цільовий PR: <b>#{TARGET_PR}</b> (Python / Backend)",
        f"📊 Статус PR: <b>{st}</b>",
        f"{ci_emoji} GitHub Actions CI: <b>{ci.upper() if ci else 'UNKNOWN'}</b>",
        f"👤 Мейнтейнер: <b>@{MAINTAINER}</b>",
        "💎 Винагорода: <b>250 MYZ</b>",
        "🌐 Статус VPS: <b>Очікує видачі SSH ключів/доступу</b>",
        "\n📡 <i>Турбо-опитування активне кожні 35 секунд.</i>"
    ]
    return "\n".join(lines)

def monitor_myzubster(state):
    logger.info(f"Turbo-polling {TARGET_REPO} PR #{TARGET_PR}...")

    pr_res = github_api_get(f"repos/{TARGET_REPO}/pulls/{TARGET_PR}")
    if pr_res.get("rate_limited"):
        time.sleep(30)
        return

    head_sha = None
    if pr_res.get("status") == 200 and pr_res.get("data"):
        pr_data = pr_res["data"]
        curr_state = pr_data.get("state")
        curr_merged = pr_data.get("merged", False)
        head_sha = pr_data.get("head", {}).get("sha")

        old_state = state.get("pr_state")
        if old_state and old_state != curr_state:
            if curr_merged:
                msg = (
                    f"🎉 <b>MYZUBSTER PR #{TARGET_PR} ЗЛИТО В MAIN!</b>\n"
                    f"📁 Репо: <code>{TARGET_REPO}</code>\n"
                    f"💎 Винагорода: 250 MYZ активовано!\n"
                    f"🚀 Партнерська нода готова до розгортання!"
                )
            else:
                msg = (
                    f"⚡ <b>MyZubster PR #{TARGET_PR} Оновлення</b>\n"
                    f"📊 Статус змінено: <b>{curr_state.upper()}</b>"
                )
            send_telegram(msg)

        state["pr_state"] = curr_state
        state["pr_merged"] = curr_merged

    if head_sha:
        time.sleep(1.0)
        ci_res = github_api_get(f"repos/{TARGET_REPO}/commits/{head_sha}/status")
        if ci_res.get("status") == 200 and ci_res.get("data"):
            ci_state = ci_res["data"].get("state")
            old_ci = state.get("ci_status")
            if old_ci and old_ci != ci_state:
                emoji = "✅" if ci_state == "success" else ("❌" if ci_state == "failure" else "⏳")
                msg = (
                    f"{emoji} <b>GitHub Actions CI Оновлено!</b>\n"
                    f"📁 Репо: <code>{TARGET_REPO}</code>\n"
                    f"🔗 PR #{TARGET_PR} (Commit: <code>{head_sha[:7]}</code>)\n"
                    f"🚦 Новий статус CI: <b>{ci_state.upper()}</b>"
                )
                send_telegram(msg)
            state["ci_status"] = ci_state

    time.sleep(1.2 + random.uniform(0.2, 0.5))
    comm_res = github_api_get(f"repos/{TARGET_REPO}/issues/{TARGET_PR}/comments?per_page=5")
    if comm_res.get("status") == 200 and comm_res.get("data"):
        comments = comm_res["data"]
        if comments:
            last_comment = comments[-1]
            comm_id = last_comment.get("id")
            author = last_comment.get("user", {}).get("login", "")
            body = last_comment.get("body", "")

            old_comm_id = state.get("last_comment_id")
            if old_comm_id and old_comm_id != comm_id:
                is_maintainer = MAINTAINER.lower() in author.lower()
                has_ssh = any(k in body.lower() for k in ["ssh", "vps", "root@", "password", "port", "ip", "login"])
                header = "🔑 <b>УВАГА: Отримано реквізити VPS / Доступ!</b>" if has_ssh else (
                    f"👤 <b>Відповідь мейнтейнера @{author}!</b>" if is_maintainer else f"💬 <b>Новий коментар у PR #{TARGET_PR}</b>"
                )
                preview = body[:350].replace("<", "&lt;").replace(">", "&gt;")
                msg = (
                    f"{header}\n"
                    f"📁 Репо: <code>{TARGET_REPO}</code>\n"
                    f"🔗 PR #{TARGET_PR}\n"
                    f"👤 Від: <b>@{author}</b>\n\n"
                    f"📝 <b>Повідомлення:</b>\n<i>{preview}</i>"
                )
                send_telegram(msg)

            state["last_comment_id"] = comm_id

    save_state(state)

def bot_polling_loop(state):
    logger.info("Starting Telegram Command Listener for @Gankotepux_bot...")
    offset = state.get("last_update_id", 0)

    menu_keyboard = {
        "keyboard": [
            [{"text": "📊 Статус MyZubster"}, {"text": "⚡ Турбо-перевірка"}],
            [{"text": "🔑 Стан VPS / Доступ"}, {"text": "ℹ️ Довідка"}]
        ],
        "resize_keyboard": True
    }

    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=15"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
                updates = data.get("result", [])

            for u in updates:
                up_id = u.get("update_id", 0)
                offset = max(offset, up_id + 1)
                state["last_update_id"] = offset

                msg = u.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "").strip()

                if not text or not chat_id:
                    continue

                cmd = text.lower()
                if cmd in ["/start", "/help", "ℹ️ довідка", "меню"]:
                    reply = (
                        "🟣 <b>@Gankotepux_bot — MyZubster & Node Master (Спосіб 2)</b>\n\n"
                        "Я автономно веду суворий моніторинг партнерства з MyZubster, PR #1636 та очікування виділеного VPS сервера від Деніела.\n\n"
                        "<b>Команди:</b>\n"
                        "📊 /status або <i>Статус MyZubster</i> — поточний стан PR #1636 та CI\n"
                        "⚡ /check або <i>Турбо-перевірка</i> — негайне опитування GitHub API\n"
                        "🔑 /vps або <i>Стан VPS / Доступ</i> — стан домовленостей щодо ноди/VPS\n"
                        "ℹ️ /help — довідка"
                    )
                    send_telegram(reply, target_chat=chat_id, reply_markup=menu_keyboard)

                elif cmd in ["/status", "📊 статус myzubster", "активні задачі"]:
                    summary = format_myzubster_summary(state)
                    send_telegram(summary, target_chat=chat_id, reply_markup=menu_keyboard)

                elif cmd in ["/check", "⚡ турбо-перевірка"]:
                    send_telegram("⏳ <i>Опитую GitHub API по PR #1636 та останнім коментарям...</i>", target_chat=chat_id)
                    monitor_myzubster(state)
                    send_telegram("✅ <i>Турбо-перевірку завершено! Дані актуальні.</i>", target_chat=chat_id, reply_markup=menu_keyboard)

                elif cmd in ["/vps", "🔑 стан vps / доступ"]:
                    vps_info = (
                        "🔑 <b>Стан виділеного сервера VPS для MyZubster:</b>\n\n"
                        "• <b>Мейнтейнер:</b> @danieldirimini-myzubster\n"
                        "• <b>Умови:</b> Безкоштовний VPS від проекту для хостингу та розгортання Tor/Onion вузла.\n"
                        "• <b>Поточний статус:</b> Очікуємо передачу SSH-реквізитів у коментарях PR #1636.\n"
                        "• <b>Автоматичний перехоплювач:</b> АКТИВНИЙ (як тільки Деніел напише IP/порт/пароль — бот миттєво пришле пуш)."
                    )
                    send_telegram(vps_info, target_chat=chat_id, reply_markup=menu_keyboard)

                save_state(state)

        except Exception as e:
            logger.warning(f"Error in polling updates: {e}")
            time.sleep(3)

def monitor_scheduler_loop(state):
    while True:
        try:
            monitor_myzubster(state)
        except Exception as e:
            logger.error(f"Error in myzubster monitor cycle: {e}")
        time.sleep(POLL_INTERVAL)

def main():
    logger.info("Initializing Bot 2 (@Gankotepux_bot)...")
    state = load_state()

    # Startup message
    if not state.get("initial_greet"):
        greet_ok = send_telegram("🟣 <b>Бот 2 (Спосіб 2: MyZubster & Node) запущено з чистого аркуша!</b>\n\nТурбо-моніторинг PR #1636 та інтерактивні команди активовано 24/7.")
        if greet_ok:
            state["initial_greet"] = True
            save_state(state)

    # Thread 1: Telegram command listener
    t_listener = threading.Thread(target=bot_polling_loop, args=(state,), daemon=True)
    t_listener.start()

    # Thread 2: MyZubster monitor scheduler
    t_scheduler = threading.Thread(target=monitor_scheduler_loop, args=(state,), daemon=True)
    t_scheduler.start()

    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
