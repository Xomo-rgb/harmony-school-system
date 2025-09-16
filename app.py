from flask import Flask, redirect, url_for
from config import Config
from routes.auth import auth_bp
from routes.student import student_bp
from routes.teacher import teacher_bp
from routes.admin import admin_bp
from routes.user import user_bp
from routes.assignment import assignment_bp
from routes.profile import profile_bp
from routes.curriculum import curriculum_bp
from db import close_db, get_db_connection
from whitenoise import WhiteNoise  # Serve static files
import psycopg2

def create_app():
    app = Flask(__name__)
    app.secret_key = Config.SECRET_KEY
    app.debug = Config.DEBUG

    app.teardown_appcontext(close_db)

    # Register all blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix='/students')
    app.register_blueprint(teacher_bp, url_prefix='/teachers')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(user_bp, url_prefix='/users')
    app.register_blueprint(assignment_bp, url_prefix='/assignments')
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(curriculum_bp, url_prefix='/curriculum')

    # Default route
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    # --- TEMPORARY TEST ROUTE ---
    # Test database connection from Render
    @app.route('/test-db')
    def test_db():
        try:
            conn = get_db_connection()
            conn.cursor().execute("SELECT 1;")
            return "✅ Database connection successful!"
        except Exception as e:
            return f"❌ Database connection failed: {e}"

    return app

app = create_app()

# Serve static files using WhiteNoise
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/')

if __name__ == "__main__":
    app.run()
