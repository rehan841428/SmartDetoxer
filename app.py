
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)

# For local development only.
# Replace with a secure environment variable before deployment.
app.secret_key = "smartdetoxer-development-key"

DATABASE = "smartdetoxer.db"


# DATABASE CONNECTION
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# CREATE DATABASE TABLES
def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            screen_time REAL NOT NULL,
            social_media REAL NOT NULL,
            phone_checks INTEGER NOT NULL,
            sleep_hours REAL NOT NULL,
            before_sleep INTEGER NOT NULL,
            risk_score INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


# LOGIN PROTECTION
def login_required(route):
    @wraps(route)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.")
            return redirect(url_for("login"))
        return route(*args, **kwargs)
    return wrapper


# HOME
@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or len(password) < 8:
            flash("Enter valid details. Password must have at least 8 characters.")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        conn = get_db()

        try:
            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, hashed_password)
            )
            conn.commit()

            flash("Account created successfully. Please login.")

        except sqlite3.IntegrityError:
            flash("Email already registered.")

        finally:
            conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


# DASHBOARD
@app.route("/dashboard")
@login_required
def dashboard():

    conn = get_db()

    assessments = conn.execute("""
        SELECT * FROM assessments
        WHERE user_id = ?
        ORDER BY id DESC
    """, (session["user_id"],)).fetchall()

    conn.close()

    latest = assessments[0] if assessments else None

    return render_template(
        "dashboard.html",
        assessments=assessments,
        latest=latest
    )


# ASSESSMENT
@app.route("/assessment", methods=["GET", "POST"])
@login_required
def assessment():

    if request.method == "POST":

        try:
            screen_time = float(request.form["screen_time"])
            social_media = float(request.form["social_media"])
            phone_checks = int(request.form["phone_checks"])
            sleep_hours = float(request.form["sleep_hours"])
            before_sleep = int(request.form.get("before_sleep", 0))

        except (ValueError, KeyError):
            flash("Please enter valid information.")
            return redirect(url_for("assessment"))

        if (
            not 0 <= screen_time <= 24
            or not 0 <= social_media <= 24
            or not 0 <= phone_checks <= 2000
            or not 0 <= sleep_hours <= 24
            or before_sleep not in (0, 1)
        ):
            flash("Please enter values within the allowed ranges.")
            return redirect(url_for("assessment"))

        # INITIAL DEMONSTRATION SCORING
        # This will be replaced with the trained ML model in Phase 2.

        score = 0

        if screen_time >= 8:
            score += 3
        elif screen_time >= 5:
            score += 2
        elif screen_time >= 3:
            score += 1

        if social_media >= 5:
            score += 2
        elif social_media >= 3:
            score += 1

        if phone_checks >= 100:
            score += 2
        elif phone_checks >= 50:
            score += 1

        if sleep_hours < 6:
            score += 2
        elif sleep_hours < 7:
            score += 1

        if before_sleep:
            score += 1

        if score <= 3:
            risk_level = "Low"
        elif score <= 6:
            risk_level = "Moderate"
        else:
            risk_level = "High"

        conn = get_db()

        conn.execute("""
            INSERT INTO assessments
            (user_id, screen_time, social_media,
             phone_checks, sleep_hours, before_sleep,
             risk_score, risk_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            screen_time,
            social_media,
            phone_checks,
            sleep_hours,
            before_sleep,
            score,
            risk_level
        ))

        conn.commit()
        conn.close()

        return render_template(
            "result.html",
            score=score,
            risk_level=risk_level
        )

    return render_template("assessment.html")


# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)