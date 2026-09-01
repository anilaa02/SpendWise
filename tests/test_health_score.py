import unittest
from datetime import date
from app import create_app, db
from app.models import User, Category, Expense, Income, SavingsGoal
from app.health_score import calculate_financial_health
from config import TestConfig


class HealthScoreTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(name="Health Tester", email="health@example.com", currency="USD")
        self.user.set_password("pass123")
        db.session.add(self.user)
        db.session.commit()

        self.cat = Category(name="Groceries", monthly_budget=1000.0, user_id=self.user.id)
        db.session.add(self.cat)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_excellent_health_profile(self):
        today = date.today()
        # High income: $5000
        inc = Income(amount=5000.0, source="Salary", date=today, user_id=self.user.id)
        # Moderate expense: $800
        exp = Expense(amount=800.0, note="Food", date=today, user_id=self.user.id, category_id=self.cat.id)
        # Active goal:
        goal = SavingsGoal(name="House Downpayment", target_amount=20000.0, current_amount=5000.0, user_id=self.user.id)
        db.session.add_all([inc, exp, goal])
        db.session.commit()

        health = calculate_financial_health(self.user.id)
        self.assertGreaterEqual(health["score"], 80)
        self.assertIn(health["grade"], ["Good", "Excellent"])
        self.assertGreater(len(health["strengths"]), 0)
        self.assertIn("budget", health["pillar_scores"])
        self.assertIn("savings", health["pillar_scores"])

    def test_overspending_health_profile(self):
        today = date.today()
        # Income: $1000
        inc = Income(amount=1000.0, source="Salary", date=today, user_id=self.user.id)
        # Expenses: $2500 (overspent budget $1000 and income $1000)
        exp = Expense(amount=2500.0, note="Big spend", date=today, user_id=self.user.id, category_id=self.cat.id)
        db.session.add_all([inc, exp])
        db.session.commit()

        health = calculate_financial_health(self.user.id)
        self.assertLess(health["score"], 65)
        self.assertGreater(len(health["recommendations"]), 0)


if __name__ == "__main__":
    unittest.main()
