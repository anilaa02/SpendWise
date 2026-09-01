from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


CURRENCY_MAP = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CAD": "CA$",
    "AUD": "A$",
}


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    currency = db.Column(db.String(10), default="INR", nullable=False)

    categories = db.relationship("Category", backref="user", lazy=True, cascade="all, delete-orphan")
    expenses = db.relationship("Expense", backref="user", lazy=True, cascade="all, delete-orphan")
    incomes = db.relationship("Income", backref="user", lazy=True, cascade="all, delete-orphan")
    savings_goals = db.relationship("SavingsGoal", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def currency_symbol(self):
        return CURRENCY_MAP.get(self.currency, "₹")

    def current_month_income(self, year=None, month=None):
        today = date.today()
        target_year = year or today.year
        target_month = month or today.month
        return sum(
            inc.amount
            for inc in self.incomes
            if inc.date.year == target_year and inc.date.month == target_month
        )

    def current_month_expense(self, year=None, month=None):
        today = date.today()
        target_year = year or today.year
        target_month = month or today.month
        return sum(
            e.amount
            for e in self.expenses
            if e.date.year == target_year and e.date.month == target_month
        )


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    monthly_budget = db.Column(db.Float, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    expenses = db.relationship("Expense", backref="category", lazy=True, cascade="all, delete-orphan")

    def current_month_spent(self, year=None, month=None):
        today = date.today()
        target_year = year or today.year
        target_month = month or today.month
        return sum(
            e.amount
            for e in self.expenses
            if e.date.year == target_year and e.date.month == target_month
        )

    def budget_progress(self, year=None, month=None):
        """Returns (spent, budget, percentage, status_level)"""
        spent = self.current_month_spent(year, month)
        if not self.monthly_budget or self.monthly_budget <= 0:
            return spent, 0.0, 0.0, "none"
        pct = (spent / self.monthly_budget) * 100.0
        if pct >= 100:
            level = "over"
        elif pct >= 90:
            level = "danger"
        elif pct >= 75:
            level = "warning"
        elif pct >= 50:
            level = "notice"
        else:
            level = "ok"
        return spent, self.monthly_budget, pct, level


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(255), nullable=True)
    date = db.Column(db.Date, nullable=False, default=date.today)

    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_period = db.Column(db.String(20), nullable=True)  # weekly / monthly / yearly
    status = db.Column(db.String(20), default="active", nullable=False)  # active / paused / cancelled
    last_reviewed_date = db.Column(db.Date, nullable=True)
    payment_method = db.Column(db.String(50), default="UPI / Online", nullable=False)
    is_anomaly = db.Column(db.Boolean, default=False, nullable=False)
    anomaly_reason = db.Column(db.String(255), nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"), nullable=False)

    def needs_review(self):
        """Flag active subscriptions not reviewed in 60+ days."""
        if not self.is_recurring or self.status != "active":
            return False
        check_date = self.last_reviewed_date or self.date
        return (date.today() - check_date).days >= 60

    @property
    def monthly_equivalent(self):
        if not self.is_recurring:
            return 0.0
        if self.recurrence_period == "monthly":
            return self.amount
        if self.recurrence_period == "yearly":
            return self.amount / 12.0
        if self.recurrence_period == "weekly":
            return self.amount * 4.33
        return 0.0

    @property
    def annual_equivalent(self):
        if not self.is_recurring:
            return 0.0
        if self.recurrence_period == "monthly":
            return self.amount * 12.0
        if self.recurrence_period == "yearly":
            return self.amount
        if self.recurrence_period == "weekly":
            return self.amount * 52.0
        return 0.0

    def next_renewal_date(self):
        """Calculates the upcoming renewal date from the original transaction date."""
        if not self.is_recurring or self.status != "active":
            return None
        today = date.today()
        current = self.date

        if self.recurrence_period == "weekly":
            while current <= today:
                current += timedelta(days=7)
            return current
        elif self.recurrence_period == "monthly":
            while current <= today:
                current += relativedelta(months=1)
            return current
        elif self.recurrence_period == "yearly":
            while current <= today:
                current += relativedelta(years=1)
            return current
        return None


class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(100), nullable=False)  # Salary, Freelance, Business, Investment, Gift, Other
    date = db.Column(db.Date, nullable=False, default=date.today)
    note = db.Column(db.String(255), nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


class SavingsGoal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0, nullable=False)
    target_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="in_progress", nullable=False)  # in_progress, completed, cancelled
    created_at = db.Column(db.Date, default=date.today, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    contributions = db.relationship("GoalContribution", backref="goal", lazy=True, cascade="all, delete-orphan")

    @property
    def progress_pct(self):
        if self.target_amount <= 0:
            return 0.0
        return min(100.0, (self.current_amount / self.target_amount) * 100.0)

    @property
    def remaining_amount(self):
        return max(0.0, self.target_amount - self.current_amount)

    @property
    def is_completed(self):
        return self.current_amount >= self.target_amount or self.status == "completed"

    @property
    def is_overdue(self):
        if not self.target_date or self.is_completed:
            return False
        return self.target_date < date.today()

    @property
    def required_monthly_savings(self):
        """Calculates approximate monthly savings required to hit target date."""
        if self.is_completed or self.remaining_amount <= 0:
            return 0.0
        if not self.target_date:
            return None
        today = date.today()
        if self.target_date <= today:
            return self.remaining_amount
        
        # Calculate months remaining
        months_left = (self.target_date.year - today.year) * 12 + (self.target_date.month - today.month)
        if self.target_date.day < today.day:
            months_left -= 1
        months_left = max(1, months_left)
        return self.remaining_amount / months_left


class GoalContribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    note = db.Column(db.String(255), nullable=True)

    goal_id = db.Column(db.Integer, db.ForeignKey("savings_goal.id"), nullable=False)


