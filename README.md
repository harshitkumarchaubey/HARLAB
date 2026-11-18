# HARLAB — Quantitative Market Research Laboratory

**Understand Markets. Test Hypotheses. Discover Evidence.**

HARLAB is a computational research workstation for studying limit order books, market microstructure, liquidity, price formation, and execution dynamics through deterministic, reproducible experiments.

> **Important disclaimer:** HARLAB is an educational and quantitative research environment. Simulated order books and seeded datasets are **SYNTHETIC** and visibly labelled as such. HARLAB does not connect to live exchanges and makes no claims of real-world trading profitability.

---

## 1. Prerequisites (Windows & VS Code Beginner Setup)

If Python or Node.js are not yet installed on your Windows machine:

1. **Install Python 3.11+** from [python.org/downloads](https://www.python.org/downloads/). During installation, check **"Add python.exe to PATH"**.
2. **Install Node.js LTS (18+)** from [nodejs.org](https://nodejs.org/) (includes `npm`).
3. **Install VS Code** from [code.visualstudio.com](https://code.visualstudio.com/).

Verify both are available in VS Code (`Terminal → New Terminal`, PowerShell):
```powershell
python --version
node --version
npm --version
```

---

## 2. Extract & Set Up the Backend (Windows PowerShell)

```powershell
# 1. Extract HARLAB.zip and open the extracted HARLAB folder in VS Code.
# 2. Create and activate a Python virtual environment:
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# If PowerShell blocks script execution, run:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# .\.venv\Scripts\Activate.ps1

# 3. Install Python dependencies and the HARLAB package:
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

### Run the CLI Order-Book Demo
```powershell
python scripts/demo_order_book.py
```

### Start the FastAPI Backend Server
```powershell
uvicorn harlab.api.app:app --reload --host 127.0.0.1 --port 8000
```
Interactive OpenAPI docs are available at `http://127.0.0.1:8000/docs`.

---

## 3. Set Up & Run the Frontend (Second VS Code Terminal)

```powershell
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser. Vite proxies all `/api/*` requests to `http://127.0.0.1:8000`.

### Build Frontend for Production
```powershell
cd frontend
npm run build
```

---

## 4. Running Automated Tests

### Backend Tests (Unit, Regression, 1,500-Op Invariant Fuzz, AI Failover, FastAPI)
```powershell
# With pytest (recommended):
python -m pytest -v

# Or with Python's built-in unittest runner:
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```

### Frontend Tests (Vitest + Testing Library)
```powershell
cd frontend
npm test
```

---

## 5. Optional Three-Provider AI Configuration

HARLAB's deterministic quantitative engine works **100% offline without any AI keys**.
To enable the AI Research Assistant with automatic `Gemini → Groq → OpenRouter` failover:

1. Copy `.env.example` to `.env` in the `HARLAB/` root directory.
2. Add one or more keys (never commit `.env` to Git):
   ```env
   AI_PROVIDER_PRIORITY=gemini,groq,openrouter
   GEMINI_API_KEY=your_key_here
   GROQ_API_KEY=your_key_here
   OPENROUTER_API_KEY=your_key_here
   ```
3. Start `uvicorn` — HARLAB automatically loads `.env` from the project root without overwriting any variables already set in your shell (or you can export them manually in PowerShell):
   ```powershell
   Get-Content .env | ForEach-Object {
     if ($_ -match '^([^#=]+)=(.*)$') {
       [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
     }
   }
   uvicorn harlab.api.app:app --reload --host 127.0.0.1 --port 8000
   ```
API keys remain strictly on the backend and are never exposed to the browser or API status responses.

---

## 6. Architecture & Project Structure

```text
HARLAB/
├── src/harlab/
│   ├── market/        # Exact-tick OrderBook, MatchingEngine, 12 microstructure metrics
│   ├── simulation/    # Seeded reproducible synthetic LOB simulator + preset scenarios
│   ├── data/          # Validated DatasetRegistry, OHLCV CSV ingestion, DataProvider ABC
│   ├── research/      # Hypothesis registry, leakage-checked ExperimentRunner, JSON/CSV export
│   ├── execution/     # Causal signal rules & cost-aware backtester (fees + slippage)
│   ├── ml/            # Leakage-free train-fit volatility/liquidity regime classifier
│   ├── ai/            # Separate 3-provider failover router (Gemini, Groq, OpenRouter)
│   └── api/           # FastAPI backend (schemas, session state, REST endpoints)
├── frontend/          # React 18 + TypeScript + Vite institutional research terminal
├── tests/             # 30 automated backend unit, regression, invariant, AI, and API tests
├── docs/              # Baseline audit verification, methodology, design decisions, research log
├── scripts/           # CLI demonstration script
├── .env.example       # Environment variable template
├── pyproject.toml     # Python package configuration
└── requirements.txt   # Python dependencies
```

---

## 7. API Endpoints Summary

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/api/health` | System status, dataset/experiment counts, AI router status |
| `GET` | `/api/book/snapshot` | Bid/ask ladders, active orders, recent trades, all 12 metrics |
| `POST` | `/api/book/orders` | Submit & match a limit order (exact tick & quantity validation) |
| `DELETE` | `/api/book/orders/{id}` | Cancel an active resting order |
| `POST` | `/api/book/reset` | Reset order book (custom tick size, optional demo seed) |
| `GET` | `/api/simulation/scenarios` | List preset synthetic simulation scenarios |
| `POST` | `/api/simulation/run` | Run reproducible seeded simulation and register dataset |
| `GET` | `/api/datasets` | List validated datasets with `is_synthetic` and `has_order_book_depth` flags |
| `POST` | `/api/datasets/upload-ohlcv` | Validate and register historical OHLCV CSV data |
| `GET` | `/api/datasets/{id}/regimes` | Leakage-free out-of-sample volatility/liquidity regime counts |
| `GET` | `/api/research/hypotheses` | List structured research hypotheses |
| `POST` | `/api/research/experiments` | Run train/test + walk-forward + leakage-checked experiment |
| `GET` | `/api/research/experiments/{id}/export?fmt=json\|csv` | Export experiment results |
| `GET` | `/api/ai/status` | Safe provider priority, cooldown, and usage stats (no secrets) |
| `POST` | `/api/ai/assist` | Ask grounded research question via 3-provider failover router |

---

## 8. Known Limitations & Production Readiness

- **Not exchange-grade matching:** Single-threaded, in-memory limit orders only (no market/stop/iceberg orders, no auction phases, no self-trade prevention, no persistence across server restarts).
- **In-memory API state:** Datasets, orders, and experiments reset when the `uvicorn` process restarts; export important experiments via JSON/CSV.
- **No authentication / multi-user isolation:** Designed for local single-researcher workstation use (`127.0.0.1`), not public multi-tenant deployment.
- **No bundled live market feed or live AI keys:** External AI adapters are verified with unit-tested failover/backoff/cooldown stubs; live provider calls require your own `.env` keys.
- **Frontend lockfile note:** Built in an offline sandbox without npm registry access; run `cd frontend && npm install` on your machine to generate `package-lock.json` and run `npm test` / `npm run build`.
