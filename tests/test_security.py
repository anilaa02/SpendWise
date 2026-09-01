import unittest
from datetime import date
from app import create_app, db
from app.models import User, Category, Expense, Income, SavingsGoal
from config import TestConfig


class SecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # User A (Alice)
        self.user_a = User(name="Alice", email="alice@example.com")
        self.user_a.set_password("alicepass")

        # User B (Bob)
        self.user_b = User(name="Bob", email="bob@example.com")
        self.user_b.set_password("bobpass")

        db.session.add_all([self.user_a, self.user_b])
        db.session.commit()

        # Bob's private data
        self.cat_b = Category(name="Bob Secret Cat", monthly_budget=5000.0, user_id=self.user_b.id)
        db.session.add(self.cat_b)
        db.session.commit()

        self.exp_b = Expense(amount=1200.0, note="Bob Private Expense", date=date.today(), user_id=self.user_b.id, category_id=self.cat_b.id)
        self.inc_b = Income(amount=50000.0, source="Bob Salary", date=date.today(), user_id=self.user_b.id)
        self.goal_b = SavingsGoal(name="Bob Goal", target_amount=100000.0, user_id=self.user_b.id)
        db.session.add_all([self.exp_b, self.inc_b, self.goal_b])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_unauthenticated_access_redirects(self):
        endpoints = ["/", "/expenses", "/income", "/goals", "/analytics", "/subscriptions"]
        for ep in endpoints:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 302)
            self.assertIn("/login", res.headers["Location"])

    def test_user_data_isolation(self):
        # Log in as Alice
        self.client.post("/login", data={"email": "alice@example.com", "password": "alicepass"})

        # Alice cannot delete Bob's expense
        res_del_exp = self.client.post(f"/expenses/{self.exp_b.id}/delete")
        self.assertEqual(res_del_exp.status_code, 404)
        self.assertIsNotNone(db.session.get(Expense, self.exp_b.id))

        # Alice cannot delete Bob's income
        res_del_inc = self.client.post(f"/income/{self.inc_b.id}/delete", follow_redirects=True)
        self.assertIn(b"Income record not found", res_del_inc.data)
        self.assertIsNotNone(db.session.get(Income, self.inc_b.id))

        # Alice cannot delete Bob's savings goal
        res_del_goal = self.client.post(f"/goals/{self.goal_b.id}/delete", follow_redirects=True)
        self.assertIn(b"Savings goal not found", res_del_goal.data)
        self.assertIsNotNone(db.session.get(SavingsGoal, self.goal_b.id))

    def test_custom_404_page(self):
        self.client.post("/login", data={"email": "alice@example.com", "password": "alicepass"})
        res = self.client.get("/this-route-does-not-exist-xyz")
        self.assertEqual(res.status_code, 404)
        self.assertIn(b"Ledger Entry Not Found", res.data)


if __name__ == "__main__":
    unittest.main()
