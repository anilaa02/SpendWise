import unittest
from datetime import date, timedelta
from app import create_app, db
from app.models import User, Category, Expense
from config import TestConfig


class SubscriptionsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(name="Tester", email="test@example.com", currency="USD")
        self.user.set_password("pass123")
        db.session.add(self.user)
        db.session.commit()

        self.cat = Category(name="Utilities", monthly_budget=200.0, user_id=self.user.id)
        db.session.add(self.cat)
        db.session.commit()

        self.client.post("/login", data={"email": "test@example.com", "password": "pass123"})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_recurrence_equivalents_and_forecast(self):
        sub_monthly = Expense(
            amount=15.0,
            note="Spotify",
            date=date(2026, 1, 15),
            is_recurring=True,
            recurrence_period="monthly",
            status="active",
            user_id=self.user.id,
            category_id=self.cat.id,
        )
        sub_yearly = Expense(
            amount=120.0,
            note="Amazon Prime",
            date=date(2025, 6, 1),
            is_recurring=True,
            recurrence_period="yearly",
            status="active",
            user_id=self.user.id,
            category_id=self.cat.id,
        )
        db.session.add_all([sub_monthly, sub_yearly])
        db.session.commit()

        self.assertEqual(sub_monthly.monthly_equivalent, 15.0)
        self.assertEqual(sub_monthly.annual_equivalent, 180.0)

        self.assertEqual(sub_yearly.monthly_equivalent, 10.0)
        self.assertEqual(sub_yearly.annual_equivalent, 120.0)

        # Forecast next renewal date
        next_dt = sub_monthly.next_renewal_date()
        self.assertGreater(next_dt, date.today())

    def test_stale_subscription_needs_review(self):
        old_date = date.today() - timedelta(days=70)
        stale_sub = Expense(
            amount=50.0,
            note="Gym Membership",
            date=old_date,
            is_recurring=True,
            recurrence_period="monthly",
            status="active",
            user_id=self.user.id,
            category_id=self.cat.id,
        )
        db.session.add(stale_sub)
        db.session.commit()

        self.assertTrue(stale_sub.needs_review())

        # Mark reviewed
        response = self.client.post(f"/expenses/{stale_sub.id}/mark-reviewed", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        db.session.refresh(stale_sub)
        self.assertFalse(stale_sub.needs_review())
        self.assertEqual(stale_sub.last_reviewed_date, date.today())

    def test_one_click_renew_subscription(self):
        sub = Expense(
            amount=14.99,
            note="Cloud Storage",
            date=date.today() - timedelta(days=35),
            is_recurring=True,
            recurrence_period="monthly",
            status="active",
            user_id=self.user.id,
            category_id=self.cat.id,
        )
        db.session.add(sub)
        db.session.commit()

        response = self.client.post(f"/subscriptions/{sub.id}/renew", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # New renewal transaction created
        renewals = Expense.query.filter(Expense.note.like("%(Renewal)%")).all()
        self.assertEqual(len(renewals), 1)
        self.assertEqual(renewals[0].amount, 14.99)
        self.assertEqual(renewals[0].date, date.today())

        # Source subscription marked reviewed
        db.session.refresh(sub)
        self.assertEqual(sub.last_reviewed_date, date.today())

    def test_status_toggle(self):
        sub = Expense(
            amount=20.0,
            note="Magazine",
            date=date.today(),
            is_recurring=True,
            recurrence_period="monthly",
            status="active",
            user_id=self.user.id,
            category_id=self.cat.id,
        )
        db.session.add(sub)
        db.session.commit()

        # Pause
        self.client.post(f"/expenses/{sub.id}/toggle-status", data={"status": "paused"}, follow_redirects=True)
        db.session.refresh(sub)
        self.assertEqual(sub.status, "paused")

        # Cancel
        self.client.post(f"/expenses/{sub.id}/toggle-status", data={"status": "cancelled"}, follow_redirects=True)
        db.session.refresh(sub)
        self.assertEqual(sub.status, "cancelled")


if __name__ == "__main__":
    unittest.main()
