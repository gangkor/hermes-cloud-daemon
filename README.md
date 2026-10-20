# 🌐 Hermes Cloud Daemon (24/7 Autonomous Coordinator)

Хмарний автономний демон для координації баунті-кластера, моніторингу відкритих PR на $1060+ та управління Telegram-ботом [@Gankotepux_bot](https://t.me/Gankotepux_bot) без потреби тримати відкритим телефон або Termux.

---

## 🚀 1-Клік Деплой у Хмару

Обери будь-яку безкоштовну платформу для запуску:

### Варіант А: Render (Рекомендовано)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/gangkor/hermes-cloud-daemon)

1. Натисни кнопку **Deploy to Render** вище.
2. Підключи свій GitHub акаунт.
3. У формі оточення заповни або залиш дефолтні значення (токен бота та Chat ID уже прописані).
4. Натисни **Apply**. Сервер підніметься автоматично за 1 хвилину.

---

### Варіант Б: Koyeb (Безкоштовно без кредитки)
1. Зареєструйся на [koyeb.com](https://app.koyeb.com/).
2. Створи новий сервіс -> **GitHub**.
3. Обери репозиторій `gangkor/hermes-cloud-daemon`.
4. Обери тип: **Worker** (або Web Service з портом 8080).
5. Додай змінні середовища з файлу `.env.example`.
6. Натисни **Deploy**.

---

### Варіант В: Запуск через Docker
```bash
git clone https://github.com/gangkor/hermes-cloud-daemon.git
cd hermes-cloud-daemon
cp .env.example .env
# Заповни змінні в .env
docker build -t hermes-cloud .
docker run -d --restart unless-stopped --name hermes-daemon hermes-cloud
```

---

## ⚡ Що робить цей демон у хмарі:

1. **Telegram-бот (@Gankotepux_bot):**
   - `/status` — Перевіряє всі 12 PR у реальному часі ($1060+ нагород) і показує їхній статус.
   - `/check` — Негайне опитування всіх репозиторіїв.
   - `/dispatch` — Запуск скаутингу нових баунті у всіх 4 воркерів у GitHub Actions.
   - `/wallets` — Перегляд адрес Solana для виплат.
   - `/ping` — Перевірка зв'язку.

2. **Автономний фоновий планувальник (кожні 15 хвилин):**
   - Перевіряє статус відкритих PR на GitHub.
   - Якщо PR замерджено -> надсилає пуш: `🚨 УВАГА! Баунті замерджено! Перевір баланс!`.
   - Якщо PR закрито -> інформує та звільняє слот.
   - Перевіряє GitHub Actions раннери 4 акаунтів (`gangkor`, `Danko145`, `danko5443-rgb`, `danopef-eng`) і перезапускає їх через `workflow_dispatch`, якщо вони простоюють більше 3 годин.
