# SpendWise 💰

A smart expense tracker and subscription telemetry system — built with Flask, SQLAlchemy, and a ledger-inspired visual design. SpendWise flags recurring subscriptions you haven't reviewed in 60+ days, forecasts upcoming renewal cycles, and gives you complete control over your budget.

---

## ✨ Features

### 1. Expense & Ledger Management (Full CRUD)
- **Record & Edit Transactions**: Full update modal for amounts, dates, notes, categories, and recurring statuses.
- **Category & Budget Control**: Set, adjust, or remove monthly category limits with real-time budget progress bars.
- **Bulk CSV Import**: Upload bank statements or expense sheets via CSV with automated category creation and sample templates.
- **Filter & Search**: Query by category, date range, amount thresholds, recurrence type, or note keywords.
- **Multi-Format Export**: Export your entire ledger or filtered views as **CSV** or **JSON**.

### 2. Proactive Subscription Audit & Control
- **60-Day Stale Subscription Detection**: Surfaces forgotten recurring services with 1-click "Keep & Verify" confirmation.
- **Lifecycle Statuses**: Mark subscriptions as **Active**, **Paused**, or **Cancelled**.
- **1-Click Renewal Logger**: Log current cycle renewals directly into your expense ledger in one tap.
- **Renewal Forecast Schedule**: 30-day timeline with urgent alerts for bills due within 7 days.
- **Annual & Monthly Burden**: Automatic translation of weekly, monthly, and yearly cadences into normalized monthly equivalents and annual cost projections.

### 3. Rule-Based Insights & Pacing Engine
- **Spending Velocity Alert**: Projects month-end spending based on current daily run-rate vs. total monthly budget.
- **Spending Spike Detection**: Flags individual purchases exceeding 2.5x the typical category transaction size.
- **Subscription Creep Indicator**: Warns when recurring commitments exceed 30% of total monthly spending.
- **Month-over-Month Comparisons**: Analyzes shifts across categories with exact percentage deltas.

### 4. Customization & Security
- **Multi-Currency Engine**: Switch seamlessly between **INR (₹)**, **USD ($)**, **EUR (€)**, **GBP (£)**, **JPY (¥)**, **CAD (CA$)**, and **AUD (A$)**.
- **CSRF Protection**: Hardened forms protected against Cross-Site Request Forgery via `Flask-WTF`.
- **Responsive Ledger UI**: Mobile navigation drawer, semantic color coding (Emerald, Amber, Brick Red), and tabular monospace formatting (`JetBrains Mono`).

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, Flask 3.0.3, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Werkzeug
- **Database**: SQLite (local development) / PostgreSQL ready
- **Frontend**: Jinja2 templates, Custom Ledger CSS system, Chart.js (CDN)
- **Testing**: Python `unittest` suite (17 automated tests)

---

## ⚡ Quick Start

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run automated tests
python -m unittest discover -s tests -p "test_*.py" -v

# 4. Run the app
python run.py
```

Visit `http://127.0.0.1:5000` in your browser. The database (`spendwise.db`) is initialized automatically.

---

## 📂 Project Structure

```
SpendWise/
├── app/
│   ├── __init__.py           # App factory & CSRF/currency context injection
│   ├── models.py             # User, Category, Expense models & renewal logic
│   ├── insights.py           # Rule-based spending analytics engine
│   ├── routes/
│   │   ├── auth.py           # Signup, login, logout, starter categories seeding
│   │   ├── expenses.py       # Full CRUD, category manager, CSV bulk import
│   │   └── dashboard.py      # Analytics, renewal alerts, preferences, JSON export
│   ├── templates/            # Jinja2 HTML templates
│   │   ├── auth/             # Login & Signup pages
│   │   ├── base.html         # Master ledger layout, mobile drawer, preferences modal
│   │   ├── dashboard.html    # Progress bars, renewal pills, Chart.js graphs
│   │   ├── expenses.html     # CRUD ledger, edit modals, bulk CSV upload
│   │   └── subscriptions.html# Subscription audit, 1-click renewal, timeline
│   └── static/css/style.css  # Responsive ledger design system
├── tests/                    # Automated test suite
│   ├── test_auth.py          # Authentication tests
│   ├── test_expenses.py      # CRUD, CSV import/export tests
│   ├── test_subscriptions.py # Stale detection, renewals, forecast tests
│   └── test_insights.py      # Velocity, spike, and currency tests
├── config.py                 # Configuration & TestConfig
├── run.py                    # Entry point script
├── requirements.txt          # Python dependencies
└── README.md
```

