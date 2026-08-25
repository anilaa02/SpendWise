from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config
from sqlalchemy import text

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_user_preferences():
        from flask_login import current_user
        currency_sym = "₹"
        if current_user.is_authenticated and hasattr(current_user, "currency_symbol"):
            currency_sym = current_user.currency_symbol
        return dict(currency_sym=currency_sym)

    from app.routes.auth import auth_bp
    from app.routes.expenses import expenses_bp
    from app.routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(dashboard_bp)

    with app.app_context():
        db.create_all()

        # Automatic SQLite schema migration for older database files:
        # Ensures `user.currency` and `expense.status` exist without losing existing data.
        try:
            with db.engine.connect() as conn:
                user_cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(user)").fetchall()]
                if "currency" not in user_cols:
                    conn.exec_driver_sql("ALTER TABLE user ADD COLUMN currency VARCHAR(10) DEFAULT 'INR' NOT NULL")

                expense_cols = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(expense)").fetchall()]
                if "status" not in expense_cols:
                    conn.exec_driver_sql("ALTER TABLE expense ADD COLUMN status VARCHAR(20) DEFAULT 'active' NOT NULL")

                conn.commit()
        except Exception as e:
            app.logger.warning(f"Database schema auto-migration notice: {e}")

    return app


