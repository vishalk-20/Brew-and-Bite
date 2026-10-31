import os
import click
from flask import Flask
from sqlalchemy import text, inspect
from app.extensions import db, login_manager


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-in-production"),
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(basedir, 'instance', 'cafe.db')}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.path.join(basedir, 'app', 'static', 'uploads'),
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,
        # Secure session settings.
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 7,  # 7 days for "remember me"
    )

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User, Category, Product

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.main.routes import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()

        # Auto-migrate: add phone column to existing users table if missing.
        inspector = inspect(db.engine)
        if inspector.has_table("users"):
            existing_columns = {col["name"] for col in inspector.get_columns("users")}
            if "phone" not in existing_columns:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE users ADD COLUMN phone VARCHAR(20)'))
                    conn.commit()

        # Seed default categories if the table is empty.
        if Category.query.count() == 0:
            seed_categories = [
                ("Pizzas", "Smoky, cheesy pizzas made fresh."),
                ("Burgers", "Grilled patties with house sauces."),
                ("Shakes", "Creamy milkshakes and cold drinks."),
                ("Beverages", "Coffee, tea and cold beverages."),
                ("Desserts", "Sweet treats to end your meal."),
                ("Snacks", "Light bites and savoury snacks."),
            ]
            for name, description in seed_categories:
                db.session.add(Category(name=name, description=description))
            db.session.commit()

    @app.cli.command("create-admin")
    def create_admin():
        """Create an admin user (email, password and name are prompted)."""
        email = click.prompt("Admin email").strip().lower()
        password = click.prompt("Admin password", hide_input=True, confirmation_prompt=True)
        name = click.prompt("Admin name").strip()
        if User.query.filter_by(email=email).first():
            click.echo("A user with that email already exists.")
            return
        user = User(name=name, email=email, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin user created: {email}")

    return app
