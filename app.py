from flask import Flask, render_template, request, redirect
import sqlite3, os

app = Flask(__name__)

DB_NAME = "fund.db"

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
