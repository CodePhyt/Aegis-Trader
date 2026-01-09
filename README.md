# 🛡️ Aegis-Trader: Autonomous MoonBag Liquidity Engine

> **"Capital Preservation Through Algorithmic Rigor."**

Aegis-Trader (formerly Project Predator) is an institutional-grade, local-first trading system designed validly for the "MoonBag" strategy. It utilizes millisecond-latency processing to secure principal investments and protect pure-profit positions.

---

## ⚡ Principal Protection Algorithm

The core mandate of Aegis-Trader is to **eliminate risk** at the earliest mathematical opportunity.

### The "Free Roll" Logic
When a position doubles in value (`200% ROI`), the system executes a **Principal Recovery Event**:
1.  **Breakeven Calculation**: It calculates the exact amount to sell to recover `Initial Investment + Trading Fees`.
2.  **Liquidity Extraction**: It uses `core/executor.py` to check Order Book depth. If the sell order would cause >0.5% slippage, it splits the order into smaller "Iceberg" chunks (TWAP-lite).
3.  **Result**: The user retains ~50% of the tokens with a **Cost Basis of $0.00**.

### Trailing MoonBags
The remaining tokens ("MoonBag") are immediately wrapped in a **Hedged Trailing Stop** (default 5%).
- **If Price Rises**: The stop-loss follows the price up (ratchet mechanism).
- **If Price Dumps**: The system exits instantly, securing the "Free Roll" profit.

---

## ⚙️ Tech Highlights

- **Speed**: Built on **Python 3.11 AsyncIO** for non-blocking concurrency.
- **Latency**: **WebSockets** (via CCXT Pro/Polling Watchdog) ensure price data is roughly real-time.
- **Privacy**: **SQLite** database stores all trade history and portfolio state locally. No external cloud dependencies.
- **Reliability**: **Docker** containerization ensures identical performance on any VPS.

---

## 🖥️ The Portal (Command Center)

Aegis-Trader includes a self-hosted **Streamlit** dashboard for real-time monitoring.

- **Live Grid**: Visualize entry prices vs. 2x targets.
- **Heatmap**: Green = MoonBag Secured, Red = Active Risk.
- **Logs**: Real-time trail of the algorithmic decision engine.

---

## 🛠️ Installation Guide

### 1. Clone & Configure
```bash
git clone https://github.com/CodePhyt/Aegis-Trader.git
cd aegis-trader
cp .env.example .env
# Edit .env with your Exchange API Keys (Keep them SAFE!)
```

### 2. Deployment (Docker)
We provide a production-ready `docker-compose.yml` for one-click deployment.

```bash
docker-compose up -d
```
This launches:
- `predator-backend`: The trading engine.
- `predator-portal`: The UI (accessible at `http://localhost:8501`).

### 3. Deployment (Manual)
```bash
# Backend
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
python bot_brain.py

# Portal (New Terminal)
streamlit run portal.py
```

---

## 🔐 Security Notice

- **API Keys**: Your keys are stored **ONLY** in the local `.env` file. They are never sent to any third-party server.
- **Execution Safety**: The bot includes a **Volatility Guard**. If 1-minute volatility exceeds 10% (fake pump), the bot delays execution to avoid selling into a wick.

---

## ⚠️ Disclaimer

**Not Financial Advice.**
*Cryptocurrency trading involves high risk. This software is an automation tool provided "as is" under the MIT License. The developers are not responsible for any financial losses.*
