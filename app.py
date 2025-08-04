from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import uuid
import qrcode
from openpyxl import load_workbook
from datetime import datetime

app = Flask(__name__)

# Session storage (in production use database)
sessions = {}

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get('Body', '').strip().lower()
    sender = request.values.get('From', '')
    response = MessagingResponse()
    msg = response.message()

    # Initialize user session
    if sender not in sessions:
        sessions[sender] = {"step": "name"}
        msg.body("Welcome! Please enter your full name:")
        return str(response)

    session = sessions[sender]

    if session["step"] == "name":
        session["name"] = incoming_msg.title()
        session["step"] = "address"
        msg.body("Thanks! Now enter your address:")
    elif session["step"] == "address":
        session["address"] = incoming_msg
        session["step"] = "phone"
        msg.body("Great. Now enter your phone number:")
    elif session["step"] == "phone":
        session["phone"] = incoming_msg
        session["step"] = "order_type"
        msg.body("Is this a *pre-order* or *urgent* order?")
    elif session["step"] == "order_type":
        session["order_type"] = incoming_msg
        session["step"] = "amount"
        msg.body("Enter total order amount (e.g. 2500):")
    elif session["step"] == "amount":
        try:
            total = float(incoming_msg)
            advance = round(total * 0.25, 2)
            session["amount"] = total
            session["advance"] = advance
            session["step"] = "await_payment"
            msg.body(f"To confirm your order, pay ₹{advance} now.\n\nPaytm link: [your-paytm-link-here]\nAfter payment, reply with 'PAID'.")
        except:
            msg.body("Please enter a valid number.")
    elif session["step"] == "await_payment" and incoming_msg == "paid":
        # Generate token
        token = str(uuid.uuid4())[:8].upper()
        session["token"] = token
        session["date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Save to Excel
        wb = load_workbook("excel_store.xlsx")
        ws = wb.active
        ws.append([
            session["name"], session["address"], session["phone"],
            session["order_type"], session["amount"], session["advance"],
            session["date"], token
        ])
        wb.save("excel_store.xlsx")
        
        # Generate QR
        qr_data = f"Token: {token}\nName: {session['name']}\nDue: ₹{session['amount'] - session['advance']}"
        qr = qrcode.make(qr_data)
        qr_path = f"static/qrcodes/{token}.png"
        qr.save(qr_path)

        msg.body(
            f"✅ Payment confirmed!\nToken: *{token}*\nOrder Date: {session['date']}\n\n"
            f"Total: ₹{session['amount']}\nAdvance Paid: ₹{session['advance']}\nRemaining: ₹{session['amount'] - session['advance']}"
        )
        msg.media(f"{request.url_root}{qr_path}")
        sessions.pop(sender)

    else:
        msg.body("Please follow the steps or say 'restart' to begin again.")

    return str(response)

