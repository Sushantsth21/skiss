import os
from twilio.rest import Client
from datetime import datetime, timedelta
from app import app
from models import db, InventoryItem
from dotenv import load_dotenv

load_dotenv()

def send_daily_alerts():
    # Load Credentials
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    to_phone = os.getenv('USER_PHONE')
    from_phone = os.getenv('TWILIO_PHONE')

    # Initialize Twilio Client
    try:
        client = Client(account_sid, auth_token)
    except Exception as e:
        print(f"Twilio Client Init Error: {e}")
        return

    with app.app_context():
        # Logic: Find items expiring within the next 3 days
        today = datetime.utcnow().date()
        threshold = today + timedelta(days=3)
        
        expiring_items = InventoryItem.query.filter(
            InventoryItem.expiration_date <= threshold
        ).all()

        if expiring_items:
            # Construct SMS Body
            msg_body = "SKISS Pantry Alert! \n\nThe following items are expiring soon:\n"
            for item in expiring_items:
                days_left = (item.expiration_date - today).days
                if days_left < 0:
                    status = "EXPIRED"
                elif days_left == 0:
                    status = "Today"
                else:
                    status = f"in {days_left} days"
                    
                msg_body += f"- {item.product.name}: {status}\n"
            
            # Send SMS
            try:
                message = client.messages.create(
                    body=msg_body,
                    from_=from_phone,
                    to=to_phone
                )
                print(f"Alert successfully sent. SID: {message.sid}")
            except Exception as e:
                print(f"Failed to send SMS: {e}")
        else:
            print("No expiring items found today.")

if __name__ == "__main__":
    send_daily_alerts()