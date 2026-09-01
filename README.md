# SpendWise 💰 — Intelligent Personal Finance Platform

SpendWise is a full-featured, intelligent personal finance and expense management platform built with Python, Flask, and SQLAlchemy. Featuring a distinctive "ledger" visual identity, SpendWise goes beyond passive expense tracking with proactive subscription audit telemetry, machine-learning-powered expense categorization, statistical spending anomaly detection, savings goal pacing, and a transparent Financial Health Score.

---

## 🏛️ Architecture Overview

```
                          ┌──────────────────────────┐
                          │   User / Web Browser     │
                          └────────────┬─────────────┘
                                       │ HTTPS / Form POST / AJAX
                                       ▼
                          ┌──────────────────────────┐
                          │  Jinja2 + Ledger CSS UI  │
                          │  Chart.js Visualizations │
                          └────────────┬─────────────┘
                                       │
                                       ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                           Flask Application Layer                              │
├─────────────────┬─────────────────┬─────────────────┬──────────────────────────┤
│  Auth Blueprint │ Expense & Ledger│ Income & Goals  │ Dashboard & Analytics    │
│  (Session/CSRF) │ (CRUD/CSV 2-Step│ (Pacing Engine) │ (Telemetry/Export)       │
└────────┬────────┴────────┬────────┴────────┬────────┴────────────┬─────────────┘
         │                 │                 │                     │
         ▼                 ▼                 ▼                     ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                    Intelligent Business & ML Engines Layer                     │
├──────────────────────┬──────────────────────┬──────────────────────────────────┤
│ ML Category Engine   │ Anomaly Detection    │ Financial Health Score & Insights│
│ (TF-IDF + NaiveBayes)│ (IQR + Z-Score Stat) │ (Transparent 6-Pillar Diagnostic)│
└──────────────────────┴──────────┬───────────┴──────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                   SQLAlchemy ORM Data Persistence Layer                        │
├────────────────────────────────────────────────────────────────────────────────┤
│  User  │  Category  │  Expense  │  Income  │  SavingsGoal  │  GoalContribution │
└─────────────────────────────────┬──────────────────────────────────────────────┘
                                  │
                                  ▼
                   ┌──────────────────────────────┐
                   │ SQLite (Dev) / PostgreSQL    │
                   └──────────────────────────────┘
```

---

## ✨ Core Features

### 1. 📊 Intelligent Financial Dashboard
* **Real-Time Cashflow KPIs**: Track current-month Total Income, Total Expenses, Net Savings Balance, Savings Rate (%), and Budget Utilization.
* **Month-over-Month Delta**: Visual percentage shift vs. previous month.
* **SpendWise Insights**: Real data-driven observations covering spending velocity, budget pace projections, category shifts, and renewal notices.
* **Recent Ledger Slip**: Quick receipt modal, transaction duplication to today, edit, and deletion.

### 2. ⚡ ML-Based Expense Categorization
* **Real-Time Prediction**: Utilizes TF-IDF vectorization and Multinomial Naive Bayes classifier trained on personal finance descriptions (Swiggy, Uber, Netflix, Whole Foods, etc.).
* **Confidence Scoring**: Returns predicted category name and confidence percentage (e.g. *"Food & Dining — 94% confidence"*).
* **Manual Override**: Automatically selects category in the form while allowing full manual override by the user.

### 3. 🛡️ Statistical Spending Anomaly Detection
* **IQR & Z-Score Analysis**: Evaluates historical category spending distributions to flag unusually large transactions.
* **Noise Floor Filtering**: Avoids false alarms on small normal variations.
* **Dynamic Warning Badges**: Highlights transactions exceeding category normal bounds with explainable reasoning (e.g. *"Transaction is 4.5x your typical ₹150–₹450 range"*).

### 4. 🎯 Savings Goals & Monthly Target Pacing
* **Financial Goal Milestones**: Set target amounts, current saved balances, and target dates.
* **Automated Monthly Calculator**: Automatically calculates required monthly savings (e.g. *"Save ₹5,380/month to hit target by March 2027"*).
* **Progress Tracking**: Visual color-coded progress bars, milestone celebrations, and overdue goal detection.
* **Direct Deposits**: 1-click contribution logging toward active goals.

### 5. 🔁 Subscription Telemetry & Proactive Audit
* **60-Day Inactive Audit**: Flags recurring subscriptions not reviewed in over 60 days to prevent subscription creep.
* **30-Day Renewal Schedule**: Timeline projection with urgent alerts for bills due within 7 days.
* **1-Click Renewal Logger**: Log current cycle renewals directly into the ledger in one tap.
* **Lifecycle Statuses**: Mark subscriptions as **Active**, **Paused**, or **Cancelled**.

### 6. 🩺 Transparent Financial Health Score (0–100)
* **6-Pillar Diagnostic**: Evaluates Budget Adherence (25 pts), Savings Rate (20 pts), Cashflow Ratio (20 pts), Subscription Burden (15 pts), Spending Stability (10 pts), and Goals Momentum (10 pts).
* **Itemized Feedback**: Itemized list of key strengths and actionable financial recommendations.

### 7. 📥 2-Step CSV Import & Multi-Format Export
* **Validation & Preview Workflow**: Inspects uploaded CSV files, detects valid rows, flags duplicate transactions, highlights invalid/negative rows, and lets user review before committing.
* **Downloadable Template**: Built-in template generator (`/expenses/sample-csv`).
* **Multi-Format Export**: Export ledger views as **CSV** or **JSON**.

### 8. 🌐 Multi-Currency & Responsive Ledger Design
* **Multi-Currency Engine**: Seamlessly switch between **INR (₹)**, **USD ($)**, **EUR (€)**, **GBP (£)**, **JPY (¥)**, **CAD (CA$)**, and **AUD (A$)**.
* **Ledger Design Language**: Paper-and-ink aesthetics, monospace financial figures (`JetBrains Mono`), semantic alert colors, and mobile navigation drawer.

---

## 🛠️ Tech Stack

* **Backend**: Python 3.10+, Flask 3.0.3, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Werkzeug
* **Machine Learning & Analytics**: scikit-learn, NumPy, pandas, python-dateutil
* **Database**: SQLite (development) / PostgreSQL (production ready)
* **Frontend**: Jinja2 Templates, Custom Ledger CSS Design System, Chart.js (CDN)
* **Testing**: Python `unittest` suite (40 automated tests)

---

## ⚡ Quick Start & Installation

```bash
# 1. Clone the repository
git clone https://github.com/anilaa02/SpendWise.git
cd SpendWise

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the automated test suite (40 tests)
python -m unittest discover -s tests -p "test_*.py" -v

# 5. Start the application
python run.py
```

Open **`http://127.0.0.1:5000`** in your browser. The SQLite database is created and auto-migrated on first launch.

---

## 📂 Project Structure

```
SpendWise/
├── app/
│   ├── __init__.py           # App factory, CSRF, error handlers, DB auto-migration
│   ├── models.py             # User, Category, Expense, Income, SavingsGoal models
│   ├── ml.py                 # ML TF-IDF + Naive Bayes category prediction engine
│   ├── anomaly.py            # Statistical IQR/Z-score spending anomaly engine
│   ├── health_score.py       # Transparent 0-100 financial health score calculator
│   ├── insights.py           # Real user-data rule-based insights engine
│   ├── routes/
│   │   ├── auth.py           # User authentication & starter categories
│   │   ├── expenses.py       # Full CRUD, 2-step CSV import, duplicates, duplicate action
│   │   ├── income.py         # Income management & earnings categorization
│   │   ├── goals.py          # Savings goals, contributions & monthly pacing
│   │   ├── dashboard.py      # Main dashboard, subscriptions, preferences, export
│   │   ├── analytics.py      # Chart.js analytics & financial health breakdown
│   │   └── api.py            # Async endpoints for ML prediction & anomaly checks
│   ├── templates/            # Jinja2 templates
│   │   ├── auth/             # Login & Signup pages
│   │   ├── errors/           # 400, 403, 404, 500 error pages
│   │   ├── expenses/         # CSV validation preview template
│   │   ├── base.html         # Master ledger layout, sidebar & mobile drawer
│   │   ├── dashboard.html    # Financial KPIs, health banner, recent ledger
│   │   ├── income.html       # Income ledger & source management
│   │   ├── goals.html        # Savings goals cards & progress visualizers
│   │   ├── expenses.html     # Expenses table, ML autofill, category manager
│   │   ├── subscriptions.html# 60-day audit, 1-click renewal, timeline
│   │   └── analytics.html    # Interactive Chart.js graphs & diagnostics
│   └── static/css/style.css  # Responsive ledger styling system
├── tests/                    # 40 automated tests
│   ├── test_auth.py          # Authentication tests
│   ├── test_expenses.py      # CRUD, duplicate, 2-step CSV import tests
│   ├── test_income.py        # Income CRUD & month total calculations
│   ├── test_goals.py         # Savings goals, pacing, contributions tests
│   ├── test_ml.py            # ML category prediction & confidence tests
│   ├── test_anomaly.py       # Statistical anomaly detection tests
│   ├── test_health_score.py  # Financial health scoring profile tests
│   ├── test_security.py      # User data isolation & error handling tests
│   ├── test_subscriptions.py # Stale detection & 1-click renewal tests
│   └── test_insights.py      # Spending pacing & insight generation tests
├── config.py                 # App configuration & TestConfig
├── run.py                    # Server entrypoint
├── requirements.txt          # Python package requirements
├── .gitignore                # Git ignore configuration
└── README.md
```

---

## 🧪 Testing

SpendWise includes an extensive automated test suite covering authentication, expense management, income, savings goals, ML predictions, statistical anomaly checks, financial health diagnostics, and security user-isolation.

Run all tests:
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 🚀 Future Roadmap

- [ ] Automated recurring expense cron processor (e.g. APScheduler).
- [ ] Email notifications for upcoming subscription renewals.
- [ ] Bank statement PDF parser integration.
- [ ] Multi-user family budget sharing with granular permissions.
