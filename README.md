# SpendWise 💰

A smart expense tracker with a built-in **subscription audit** — not just another expense logger. SpendWise flags recurring subscriptions you haven't reviewed in 60+ days, so you catch the "forgotten Netflix plan" problem before it drains your budget.

## Features
- User authentication (signup/login/logout)
- Add, view, delete expenses with custom categories
- Mark expenses as recurring (weekly/monthly/yearly)
- Dashboard with spend-by-category (pie chart) and 6-month trend (line chart)
- Budget limits per category with visual alerts when you're close to or over budget
- **Subscription Audit** page — flags recurring expenses unreviewed in 60+ days, shows total monthly "subscription burden"
- CSV export of all expenses

## Design
SpendWise uses a "ledger" visual identity — a dark ink sidebar (like a ledger book spine) with a brass accent, and every currency figure rendered in tabular monospace (JetBrains Mono) so amounts align like a real financial statement. Category status uses semantic color: emerald (healthy), amber (approaching budget), brick red (over budget).

## Tech Stack
- Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF
- SQLite (dev database)
- Jinja2 templates + vanilla CSS, Space Grotesk / Inter / JetBrains Mono typefaces
- Chart.js (via CDN) for charts

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
python run.py
```

Visit `http://127.0.0.1:5000` in your browser. The database (`spendwise.db`) is created automatically on first run.

## Project Structure

```
spendwise/
├── app/
│   ├── __init__.py         # App factory
│   ├── models.py           # User, Category, Expense models
│   ├── routes/
│   │   ├── auth.py         # Signup / login / logout
│   │   ├── expenses.py     # Expense & category CRUD
│   │   └── dashboard.py    # Dashboard, subscription audit, CSV export
│   ├── templates/          # Jinja2 HTML templates
│   └── static/css/         # Stylesheet
├── config.py
├── run.py
└── requirements.txt
```

## Suggested Next Steps (Roadmap)
- [ ] Auto-generate future recurring expense entries (e.g. with Flask-APScheduler)
- [ ] Email reminders before a subscription renews
- [ ] Password reset flow
- [ ] Multi-currency support
- [ ] Deploy to Render/Railway with PostgreSQL

## Why This Project Is Different
Most student expense trackers just log spending. SpendWise's **subscription audit** view is the differentiator — it actively surfaces recurring payments you might have forgotten about, turning passive tracking into an actionable nudge. It's a small feature with real behavioral value, which makes for a much better portfolio talking point than "I built a CRUD app."
