# Atlas AI — Institutional Financial Intelligence Partner

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141.1-009688.svg)](https://fastapi.tiangolo.com/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-2CA5E0.svg)](https://core.telegram.org/bots)
[![LangChain](https://img.shields.io/badge/LangChain-1.3.14-0055FF.svg)](https://python.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.10-FF6F00.svg)](https://langchain-ai.github.io/langgraph/)
[![Supabase](https://img.shields.io/badge/Database-Supabase%20PostgreSQL-3ECF8E.svg)](https://supabase.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)

**Atlas AI** is an institutional-grade financial intelligence assistant and executive partner natively integrated with Telegram. Designed for investors, financial analysts, portfolio managers, and founders, Atlas synthesizes real-time market data, company filings, earnings transcripts, multi-modal documents, voice notes, and vision inputs into actionable, high-signal intelligence without fluff or synthetic hallucinations.

---

## 🌟 Key Features & Capabilities

### 📊 1. Real-Time Market Intelligence & Live Quotes
- **Instant Verified Stock Quotes**: Real-time stock prices, percentage changes, trading volume, 52-week highs/lows, trailing & forward P/E ratios, and market capitalizations via `Finnhub` and `Yahoo Finance`.
- **Global Index & Multi-Exchange Coverage**: Live performance tracking across major market indices (S&P 500, Nasdaq, Dow Jones, Russell 2000, VIX Fear Index) as well as international exchanges (e.g. Indian NSE/BSE `.NS`, `.BO`).
- **Analyst Targets & Consensus**: Fetches target price ranges, forward EPS, TTM revenue, profit margins, and consensus ratings (`BUY`, `HOLD`, `SELL`).

### 📈 2. Institutional Market Movement Analyzer
- **Evidence-Grounded Price Action Analysis**: Distinguishes strictly between **FACT** (Price/Volume), **EVIDENCE** (Verified Headlines), and **ANALYSIS** (Fundamental Causality vs Correlation).
- **Epistemic Discipline**: Explicitly avoids assuming causality without proven catalysts (e.g., confirmed earnings/regulatory filings) and refrains from inventing hallucinated technical support/resistance levels.
- **Strategic Context**: Synthesizes macro discount-rate dynamics, sector rotation trends, structural tailwinds, and volume momentum into concise executive intelligence.

### 🔍 3. Epistemic Deep Research Engine (Public, Private & Pre-IPO)
- **Universal Entity Research**: Evaluates public equities, pre-IPO unicorns, private companies, and emerging technology sectors.
- **Mandatory Epistemic Calibration**: Every factual claim is classified into strict confidence tiers:
  - `Known`: Verified from official public filings or SEC disclosures.
  - `Reported`: Stated by credible media (Bloomberg, Reuters, WSJ, FT) with dates.
  - `Estimated`: Based on analyst consensus or tender-offer pricing.
  - `Inferred`: Logical conclusions derived from available evidence.
  - `Unknown`: Insufficient public data (explicitly stated).
- **Private Valuation Transparency**: Clear transaction-based valuation tracking with explicit point-in-time caveats and missing context notes.

### ⚔️ 4. Multi-Company Side-by-Side Comparison Engine
- **Head-to-Head Analysis**: Automated comparative breakdowns between competing firms (e.g., `TSLA` vs `RIVN`, `MSFT` vs `GOOGL`, `NVDA` vs `AMD`).
- **Valuation & Delta Math**: Automatically computes market cap differences (absolute & percentage deltas) and compares valuation multiples (P/E ratios).
- **Business Divergence & Entity-Segregated News**: Separates headlines strictly by target entity to prevent cross-company headline attribution errors.

### 📄 5. Executive Document Intelligence & PDF Q&A
- **Conversational PDF Analysis**: Upload financial reports, earnings releases, 10-K filings, or term sheets up to 150,000+ characters.
- **Instant Executive Summaries**: Formats uploads into clean *Financial Highlights*, *Key Takeaway*, and *⚠️ Interpretation* blocks (highlighting unverified drivers and limitations).
- **Cross-Session Document Persistence**: Persists document context across chat sessions for ongoing follow-up Q&A.

### 🎙️ 6. Audio Intelligence & Voice Notes
- **Whisper Speech-to-Text**: Converts voice notes and audio clips directly into text using OpenAI's `whisper-1` model.
- **Seamless Conversational Routing**: Seamlessly routes voice transcriptions through the LangGraph multi-agent financial engine.

### 👁️ 7. Vision AI Chart & Document Analysis
- **Financial Visual Processing**: Analyzes charts, balance sheet tables, candlestick graphs, and document screenshots via GPT-4 Vision.
- **Exact Mathematical Extraction**: Calculates margin percentages, revenue growth rates, and key metrics directly from visual media.

### 🌅 8. Automated Intelligence Briefings & Schedulers
- **Curated Morning Briefings**: Automated APScheduler background engine fetches news across user watchlists, runs LLM deduplication and impact scoring (>60 score threshold), and sends a morning intelligence brief.
- **Evening Market Wrap**: Market close summaries covering S&P 500 and Nasdaq closing movements alongside tracked portfolio performance.

### 💼 9. Executive Productivity Integration
- **Inbox Search (`read_recent_emails`)**: Scans executive emails for action items, due diligence requests, trading window notices, and meeting prep context.
- **Calendar Management (`get_upcoming_meetings`, `schedule_meeting`)**: Inspects upcoming executive schedules and schedules new calendar events directly via conversation.

### 🧠 10. Dynamic Personalization & Memory
- **Conversational Onboarding**: Natural multi-step setup asking user role (e.g. Investor, Analyst, Founder), tracked watchlist, and briefing time preferences.
- **Persistent DB Storage**: Stores user profiles, watchlists, preferences, and long-term conversation history in Supabase PostgreSQL (`asyncpg`).

### 🔒 11. Private Access Security Gateway
- **Passcode Protection**: Configurable authorization gateway (`BOT_PASSWORD`) ensuring restricted private access for institutional deployments.

---

## 🛠️ Architecture & Tech Stack

```
                                 +------------------------+
                                 |  Telegram Application  |
                                 +-----------+------------+
                                             |
                                   (Webhooks / Polling)
                                             v
                                  +----------------------+
                                  |   FastAPI Backend    |
                                  +----------+-----------+
                                             |
                                   (LangGraph Agent)
                                             v
        +------------------------------------+------------------------------------+
        |                                    |                                    |
        v                                    v                                    v
+---------------+                   +-----------------+                  +-----------------+
|  Market Data  |                   |  Multimodal AI  |                  |    Database     |
| (Finnhub, YF) |                   | (GPT-4o, Vision)|                  | (Supabase Postgres)
+---------------+                   +-----------------+                  +-----------------+
```

- **Backend Framework**: Python 3.11+, FastAPI 0.141.1, Uvicorn 0.52.1
- **Bot & Scheduling**: `python-telegram-bot` v22.8, APScheduler 3.11.3
- **Agent Orchestration**: LangChain 1.3.14, LangGraph 1.2.10
- **AI Models**: OpenAI (`gpt-4o-mini`, `whisper-1`), Google Gemini (`gemini-2.0-flash`)
- **Market Data Feeds**: Finnhub API, Yahoo Finance (`yfinance`)
- **Database & Drivers**: Supabase PostgreSQL (`asyncpg`), Motor (`MongoDB` optional driver)
- **Document Processing**: `pypdf` v6.15.0

---

## 📁 Repository Structure

```
atlas-ai-hackathon/
├── app/
│   ├── agents/
│   │   ├── assistant.py          # Core LangGraph agent & system prompt definition
│   │   ├── comparison.py         # Multi-company comparative engine
│   │   ├── market_movement.py    # Price action & fundamental driver analyzer
│   │   ├── overview.py           # Deep company overview engine
│   │   ├── price_engine.py       # Stock price fetcher & formatting engine
│   │   ├── productivity.py       # Email & calendar integration tools
│   │   ├── research.py           # Epistemic deep research engine (public/private)
│   │   └── tools.py              # Financial tool definitions (Quotes, News, Earnings)
│   ├── services/
│   │   └── market_data.py        # Classified news & market data services
│   ├── bot.py                    # Telegram handlers (Text, PDF, Voice, Vision, Auth)
│   ├── config.py                 # Pydantic BaseSettings & environment loader
│   ├── database.py               # Supabase PostgreSQL asyncpg connection manager
│   ├── main.py                   # FastAPI web server & webhook route handler
│   ├── market_data.py            # Finnhub & YFinance market data router
│   ├── models.py                 # User profile & database models
│   ├── scheduler.py              # APScheduler daily briefing & market wrap jobs
│   └── services.py               # User CRUD operations & profile persistence
├── Dockerfile                    # Production Docker container image
├── docker-compose.yml            # Container orchestration manifest
├── Procfile                      # Web process definition for Heroku / Render
├── render.yaml                   # Render Blueprint deployment configuration
├── requirements.txt              # Dependency specifications
└── run_local.py                  # Local polling daemon & standalone bot runner
```

---

## 🚀 Getting Started & Local Setup

### 1. Prerequisites
- Python 3.11 or higher
- PostgreSQL database (or [Supabase](https://supabase.com/) project)
- Telegram Bot Token (obtained from [@BotFather](https://t.me/BotFather))

### 2. Environment Configuration
Clone the repository and create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Configure your environment variables in `.env`:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.aicredits.in/v1
MODEL_NAME=gpt-4o-mini
GEMINI_API_KEY=your_gemini_api_key_here
FINNHUB_API_KEY=your_finnhub_api_key_here
POSTGRES_URI=postgresql://postgres:password@db.supabase.co:5432/postgres
BOT_PASSWORD=Atlas2024
PORT=8000
```

### 3. Installation
Create a virtual environment and install the required dependencies:

```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Running Locally

#### Option A: Local Telegram Polling Daemon (Recommended for Development)
```bash
python run_local.py
```

#### Option B: FastAPI Server with Webhooks
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🐳 Deployment Guide

### Running with Docker

Build and run using Docker Compose:

```bash
docker-compose up --build -d
```

### Deploying on Render / Cloud Hosting

The repository includes a ready-to-use [`render.yaml`](file:///d:/atlas_ai/render.yaml) Blueprint:

1. Connect your repository on Render.
2. Render will automatically detect `render.yaml` and provision the FastAPI web service.
3. Configure the environment variables (`TELEGRAM_BOT_TOKEN`, `POSTGRES_URI`, `OPENAI_API_KEY`, `WEBHOOK_URL`, etc.).
4. The server will launch `uvicorn app.main:app` and automatically register the Telegram webhook on startup.

---

## 🔒 Security & Best Practices

- **Strict Authorization**: Unauthenticated users must submit the correct `BOT_PASSWORD` before accessing financial tools.
- **Sanitized Connections**: PostgreSQL URI connection strings are automatically sanitized and URL-encoded for special characters.
- **Evidence Rules**: System prompts enforce strict ground-truth principles—never fabricating numbers or assuming causality without verified sources.

---

## 📄 License

This project is licensed under the MIT License.
