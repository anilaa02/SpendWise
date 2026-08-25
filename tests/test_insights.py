import unittest
from datetime import date
from app import create_app, db
from app.models import User, Category, Expense
from app.insights import generate_insights
from config import TestConfig


class InsightsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(name="Insight User", email="insight@example.com", currency="USD")
        self.user.set_password("pass123")
        db.session.add(self.user)
        db.session.commit()

        self.cat_groceries = Category(name="Groceries", monthly_budget=500.0, user_id=self.user.id)
        self.cat_dining = Category(name="Dining", monthly_budget=300.0, user_id=self.user.id)
        db.session.add_all([self.cat_groceries, self.cat_dining])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_empty_insights_fallback(self):
        insights = generate_insights(self.user.id)
        self.assertGreater(len(insights), 0)
        self.assertIn("Not enough spending history", insights[0]["text"])

    def test_currency_symbol_in_insights(self):
        today = date.today()
        # Add expense
        e = Expense(
            amount=200.0,
            note="Supermarket",
            date=today,
            user_id=self.user.id,
            category_id=self.cat_groceries.id,
        )
        db.session.add(e)
        db.session.commit()

        insights = generate_insights(self.user.id)
        # Verify dollar sign '$' is used since user.currency == "USD"
        found_dollar = any("$" in i["text"] for i in insights)
        self.assertTrue(found_dollar)

    def test_single_transaction_spike_detection(self):
        today = date.today()
        # Typical grocery transactions: $50, $40, $60
        e1 = Expense(amount=50.0, note="Milk and bread", date=today, user_id=self.user.id, category_id=self.cat_groceries.id)
        e2 = Expense(amount=40.0, note="Produce", date=today, user_id=self.user.id, category_id=self.cat_groceries.id)
        e3 = Expense(amount=60.0, note="Pantry staples", date=today, user_id=self.user.id, category_id=self.cat_groceries.id)
        # Giant spike: $450
        e4 = Expense(amount=450.0, note="Luxury Gourmet Basket", date=today, user_id=self.user.id, category_id=self.cat_groceries.id)
        db.session.add_all([e1, e2, e3, e4])
        db.session.commit()

        insights = generate_insights(self.user.id)
        spike_insight = any("Unusual spend detected" in i["text"] for i in insights)
        self.assertTrue(spike_insight)


if __name__ == "__main__":
    unittest.main()
