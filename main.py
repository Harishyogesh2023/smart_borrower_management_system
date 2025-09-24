from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import psycopg2.extras
from random import randrange
from pydantic import BaseModel
import psycopg2.extras
from psycopg2.extras import RealDictCursor
import json

# --- SMS Integration (Twilio Example) ---
from twilio.rest import Client

TWILIO_ACCOUNT_SID = 'your_account_sid'         # <-- Replace with your Twilio SID
TWILIO_AUTH_TOKEN = 'your_auth_token'           # <-- Replace with your Twilio Auth Token
TWILIO_PHONE_NUMBER = '+1234567890'             # <-- Replace with your Twilio phone number

# database connection
app = FastAPI()
conn = psycopg2.connect(
    host="localhost",
    database="fastapi",
    user="postgres",
    password="Harish@123",
    cursor_factory=psycopg2.extras.DictCursor
)
cur = conn.cursor()
print("connected to database")

# connecting to templates
templates = Jinja2Templates(directory="templates")

# Home page
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

# Create Borrower GET
@app.get("/post", response_class=HTMLResponse)
def post_form(request: Request):
    return templates.TemplateResponse("post.html", {"request": request})

# Create Borrower POST
@app.post("/post", response_class=HTMLResponse)
def create_posts(
    request: Request,
    borrower_id: int = Form(...),
    name: str = Form(...),
    amount: int = Form(...),
    phone: str = Form(...),
    address: str = Form(...)
):
    cur.execute(
        """insert into borrower (borrower_id, b_name, amount, phone_no, address) values(%s, %s, %s, %s, %s)""",
        (borrower_id, name, amount, phone, address)
    )
    conn.commit()
    message = f"id:{borrower_id} - name : {name} -  is added successfully"
    return templates.TemplateResponse("post.html", {"request": request, "message": message})

# View Borrowers
@app.get("/view", response_class=HTMLResponse)
def read_posts(request: Request):
    cur.execute("""
        SELECT borrower_id, b_name, SUM(amount) as total_amount, 
               MAX(phone_no) as phone_no, MAX(address) as address
        FROM borrower
        GROUP BY borrower_id, b_name
    """)
    records = cur.fetchall()
    return templates.TemplateResponse("view.html", {"request": request, "views": records})

# Delete Borrower GET
@app.get("/delete", response_class=HTMLResponse)
def delete_form(request: Request):
    cur.execute("SELECT DISTINCT borrower_id, b_name FROM borrower")
    borrowers = cur.fetchall()
    borrower_ids = sorted(set([row[0] for row in borrowers]))
    # Map: id -> list of names
    id_name_map = {}
    for row in borrowers:
        id_name_map.setdefault(str(row[0]), []).append(row[1])
    return templates.TemplateResponse(
        "delete.html",
        {
            "request": request,
            "borrower_ids": borrower_ids,
            "id_name_map": json.dumps(id_name_map)
        }
    )

# Delete Borrower POST
@app.post("/delete", response_class=HTMLResponse)
def delete_post(request: Request, borrower_id: int = Form(...), name: str = Form(...)):
    cur.execute(
        """delete from borrower where borrower_id=%s and b_name=%s""",
        (str(borrower_id), name)
    )
    conn.commit()
    if cur.rowcount == 0:
        message = "No borrower found with the given ID and Name."
    else:
        message = f"id: {borrower_id} and name: {name} - The content is deleted successfully"

    # Fetch updated borrower_ids and id_name_map for the dropdown and JS
    cur.execute("SELECT DISTINCT borrower_id, b_name FROM borrower")
    borrowers = cur.fetchall()
    borrower_ids = sorted(set([row[0] for row in borrowers]))
    id_name_map = {}
    for row in borrowers:
        id_name_map.setdefault(str(row[0]), []).append(row[1])

    return templates.TemplateResponse(
        "delete.html",
        {
            "request": request,
            "message": message,
            "borrower_ids": borrower_ids,
            "id_name_map": json.dumps(id_name_map)
        }
    )

# Subtract Amount POST
@app.post("/subtract_amount", response_class=HTMLResponse)
def subtract_amount(
    request: Request,
    borrower_id: int = Form(...),
    name: str = Form(...),
    amount: int = Form(...)
):
    # Get current amount
    cur.execute(
        "SELECT amount FROM borrower WHERE borrower_id=%s AND b_name=%s",
        (borrower_id, name)
    )
    row = cur.fetchone()
    if not row:
        subtract_message = "No borrower found with the given ID and Name."
    else:
        current_amount = row[0]
        if amount > current_amount:
            subtract_message = "Cannot subtract more than current balance!"
        else:
            new_amount = current_amount - amount
            cur.execute(
                "UPDATE borrower SET amount=%s WHERE borrower_id=%s AND b_name=%s",
                (new_amount, borrower_id, name)
            )
            conn.commit()
            # Log transaction
            cur.execute(
                """
                INSERT INTO transactions (borrower_id, b_name, amount, type)
                VALUES (%s, %s, %s, %s)
                """,
                (borrower_id, name, amount, 'subtract')
            )
            conn.commit()
            subtract_message = f"Subtracted {amount} from borrower {name} (ID: {borrower_id}). New balance: {new_amount}"

    # Fetch updated borrower_ids and id_name_map for dropdowns
    cur.execute("SELECT DISTINCT borrower_id, b_name FROM borrower")
    borrowers = cur.fetchall()
    borrower_ids = sorted(set([row[0] for row in borrowers]))
    id_name_map = {}
    for row in borrowers:
        id_name_map.setdefault(str(row[0]), []).append(row[1])

    return templates.TemplateResponse(
        "delete.html",
        {
            "request": request,
            "borrower_ids": borrower_ids,
            "id_name_map": json.dumps(id_name_map),
            "subtract_message": subtract_message
        }
    )

# Add Amount GET
@app.get("/add_amount", response_class=HTMLResponse)
def add_amount_form(request: Request):
    cur.execute("SELECT DISTINCT borrower_id, b_name FROM borrower")
    borrowers = cur.fetchall()
    borrower_ids = sorted(set([row[0] for row in borrowers]))
    id_name_map = {}
    for row in borrowers:
        id_name_map.setdefault(str(row[0]), []).append(row[1])
    return templates.TemplateResponse(
        "add_amount.html",
        {
            "request": request,
            "borrower_ids": borrower_ids,
            "id_name_map": json.dumps(id_name_map),
            "message": ""
        }
    )

from datetime import datetime

# Add Amount POST (with SMS if amount >= 500)
@app.get("/transaction_history", response_class=HTMLResponse)
def transaction_history(request: Request, borrower_id: int, name: str):
    # Try to fetch transaction history for this borrower
    # If you have a separate transaction table, replace the query accordingly
    cur.execute(
        """
        SELECT date, amount, type
        FROM transactions
        WHERE borrower_id = %s AND b_name = %s
        ORDER BY date DESC
        """,
        (borrower_id, name)
    )
    transactions = cur.fetchall()
    # If you do not have a transactions table, you need to create one and log each add/subtract
    return templates.TemplateResponse(
        "transaction_history.html",
        {"request": request, "borrower_id": borrower_id, "name": name, "transactions": transactions}
    )
@app.post("/add_amount", response_class=HTMLResponse)
def add_amount(request: Request, borrower_id: int = Form(...), name: str = Form(...), amount: int = Form(...)):
    cur.execute(
        """UPDATE borrower SET amount = amount + %s WHERE borrower_id = %s AND b_name = %s""",
        (amount, borrower_id, name)
    )
    conn.commit()
    if cur.rowcount == 0:
        message = "No borrower found with the given ID and Name."
    else:
        # Log transaction
        cur.execute(
            """
            INSERT INTO transactions (borrower_id, b_name, amount, type)
            VALUES (%s, %s, %s, %s)
            """,
            (borrower_id, name, amount, 'add')
        )
        conn.commit()
        message = f"Amount of {amount} added to borrower ID: {borrower_id}, Name: {name} successfully."

        # --- Send SMS if amount >= 500 ---
        if amount >= 500:
            cur.execute(
                "SELECT phone_no FROM borrower WHERE borrower_id = %s AND b_name = %s",
                (borrower_id, name)
            )
            phone_row = cur.fetchone()
            if phone_row and phone_row[0]:
                phone_no = phone_row[0]
                try:
                    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                    sms_body = f"Dear {name}, Rs.{amount} has been added to your account."
                    client.messages.create(
                        body=sms_body,
                        from_=TWILIO_PHONE_NUMBER,
                        to=phone_no
                    )
                    message += " SMS sent successfully."
                except Exception as e:
                    message += f" (SMS failed: {e})"

    # Fetch updated lists for the form
    cur.execute("SELECT DISTINCT borrower_id, b_name FROM borrower")
    borrowers = cur.fetchall()
    borrower_ids = sorted(set([row[0] for row in borrowers]))
    id_name_map = {}
    for row in borrowers:
        id_name_map.setdefault(str(row[0]), []).append(row[1])

    return templates.TemplateResponse(
        "add_amount.html",
        {
            "request": request,
            "borrower_ids": borrower_ids,
            "id_name_map": json.dumps(id_name_map),
            "message": message}
    )