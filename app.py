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

# --- CORRECTED IMPORTS ---
# We need get_db_connection for the test route, not just close_db.
from db import close_db, get_db_connection
# We need psycopg2 to catch specific database errors.
import psycopg2
# Your whitenoise import is correct.
from whitenoise import WhiteNoise

def create_app():
    app = Flask(__name__)
    app.secret_key = Config.SECRET_KEY
    app.debug = Config.DEBUG

    app.teardown_appcontext(close_db)

    # All your blueprint registrations are correct
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp, url_prefix='/students')
    app.register_blueprint(teacher_bp, url_prefix='/teachers')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(user_bp, url_prefix='/users')
    app.register_blueprint(assignment_bp, url_prefix='/assignments')
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(curriculum_bp, url_prefix='/curriculum')

    # Your default route is correct
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    # --- ADDED FOR TESTING ---
    # This route provides a simple way to check the database connection on Render.
    @app.route('/test-db')
    def test_db():
        try:
            # Use the corrected get_db_connection function from db.py
            conn = get_db_connection()
            cursor = conn.cursor()
            # Execute a simple query to verify the connection
            cursor.execute("SELECT 1;")
            cursor.close()
            return "✅ Database connection successful!"
        except psycopg2.Error as e:
            # This will catch specific PostgreSQL errors (e.g., bad password)
            return f"❌ Database connection failed: <pre>{e}</pre>"
        except Exception as e:
            # This will catch other errors (e.g., config variable not set)
            return f"❌ An unexpected error occurred: <pre>{e}</pre>"
    # --- END OF TEST ROUTE ---

    return app

app = create_app()

# Your WhiteNoise configuration is correct
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/')

if __name__ == "__main__":
    app.run()