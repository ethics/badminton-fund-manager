from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3, os
from datetime import datetime, timedelta

import pandas as pd
from flask import send_file
import io

from flask import Response

app = Flask(__name__)

DB_NAME = "fund.db"
app.secret_key = "time123"

# Create DB and tables if missing
def init_db():
    if not os.path.exists(DB_NAME):
        conn = get_db_connection()
        c = conn.cursor()

        c.execute('''
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_id INTEGER,
                amount INTEGER,
                date TEXT,
                FOREIGN KEY (member_id) REFERENCES members(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                amount INTEGER NOT NULL,
                date TEXT NOT NULL
            )
        ''')

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

# DB connection with row_factory for dict-like access
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# Members page with add
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
            conn.execute("INSERT INTO payments (member_id, amount, date) VALUES (?, ?, ?)", (member_id, amount, date))
        elif form_type == "expense":
            desc = request.form["description"]
            amount = request.form["amount"]
            date = request.form["date"]
            conn.execute("INSERT INTO expenses (description, amount, date) VALUES (?, ?, ?)", (desc, amount, date))
        elif form_type == "carry_forward":
            month = request.form["month"]
            amount = request.form["amount"]
            conn.execute("INSERT OR REPLACE INTO carry_forward (month, amount) VALUES (?, ?)", (month, amount))
        conn.commit()

    selected_month = request.args.get("month")
    today = datetime.now()
    current_month = selected_month if selected_month else today.strftime("%Y-%m")

    # Get previous month
    prev_month = (datetime.strptime(current_month + "-01", "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m")

    members = conn.execute("SELECT * FROM members").fetchall()

    payments = conn.execute('''
        SELECT p.id, m.name, p.amount, p.date
        FROM payments p
        JOIN members m ON p.member_id = m.id
        WHERE strftime('%Y-%m', p.date) = ?
        ORDER BY p.date DESC
    ''', (current_month,)).fetchall()

    expenses = conn.execute("SELECT * FROM expenses WHERE strftime('%Y-%m', date) = ? ORDER BY date DESC", (current_month,)).fetchall()

    total_income = conn.execute("SELECT SUM(amount) FROM payments WHERE strftime('%Y-%m', date) = ?", (current_month,)).fetchone()[0] or 0
    total_expenses = conn.execute("SELECT SUM(amount) FROM expenses WHERE strftime('%Y-%m', date) = ?", (current_month,)).fetchone()[0] or 0

    # Auto fetch carry forward from previous month and auto-insert if not exists
    carried = conn.execute("SELECT * FROM carry_forward WHERE month = ?", (current_month,)).fetchone()
    if not carried:
        prev_cf = conn.execute("SELECT amount FROM carry_forward WHERE month = ?", (prev_month,)).fetchone()
        prev_amount = prev_cf["amount"] if prev_cf else 0
        carried_amount = prev_amount
        conn.execute("INSERT INTO carry_forward (month, amount) VALUES (?, ?)", (current_month, carried_amount))
        conn.commit()
        carried_id = conn.execute("SELECT id FROM carry_forward WHERE month = ?", (current_month,)).fetchone()["id"]
    else:
        carried_amount = carried["amount"]
        carried_id = carried["id"]

    final_balance = total_income + carried_amount - total_expenses

    # Auto-update next month carry forward
    next_month = (datetime.strptime(current_month + "-01", "%Y-%m-%d") + timedelta(days=31)).replace(day=1).strftime("%Y-%m")
    next_carried = conn.execute("SELECT * FROM carry_forward WHERE month = ?", (next_month,)).fetchone()
    if not next_carried:
        conn.execute("INSERT INTO carry_forward (month, amount) VALUES (?, ?)", (next_month, final_balance))
    else:
        conn.execute("UPDATE carry_forward SET amount = ? WHERE month = ?", (final_balance, next_month))
    conn.commit()

    conn.close()

    return render_template("payments.html", members=members, payments=payments, expenses=expenses,
                           total_income=total_income, total_expenses=total_expenses, carried_amount=carried_amount,
                           final_balance=final_balance, current_month=current_month, carried_id=carried_id)

# Edit payment with row_factory handled in get_db_connection()
@app.route("/edit_payment/<int:id>", methods=["GET", "POST"])
def edit_payment(id):
    conn = get_db_connection()
    payment = conn.execute("SELECT * FROM payments WHERE id = ?", (id,)).fetchone()

    if request.method == "POST":
        new_amount = request.form["amount"]
        new_date = request.form["date"]
        conn.execute("UPDATE payments SET amount = ?, date = ? WHERE id = ?", (new_amount, new_date, id))
        conn.commit()
        conn.close()
        return redirect("/payments")

    conn.close()
    return render_template("edit_payment.html", payment=payment)

# Edit expenses
@app.route("/edit_expense/<int:id>", methods=["GET", "POST"])
def edit_expense(id):
    conn = get_db_connection()
    expense = conn.execute("SELECT * FROM expenses WHERE id = ?", (id,)).fetchone()

    if request.method == "POST":
        new_description = request.form["description"]
        new_amount = request.form["amount"]
        new_date = request.form["date"]
        conn.execute(
            "UPDATE expenses SET description = ?, amount = ?, date = ? WHERE id = ?",
            (new_description, new_amount, new_date, id)
        )
        conn.commit()
        conn.close()
        return redirect("/payments")

    conn.close()
    return render_template("edit_expense.html", expense=expense)

#Edit carry forward
@app.route("/edit_carry_forward/<int:id>", methods=["GET", "POST"])
def edit_carry_forward(id):
    conn = get_db_connection()
    carry_forward = conn.execute("SELECT * FROM carry_forward WHERE id = ?", (id,)).fetchone()

    if request.method == "POST":
        new_month = request.form["month"]
        new_amount = request.form["amount"]
        conn.execute(
            "UPDATE carry_forward SET month = ?, amount = ? WHERE id = ?",
            (new_month, new_amount, id)
        )
        conn.commit()
        conn.close()
        return redirect("/payments")

    conn.close()
    return render_template("edit_carry_forward.html", carry_forward=carry_forward)

@app.route("/export/<string:month>/<string:filetype>")
def export_report(month, filetype):
    conn = get_db_connection()
    df_payments = pd.read_sql_query('''
        SELECT m.name AS Member, p.amount AS Payment, p.date AS Date
        FROM payments p
        JOIN members m ON p.member_id = m.id
        WHERE strftime('%Y-%m', p.date) = ?
    ''', conn, params=(month,))
    df_expenses = pd.read_sql_query('''
        SELECT description AS Description, amount AS Amount, date AS Date
        FROM expenses
        WHERE strftime('%Y-%m', date) = ?
    ''', conn, params=(month,))
    conn.close()

    output = io.BytesIO()

    if filetype == "excel":
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_payments.to_excel(writer, sheet_name="Payments", index=False)
            df_expenses.to_excel(writer, sheet_name="Expenses", index=False)
        output.seek(0)
        return send_file(output, download_name=f"{month}_report.xlsx", as_attachment=True)
    
    elif filetype == "pdf":
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        pdf.set_font('DejaVu', '', 14)
        pdf.cell(200, 10, txt=f"Monthly Report: {month}", ln=True, align='C')
        pdf.ln(10)
        pdf.cell(200, 10, txt="Payments", ln=True)
        for index, row in df_payments.iterrows():
            pdf.cell(200, 10, txt=f"{row['Member']} - ₹{row['Payment']} on {row['Date']}", ln=True)
        pdf.ln(10)
        pdf.cell(200, 10, txt="Expenses", ln=True)
        for index, row in df_expenses.iterrows():
            pdf.cell(200, 10, txt=f"{row['Description']} - ₹{row['Amount']} on {row['Date']}", ln=True)
        output = io.BytesIO()
        pdf.output(output)
        output.seek(0)
        return send_file(output, download_name=f"{month}_report.pdf", as_attachment=True)
    
    return "Invalid format", 400


@app.route("/export_report_txt/<month>")
def export_report_txt(month):
    if not session.get("admin"):
        return "Unauthorized", 403

    conn = get_db_connection()

    # Format month for display: e.g., "2025-04" to "April - 2025"
    display_month = datetime.strptime(month, "%Y-%m").strftime("%B - %Y")

    # Get members who paid in that month
    members_paid = conn.execute('''
        SELECT DISTINCT m.name FROM payments p
        JOIN members m ON p.member_id = m.id
        WHERE strftime('%Y-%m', p.date) = ?
    ''', (month,)).fetchall()

    # Get expenses in that month
    expenses = conn.execute('''
        SELECT * FROM expenses WHERE strftime('%Y-%m', date) = ?
    ''', (month,)).fetchall()

    # Financial summary
    total_collected = conn.execute('''
        SELECT SUM(amount) FROM payments WHERE strftime('%Y-%m', date) = ?
    ''', (month,)).fetchone()[0] or 0

    total_expenses = conn.execute('''
        SELECT SUM(amount) FROM expenses WHERE strftime('%Y-%m', date) = ?
    ''', (month,)).fetchone()[0] or 0

    # Previous month for carry forward
    from datetime import timedelta
    prev_month_date = datetime.strptime(month + "-01", "%Y-%m-%d") - timedelta(days=1)
    prev_month = prev_month_date.strftime("%Y-%m")

    carry_forward = conn.execute('''
        SELECT amount FROM carry_forward WHERE month = ?
    ''', (prev_month,)).fetchone()

    carry_forward_amount = carry_forward["amount"] if carry_forward else 0

    cash_in_hand = carry_forward_amount + total_collected - total_expenses

    conn.close()

    # Format members list or say Nil
    members_list = "\n".join([m["name"] for m in members_paid]) if members_paid else "Nil"

    # Expenses description or Nil
    expenses_desc = "Nil"
    if expenses:
        expenses_desc = "\n".join([f"{e['description']}: {e['amount']}" for e in expenses])

    text_report = f"""
Shuttle Fund {display_month}
Subscription Details

Subscription Recipients

Name
{members_list}

Expenses
{expenses_desc}

Financial Summary for {month}
Total Subscription Collected - {total_collected if total_collected else 'Nil'}
Total Expenses - {total_expenses if total_expenses else 'Nil'}
Carry forward cash from previous month - {carry_forward_amount if carry_forward_amount else 'Nil'}
Cash in Hand - {cash_in_hand}
"""

    return Response(text_report, mimetype="text/plain",
                    headers={"Content-Disposition": f"attachment;filename=Shuttle_Fund_Report_{month}.txt"})


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

