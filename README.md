# Crypto Scanner + Grafana Dashboard

This repository contains a fully containerized crypto scanning system that detects **surge, RSI, MACD, Golden Cross** signals for top USDT pairs, sends **Telegram alerts**, saves data to **Postgres**, and visualizes performance in **Grafana**.

---

## Features
- Top 100 USDT pairs auto-detection
- Indicators: Golden Cross, RSI, MACD
- Hourly surge detection
- Candlestick chart snapshots to Telegram
- Postgres logging with future 6h/24h returns
- Grafana dashboard for live monitoring

---

## Prerequisites
- Docker & Docker Compose installed
- Telegram bot token & chat ID

---

## Setup Instructions

### 1. Clone Repo
```bash
git clone https://github.com/YOUR_USERNAME/crypto-scanner.git
cd crypto-scanner
```

### 2. Configure Environment Variables
Create `.env` file inside `scanner/` folder (or use Docker env):
```
DB_HOST=postgres
DB_NAME=crypto_db
DB_USER=crypto_user
DB_PASS=crypto_pass
TELEGRAM_TOKEN=YOUR_BOT_TOKEN
CHAT_ID=YOUR_CHAT_ID
THRESHOLD=3.0
```

### 3. Run Docker Stack
```bash
docker-compose up -d
```

- **Postgres** → stores signals
- **Grafana** → `http://localhost:3000` (admin/admin)
- **Scanner** → runs continuously, sends alerts, updates DB

### 4. Import Grafana Dashboard
- Use `crypto_signals_dashboard.json` (from repo or generated)
- Select Postgres data source in Grafana

### 5. Monitor & Analyze
- Grafana auto-refresh: 5 min
- Scanner updates 6h/24h future returns
- Telegram receives charts & alerts
