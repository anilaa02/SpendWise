import unittest
from app import create_app, db
from app.models import User, Category
from config import TestConfig


class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_signup_successful(self):
        response = self.client.post(
            "/signup",
            data={
                "name": "Jane Doe",
                "email": "jane@example.com",
                "password": "password123",
                "currency": "USD",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        user = User.query.filter_by(email="jane@example.com").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.name, "Jane Doe")
        self.assertEqual(user.currency, "USD")
        self.assertEqual(user.currency_symbol, "$")
        # Check starter categories seeded
        categories = Category.query.filter_by(user_id=user.id).all()
        self.assertGreater(len(categories), 0)

    def test_duplicate_signup_fails(self):
        self.client.post(
            "/signup",
            data={
                "name": "Jane Doe",
                "email": "jane@example.com",
                "password": "password123",
                "currency": "INR",
            },
        )
        # Log out first so current_user is not authenticated
        self.client.get("/logout")

        response = self.client.post(
            "/signup",
            data={
                "name": "Jane Twin",
                "email": "jane@example.com",
                "password": "password456",
                "currency": "INR",
            },
            follow_redirects=True,
        )
        self.assertIn(b"An account with that email already exists", response.data)


    def test_login_and_logout(self):
        # Create user
        user = User(name="Alex", email="alex@example.com")
        user.set_password("mypassword")
        db.session.add(user)
        db.session.commit()

        # Login
        response = self.client.post(
            "/login",
            data={"email": "alex@example.com", "password": "mypassword"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Financial Dashboard", response.data)

        # Logout
        response = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Log In", response.data)


if __name__ == "__main__":
    unittest.main()
