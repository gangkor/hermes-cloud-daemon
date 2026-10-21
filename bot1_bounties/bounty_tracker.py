#!/usr/bin/env python3
"""
Bot 1: Bounty Hunter (@Gitoldrichik_bot) - Method 1: Global Bounties Pool
Monitors open external bounties (Paraloom, Vista, SpaceApp, ColorYourModel, etc.)
Responds to user commands: /start, /status, /check, /bounties, /workers
STRICT ISOLATION: Zero MyZubster mentions or data!
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
    headers = {"Content-Type": "application/json", "User-Agent": "GitoldrichikBot/2.0"}
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
    return {"last_comments": {}, "pr_status": {}, "initial_greet": False, "last_update_id": 0}

def save_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

def github_api_get(endpoint: str, etag: str = None):
    url = f"https://api.github.com/{endpoint.lstrip('/')}"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Gitoldrichik-Bounty-Tracker"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    if etag:
        headers["If-None-Match"] = etag

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_etag = resp.headers.get("ETag")
            body = resp.read().decode("utf-8")
            data = json.loads(body) if body else None
            return {"status": resp.status, "data": data, "etag": res_etag}
    except urllib.error.HTTPError as he:
        if he.code == 304:
            return {"status": 304, "data": None, "etag": etag}
        if he.code in (403, 429):
            logger.warning(f"GitHub Rate Limit hit on {endpoint} (HTTP {he.code})")
            return {"status": he.code, "rate_limited": True}
        return {"status": he.code, "error": str(he)}
    except Exception as e:
        return {"status": 500, "error": str(e)}

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
                    # STRICT ISOLATION: Skip MyZubster
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
        f"📊 Всього завдань у пулі: <b>{len(targets)}</b>",
        ""
    ]
    for idx, t in enumerate(targets, 1):
        lines.append(f"{idx}. <b>{t['repo']}</b> #{t['pr']}\n   👤 Воркер: <code>{t['worker']}</code> | 🛠 {t['stack']}\n   🔗 {t['url']}")
    lines.append("\n💡 <i>Надішліть /check для негайного оновлення статусів.</i>")
    return "\n".join(lines)

def monitor_cycle(state):
    targets = get_target_prs()
    logger.info(f"Checking {len(targets)} active open bounty PRs (Спосіб 1)...")

    for t in targets:
        repo = t["repo"]
        pr_num = t["pr"]
        worker = t["worker"]
        key = f"{repo}#{pr_num}"

        pr_res = github_api_get(f"repos/{repo}/pulls/{pr_num}")
        if pr_res.get("rate_limited"):
            time.sleep(30)
            break

        if pr_res.get("status") == 200 and pr_res.get("data"):
            pr_data = pr_res["data"]
            current_state = pr_data.get("state")
            merged = pr_data.get("merged", False)

            old_state = state["pr_status"].get(key)
            if old_state and old_state != current_state:
                if merged:
                    msg = (
                        f"🎉 <b>БАУНТІ СХВАЛЕНО / MERGED!</b>\n"
                        f"📁 Репо: <code>{repo}</code>\n"
                        f"🔗 PR: #{pr_num} ({worker})\n"
                        f"💰 Статус: Злито в main! Перевіряй виплату!"
                    )
                else:
                    msg = (
                        f"🔔 <b>Зміна статусу PR</b>\n"
                        f"📁 Репо: <code>{repo}</code>\n"
                        f"🔗 PR: #{pr_num} ({worker})\n"
                        f"📊 Статус: <b>{current_state.upper()}</b>"
                    )
                send_telegram(msg)

            state["pr_status"][key] = "merged" if merged else current_state

        time.sleep(1.2 + random.uniform(0.2, 0.5))
        comm_res = github_api_get(f"repos/{repo}/issues/{pr_num}/comments?per_page=5")
        if comm_res.get("status") == 200 and comm_res.get("data"):
            comments = comm_res["data"]
            if comments:
                last_comment = comments[-1]
                comm_id = last_comment.get("id")
                author = last_comment.get("user", {}).get("login", "unknown")
                body = last_comment.get("body", "")

                last_known_id = state["last_comments"].get(key)
                if last_known_id and last_known_id != comm_id:
                    if author not in ("gangkor", "Danko145", "danko5443-rgb", "danopef-eng", "github-actions[bot]"):
                        preview = body[:250].replace("<", "&lt;").replace(">", "&gt;")
                        msg = (
                            f"💬 <b>Новий коментар мейнтейнера!</b>\n"
                            f"📁 Репо: <code>{repo}</code>\n"
                            f"🔗 PR: #{pr_num} ({worker})\n"
                            f"👤 Автор: <b>@{author}</b>\n"
                            f"📝 Текст:\n<i>{preview}...</i>"
                        )
                        send_telegram(msg)
                state["last_comments"][key] = comm_id

        time.sleep(1.5 + random.uniform(0.3, 0.7))

    save_state(state)

def bot_polling_loop(state):
    logger.info("Starting Telegram Command Listener for @Gitoldrichik_bot...")
    offset = state.get("last_update_id", 0)

    menu_keyboard = {
        "keyboard": [
            [{"text": "📊 Статус баунті"}, {"text": "🔍 Оновити"}],
            [{"text": "👤 gangkor"}, {"text": "👤 Danko145"}],
            [{"text": "👤 danko5443-rgb"}, {"text": "👤 danopef-eng"}]
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
                if cmd in ["/start", "/help", "головне меню", "меню"]:
                    reply = (
                        "🤖 <b>@Gitoldrichik_bot — Командний центр (Спосіб 1: Глобальні баунті)</b>\n\n"
                        "Я автономно відстежую пули винагород у відкритих репозиторіях (Paraloom, Vista, SpaceApp та ін.).\n\n"
                        "<b>Команди:</b>\n"
                        "📊 /status або <i>Статус баунті</i> — перелік активних завдань\n"
                        "🔍 /check або <i>Оновити</i> — негайна позачергова звірка\n"
                        "👤 <i>[Ім'я воркера]</i> — деталі по PR конкретного воркера\n"
                        "❓ /help — довідка"
                    )
                    send_telegram(reply, target_chat=chat_id, reply_markup=menu_keyboard)

                elif cmd in ["/status", "/bounties", "📊 статус баунті", "активні задачі"]:
                    summary = format_bounties_summary()
                    send_telegram(summary, target_chat=chat_id, reply_markup=menu_keyboard)

                elif cmd in ["/check", "🔍 оновити"]:
                    send_telegram("⏳ <i>Опитую GitHub API по всіх активних PR...</i>", target_chat=chat_id)
                    monitor_cycle(state)
                    send_telegram("✅ <i>Звірку завершено! Усі PR оновлені.</i>", target_chat=chat_id, reply_markup=menu_keyboard)

                elif "gangkor" in cmd or "danko145" in cmd or "danko5443" in cmd or "danopef" in cmd:
                    worker_filter = "gangkor" if "gangkor" in cmd else ("Danko145" if "danko145" in cmd else ("danko5443-rgb" if "danko5443" in cmd else "danopef-eng"))
                    targets = [t for t in get_target_prs() if t["worker"].lower() == worker_filter.lower()]
                    lines = [f"👤 <b>Воркер: {worker_filter}</b>", f"Кількість відкритих баунті: {len(targets)}", ""]
                    for t in targets:
                        st = state["pr_status"].get(f"{t['repo']}#{t['pr']}", "open")
                        lines.append(f"• <b>{t['repo']}</b> #{t['pr']}\n  Статус: <code>{st.upper()}</code>\n  {t['url']}")
                    send_telegram("\n".join(lines), target_chat=chat_id, reply_markup=menu_keyboard)

                save_state(state)

        except Exception as e:
            logger.warning(f"Error in polling updates: {e}")
            time.sleep(3)

def monitor_scheduler_loop(state):
    while True:
        try:
            monitor_cycle(state)
        except Exception as e:
            logger.error(f"Error in monitor cycle: {e}")
        time.sleep(POLL_INTERVAL)

def main():
    logger.info("Initializing Bot 1 (@Gitoldrichik_bot)...")
    state = load_state()

    # Startup message
    if not state.get("initial_greet"):
        greet_ok = send_telegram("🟢 <b>Бот 1 (Спосіб 1: Баунті-мисливець) запущено з чистого аркуша!</b>\n\nМоніторинг глобальних відкритих баунті та інтерактивні команди активовано 24/7.")
        if greet_ok:
            state["initial_greet"] = True
            save_state(state)

    # Thread 1: Telegram command listener
    t_listener = threading.Thread(target=bot_polling_loop, args=(state,), daemon=True)
    t_listener.start()

    # Thread 2: GitHub monitor scheduler
    t_scheduler = threading.Thread(target=monitor_scheduler_loop, args=(state,), daemon=True)
    t_scheduler.start()

    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
