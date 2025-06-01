from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3, os
from datetime import datetime

app = Flask(__name__)

DB_NAME = "fund.db"
app.secret_key = "time123"

# ✅ Step 1: Create DB and tables if missing
def init_db():
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # Create members table
        c.execute('''
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL
            )
        ''')

        # Payments table
        c.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER,
                amount INTEGER,
                date TEXT,
                FOREIGN KEY (member_id) REFERENCES members(id)
            )
        ''')

        # Expenses Table
        c.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                amount INTEGER NOT NULL,
                date TEXT NOT NULL
            )
        ''')

        # Carry Forward Table (one entry per month)
        c.execute('''
            CREATE TABLE IF NOT EXISTS carry_forward (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT UNIQUE,
            amount INTEGER NOT NULL
            )
            ''')

        conn.commit()
        conn.close()
        print("✅ Database and tables created.")

# ✅ Step 2: Get DB connection
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ✅ Step 3: Members page
@app.route("/members", methods=["GET", "POST"])
def members():
    conn = get_db_connection()
    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        conn.execute("INSERT INTO members (name, phone) VALUES (?, ?)", (name, phone))
        conn.commit()

    members = conn.execute("SELECT * FROM members").fetchall()
    conn.close()
    return render_template("members.html", members=members)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == "admin" and password == "iadmin123":
            session["admin"] = True
            return redirect("/members")
        else:
            return "Invalid credentials"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/login")


@app.route("/delete_member/<int:member_id>", methods=["POST"])
def delete_member(member_id):
    if not session.get("admin"):
        return "Unauthorized", 403
    conn = get_db_connection()
    conn.execute("DELETE FROM members WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()
    return redirect("/members")

@app.route("/payments", methods=["GET", "POST"])
def payments():
    if not session.get("admin"):
        return "Unauthorized", 403

    conn = get_db_connection()

    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "payment":
            member_id = request.form["member_id"]
            amount = request.form["amount"]
            date = request.form["date"]
            conn.execute("INSERT INTO payments (member_id, amount, date) VALUES (?, ?, ?)",
                         (member_id, amount, date))

        elif form_type == "expense":
            desc = request.form["description"]
            amount = request.form["amount"]
            date = request.form["date"]
            conn.execute("INSERT INTO expenses (description, amount, date) VALUES (?, ?, ?)",
                         (desc, amount, date))

        elif form_type == "carry_forward":
            month = request.form["month"]
            amount = request.form["amount"]
            conn.execute("INSERT OR REPLACE INTO carry_forward (month, amount) VALUES (?, ?)", (month, amount))

        conn.commit()

    today = datetime.now()
    current_month = today.strftime("%Y-%m")

    # Fetch all members for dropdown
    members = conn.execute("SELECT * FROM members").fetchall()

    # Join payments with member names
    payments = conn.execute('''
        SELECT m.name, p.amount, p.date
        FROM payments p
        JOIN members m ON p.member_id = m.id
        ORDER BY p.date DESC
    ''').fetchall()

    expenses = conn.execute("SELECT * FROM expenses ORDER BY date DESC").fetchall()

    total_income = conn.execute("SELECT SUM(amount) FROM payments").fetchone()[0] or 0
    total_expenses = conn.execute("SELECT SUM(amount) FROM expenses").fetchone()[0] or 0
    carried = conn.execute("SELECT amount FROM carry_forward WHERE month = ?", (current_month,)).fetchone()
    carried_amount = carried[0] if carried else 0
    final_balance = total_income + carried_amount - total_expenses

    conn.close()

    return render_template("payments.html", members=members, payments=payments,
                           expenses=expenses, total_income=total_income,
                           carried_amount=carried_amount, total_expenses=total_expenses,
                           final_balance=final_balance, current_month=current_month)


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
