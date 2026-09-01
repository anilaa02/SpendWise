import unittest
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from app import create_app, db
from app.models import User, SavingsGoal, GoalContribution
from config import TestConfig


class GoalsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.user = User(name="Goal User", email="goal@example.com", currency="INR")
        self.user.set_password("pass123")
        db.session.add(self.user)
        db.session.commit()

        self.client.post("/login", data={"email": "goal@example.com", "password": "pass123"})

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_create_savings_goal(self):
        future_date = date.today() + relativedelta(months=10)
        response = self.client.post(
            "/goals/add",
            data={
                "name": "New Laptop",
                "target_amount": "70000",
                "current_amount": "10000",
                "target_date": future_date.isoformat(),
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        goal = SavingsGoal.query.filter_by(name="New Laptop", user_id=self.user.id).first()
        self.assertIsNotNone(goal)
        self.assertEqual(goal.target_amount, 70000.0)
        self.assertEqual(goal.current_amount, 10000.0)
        self.assertFalse(goal.is_completed)
        self.assertGreater(goal.required_monthly_savings, 0.0)
        # Check initial contribution logged
        self.assertEqual(len(goal.contributions), 1)

    def test_add_contribution_and_completion(self):
        goal = SavingsGoal(
            name="Emergency Fund",
            target_amount=5000.0,
            current_amount=3000.0,
            user_id=self.user.id,
        )
        db.session.add(goal)
        db.session.commit()

        # Contribute 2500 -> reaches 5500 -> auto completed
        response = self.client.post(
            f"/goals/{goal.id}/contribute",
            data={
                "amount": "2500",
                "note": "Bonus allocation",
                "date": date.today().isoformat(),
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        db.session.refresh(goal)
        self.assertEqual(goal.current_amount, 5500.0)
        self.assertEqual(goal.status, "completed")
        self.assertTrue(goal.is_completed)
        self.assertEqual(goal.progress_pct, 100.0)

    def test_overdue_goal_detection(self):
        past_date = date.today() - timedelta(days=30)
        goal = SavingsGoal(
            name="Past Goal",
            target_amount=10000.0,
            current_amount=2000.0,
            target_date=past_date,
            user_id=self.user.id,
        )
        db.session.add(goal)
        db.session.commit()

        self.assertTrue(goal.is_overdue)

    def test_delete_goal(self):
        goal = SavingsGoal(name="To Delete", target_amount=5000.0, user_id=self.user.id)
        db.session.add(goal)
        db.session.commit()

        response = self.client.post(f"/goals/{goal.id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(db.session.get(SavingsGoal, goal.id))


if __name__ == "__main__":
    unittest.main()
