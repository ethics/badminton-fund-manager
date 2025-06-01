from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3, os

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
