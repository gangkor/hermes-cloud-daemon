#!/usr/bin/env python3
"""
Hermes Cloud Daemon: 24/7 Autonomous Cluster Coordinator & Telegram Bot.
Monitors GitHub PRs ($1060+ Bounties), synchronizes worker actions,
and delivers instant alerts via Telegram.
"""

import os
import sys
import time
import json
import base64
import logging
import threading
from datetime import datetime, timezone
import urllib.request
import urllib.error
import urllib.parse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("hermes-cloud")

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8327150816:AAGKyJzCZHw3-dDRwctin10AwjJ9uxXglDo")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7572064021")

GITHUB_TOKENS = {
    "gangkor": os.getenv("GITHUB_TOKEN_GANGKOR", ""),
    "Danko145": os.getenv("GITHUB_TOKEN_DANKO145", ""),
    "danko5443-rgb": os.getenv("GITHUB_TOKEN_DANKO5443", ""),
    "danopef-eng": os.getenv("GITHUB_TOKEN_DANOPEF", "")
}

SOLANA_WALLETS = {
    "gangkor": os.getenv("SOLANA_WALLET_GANGKOR", "3EZnNP2kfmY161XyqnRWEFgtYw6jWFXHnimU5RMqA8g8"),
    "Danko145": os.getenv("SOLANA_WALLET_DANKO145", "ExBUfiba8Bmn8PADfKboF7MzpYjv3habpvDx45PdRfJR"),
    "danko5443-rgb": os.getenv("SOLANA_WALLET_DANKO5443", "kyZ21uBacqU95ctt7Z2pn8en98o4cGxmxGXoB2Vz1hi"),
    "danopef-eng": os.getenv("SOLANA_WALLET_DANOPEF", "7Zv2Md3NLJtkLJ3HEPMESYWDEwLYW8cvNPqoH1bNj57K")
}

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "900"))  # 15 minutes
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cluster_state.json")

# Default fallback active PRs if claims registry cannot be reached
FALLBACK_PRS = {
    "gangkor": [
        {"repo": "MyZubster-Ecosystem/myzubster", "pr": 1636, "bounty": "$150", "stack": "Python / Backend"},
        {"repo": "ZackaryShen/ColorYourModel", "pr": 18, "bounty": "$50", "stack": "Python / Backend"},
        {"repo": "zhangjiayang6835-cyber/bounty-plaza", "pr": 3096, "bounty": "$60", "stack": "Python / Backend"},
        {"repo": "oll4com/spaceapp", "pr": 224, "bounty": "$600", "stack": "TypeScript / Temporal"}
    ],
    "Danko145": [
        {"repo": "sharmiaalono/go-github", "pr": 39, "bounty": "$40", "stack": "Frontend / JS"},
        {"repo": "Mantitup-Org/vista", "pr": 208, "bounty": "$40", "stack": "TypeScript / React / UI"}
    ],
    "danko5443-rgb": [
        {"repo": "zhangjiayang6835-cyber/ai-research", "pr": 1548, "bounty": "$40", "stack": "AI / LLM / Scrapers"},
        {"repo": "Senthemodder/aquarium-of-gullibles", "pr": 58, "bounty": "$30", "stack": "Data Science / Research"},
        {"repo": "FuRongJun-1999/dsh-memory", "pr": 583, "bounty": "$30", "stack": "AI / Testing / Regression"}
    ],
    "danopef-eng": [
        {"repo": "paraloom-labs/paraloom-prover-wasm", "pr": 11, "bounty": "$20", "stack": "Rust / WASM / Crypto"},
        {"repo": "paraloom-labs/paraloom-core", "pr": 1121, "bounty": "$20", "stack": "Rust / Systems / Crypto"},
        {"repo": "NSPG13/agent-bounties", "pr": 1666, "bounty": "$20", "stack": "Rust / Systems / Testing"}
    ]
}

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading state: {e}")
    return {"merged_prs": [], "closed_prs": [], "last_check": None}

def save_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving state: {e}")

def get_auth_token(user: str = "gangkor") -> str:
    token = GITHUB_TOKENS.get(user)
    if not token:
        token = GITHUB_TOKENS.get("gangkor", "")
    return token

def github_request(url: str, user: str = "gangkor", method: str = "GET", data: dict = None) -> tuple:
    token = get_auth_token(user)
    headers = {
        "User-Agent": "Hermes-Cloud-Daemon/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    encoded_data = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="ignore")
        return e.code, {"error": error_body}
    except Exception as e:
        return 0, {"error": str(e)}

def send_telegram(text: str, chat_id: str = None) -> bool:
    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat:
        logger.error("Telegram bot token or chat ID is missing!")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": text,
        "disable_web_page_preview": True
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        logger.error(f"Failed to send telegram message: {e}")
        return False

def fetch_active_prs() -> dict:
    url = "https://api.github.com/repos/gangkor/hermes-core/contents/bounty_shared_claims.json"
    status, data = github_request(url, user="gangkor")
    if status == 200 and "content" in data:
        try:
            content = base64.b64decode(data["content"]).decode("utf-8")
            claims = json.loads(content)
            if "active_open_prs" in claims:
                return claims["active_open_prs"]
        except Exception as e:
            logger.warning(f"Failed to parse remote claims: {e}")
    return FALLBACK_PRS

def check_all_prs(notify: bool = True) -> list:
    logger.info("Checking status of all active PRs...")
    active_prs = fetch_active_prs()
    state = load_state()
    results = []

    for worker, pr_list in active_prs.items():
        for item in pr_list:
            repo = item.get("repo")
            pr_num = item.get("pr")
            stack = item.get("stack", "")
            pr_id = f"{repo}#{pr_num}"
            
            url = f"https://api.github.com/repos/{repo}/pulls/{pr_num}"
            status, pr_data = github_request(url, user=worker)
            
            if status != 200:
                results.append({
                    "id": pr_id,
                    "worker": worker,
                    "repo": repo,
                    "pr": pr_num,
                    "status": "error",
                    "state": f"HTTP {status}"
                })
                continue
            
            is_merged = pr_data.get("merged", False)
            pr_state = pr_data.get("state", "open")
            title = pr_data.get("title", "")
            pr_url = pr_data.get("html_url", f"https://github.com/{repo}/pull/{pr_num}")
            
            results.append({
                "id": pr_id,
                "worker": worker,
                "repo": repo,
                "pr": pr_num,
                "title": title,
                "state": "merged" if is_merged else pr_state,
                "url": pr_url,
                "stack": stack
            })
            
            if is_merged:
                if pr_id not in state["merged_prs"]:
                    state["merged_prs"].append(pr_id)
                    save_state(state)
                    if notify:
                        wallet = SOLANA_WALLETS.get(worker, "—")
                        msg = (
                            f"🚨 УВАГА! Баунті замерджено! Перевір баланс!\n\n"
                            f"💎 Воркер: {worker}\n"
                            f"📦 Репозиторій: {repo}\n"
                            f"🔗 PR: #{pr_num} ({title})\n"
                            f"🌐 Посилання: {pr_url}\n"
                            f"💳 Solana-гаманець: {wallet}\n\n"
                            f"Статус: MERGED (Успішно закрито з нагородою!)"
                        )
                        send_telegram(msg)
            elif pr_state == "closed":
                if pr_id not in state["closed_prs"]:
                    state["closed_prs"].append(pr_id)
                    save_state(state)
                    if notify:
                        msg = (
                            f"ℹ️ Інформація: PR #{pr_num} закрито без мерджу.\n"
                            f"Воркер: {worker} | Репо: {repo}\n"
                            f"Посилання: {pr_url}"
                        )
                        send_telegram(msg)

    state["last_check"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    return results

def check_and_dispatch_workers() -> dict:
    logger.info("Auditing GitHub Actions workflow runs across all 4 workers...")
    dispatch_results = {}
    
    workers = ["gangkor", "Danko145", "danko5443-rgb", "danopef-eng"]
    for worker in workers:
        url = f"https://api.github.com/repos/{worker}/bounty-runner/actions/runs?per_page=1"
        status, data = github_request(url, user=worker)
        
        needs_dispatch = False
        reason = "healthy"
        
        if status == 200:
            runs = data.get("workflow_runs", [])
            if runs:
                last_run = runs[0]
                run_status = last_run.get("status")
                conclusion = last_run.get("conclusion")
                created_at_str = last_run.get("created_at")
                
                # Parse created time
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                    diff_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
                    if diff_hours > 3 and run_status != "in_progress":
                        needs_dispatch = True
                        reason = f"idle for {diff_hours:.1f} hours"
                except Exception:
                    pass
            else:
                needs_dispatch = True
                reason = "no runs found"
        else:
            reason = f"HTTP {status}"

        if needs_dispatch:
            dispatch_url = f"https://api.github.com/repos/{worker}/bounty-runner/actions/workflows/bounty-runner.yml/dispatches"
            d_status, _ = github_request(dispatch_url, user=worker, method="POST", data={"ref": "main"})
            if d_status == 204:
                dispatch_results[worker] = f"re-dispatched ({reason})"
                logger.info(f"Dispatched worker {worker}: {reason}")
            else:
                dispatch_results[worker] = f"dispatch failed (HTTP {d_status})"
        else:
            dispatch_results[worker] = f"ok ({reason})"

    return dispatch_results

def scheduler_loop():
    logger.info(f"Starting background scheduler loop (interval: {CHECK_INTERVAL_SECONDS}s)...")
    while True:
        try:
            check_all_prs(notify=True)
            check_and_dispatch_workers()
        except Exception as e:
            logger.error(f"Error in scheduler iteration: {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)

def telegram_bot_listener():
    logger.info("Starting Telegram bot listener (@Gankotepux_bot)...")
    offset = 0
    
    # Send online notification
    send_telegram("🚀 Hermes Cloud Daemon успішно запущено у хмарі 24/7!\nУсі 4 GitHub воркери та 12 PR ($1060+) під постійним моніторингом.")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={offset}&timeout=20"
            req = urllib.request.Request(url, headers={"User-Agent": "Hermes-Cloud-Daemon/1.0"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            
            for item in data.get("result", []):
                update_id = item.get("update_id", 0)
                offset = max(offset, update_id + 1)
                
                message = item.get("message", {})
                chat_id = str(message.get("chat", {}).get("id", ""))
                text = message.get("text", "").strip()
                
                if not text:
                    continue
                
                command = text.split()[0].lower()
                
                if command in ["/start", "/help"]:
                    reply = (
                        "🤖 Hermes Cloud Autonomous Coordinator (24/7)\n\n"
                        "Доступні команди:\n"
                        "📊 /status — Повний аудит усіх активних PR ($1060+ баунті)\n"
                        "⚡ /check — Миттєва примусова перевірка PR\n"
                        "🔄 /dispatch — Перезапуск GitHub Actions для всіх 4 воркерів\n"
                        "💳 /wallets — Перелік прив'язаних Solana гаманців\n"
                        "ℹ️ /ping — Перевірка зв'язку з хмарним демоном"
                    )
                    send_telegram(reply, chat_id=chat_id)
                
                elif command == "/ping":
                    send_telegram("🏓 Pong! Hermes Cloud Daemon активний і працює безперервно.", chat_id=chat_id)
                
                elif command == "/wallets":
                    lines = ["💳 Solana гаманці для виплат баунті:"]
                    for w, addr in SOLANA_WALLETS.items():
                        lines.append(f"• {w}: `{addr}`")
                    send_telegram("\n".join(lines), chat_id=chat_id)
                
                elif command == "/status":
                    send_telegram("⏳ Збираю актуальні дані з GitHub API...", chat_id=chat_id)
                    prs = check_all_prs(notify=False)
                    open_count = sum(1 for p in prs if p.get("state") == "open")
                    merged_count = sum(1 for p in prs if p.get("state") == "merged")
                    
                    lines = [
                        f"📊 Статус баунті-кластера:",
                        f"• Всього активних PR: {len(prs)}",
                        f"• Відкрито (на розгляді): {open_count}",
                        f"• Замерджено: {merged_count}",
                        "",
                        "Список задач:"
                    ]
                    for p in prs:
                        icon = "🟢" if p.get("state") == "open" else ("💎" if p.get("state") == "merged" else "⚪")
                        lines.append(f"{icon} #{p.get('pr')} {p.get('repo')} ({p.get('worker')}): {p.get('state').upper()}")
                    send_telegram("\n".join(lines), chat_id=chat_id)
                
                elif command == "/check":
                    send_telegram("🔍 Запуск позачергової звірки PR та воркерів...", chat_id=chat_id)
                    prs = check_all_prs(notify=True)
                    send_telegram(f"✅ Перевірку завершено. Оброблено {len(prs)} PR.", chat_id=chat_id)
                
                elif command == "/dispatch":
                    send_telegram("🚀 Відправляю workflow_dispatch для 4 хмарних воркерів...", chat_id=chat_id)
                    res = check_and_dispatch_workers()
                    lines = ["Результати запуску:"]
                    for w, st in res.items():
                        lines.append(f"• {w}: {st}")
                    send_telegram("\n".join(lines), chat_id=chat_id)

        except Exception as e:
            logger.warning(f"Telegram polling warning: {e}")
            time.sleep(3)

def main():
    logger.info("Initializing Hermes Cloud Core...")
    
    # Thread 1: Telegram Bot Polling
    bot_thread = threading.Thread(target=telegram_bot_listener, daemon=True)
    bot_thread.start()
    
    # Thread 2: 15-minute Scheduler
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    
    # Keep main thread alive
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
