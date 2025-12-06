import cv2
import time
import requests
import RPi.GPIO as GPIO
from pyzbar import pyzbar
from datetime import datetime, timedelta
from app import app
from models import db, Product, InventoryItem

# --- Configuration Constants ---
GPIO_GREEN_LED = 17  # Pin 11
GPIO_RED_LED = 22    # Pin 15
GPIO_BUZZER = 18     # Pin 12
GPIO_BUTTON = 23     # Pin 16

# Open Food Facts API Endpoint
OFF_API_URL = "https://world.openfoodfacts.org/api/v2/product/{}"

# --- GPIO Initialization ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(GPIO_GREEN_LED, GPIO.OUT)
GPIO.setup(GPIO_RED_LED, GPIO.OUT)
GPIO.setup(GPIO_BUZZER, GPIO.OUT)
# Button uses internal pull-up resistor (Active Low)
GPIO.setup(GPIO_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def feedback_success():
    """Triggers visual (Green LED) and auditory (Short Beep) success indicators."""
    print("Feedback: Success")
    GPIO.output(GPIO_GREEN_LED, GPIO.HIGH)
    GPIO.output(GPIO_BUZZER, GPIO.HIGH)
    time.sleep(0.1) # Short beep
    GPIO.output(GPIO_BUZZER, GPIO.LOW)
    time.sleep(0.4) # LED remains on briefly
    GPIO.output(GPIO_GREEN_LED, GPIO.LOW)

def feedback_error():
    """Triggers visual (Red LED) and auditory (Long Beep) error indicators."""
    print("Feedback: Error")
    GPIO.output(GPIO_RED_LED, GPIO.HIGH)
    GPIO.output(GPIO_BUZZER, GPIO.HIGH)
    time.sleep(0.5) # Long beep
    GPIO.output(GPIO_BUZZER, GPIO.LOW)
    GPIO.output(GPIO_RED_LED, GPIO.LOW)

def get_product_info_from_api(barcode):
    """
    Queries Open Food Facts API for product details.
    Returns a dictionary of metadata or None if failed.
    """
    try:
        url = OFF_API_URL.format(barcode)
        # Custom User-Agent is required by OFF policy
        headers = {'User-Agent': 'SKISS-RaspberryPi/1.0 (Student Project)'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 1:
                product_data = data['product']
                return {
                    'name': product_data.get('product_name', 'Unknown Product'),
                    'category': product_data.get('categories_tags', ['Unknown']),
                    'image': product_data.get('image_front_small_url', '')
                }
    except Exception as e:
        print(f"API Connection Error: {e}")
    return None

def process_barcode(barcode_data):
    """
    Main business logic:
    1. Check if product exists in local DB.
    2. If not, fetch from API and save to DB.
    3. Add instance to InventoryItem.
    4. Trigger feedback.
    """
    # Use app context to access the database outside of a web request
    with app.app_context():
        product = Product.query.get(barcode_data)
        
        # If product is new to the system, fetch metadata
        if not product:
            print(f"New product detected: {barcode_data}. Querying API...")
            info = get_product_info_from_api(barcode_data)
            
            if info:
                product = Product(
                    barcode=barcode_data,
                    name=info['name'],
                    category=info['category'],
                    image_url=info['image']
                )
                db.session.add(product)
                db.session.commit()
            else:
                print("Product not found in Open Food Facts.")
                feedback_error()
                return

        # Add item to inventory
        # Check if we already have this item to just increment quantity (optional logic)
        # For this implementation, we add a distinct item or increment quantity
        existing_item = InventoryItem.query.filter_by(barcode=barcode_data).first()
        
        if existing_item:
            existing_item.quantity += 1
            print(f"Updated quantity for {product.name}")
        else:
            # Simple shelf-life heuristic: Default to 7 days from now
            default_expiry = datetime.utcnow().date() + timedelta(days=7)
            new_item = InventoryItem(
                barcode=barcode_data,
                expiration_date=default_expiry
            )
            db.session.add(new_item)
            print(f"Added new item: {product.name}")
        
        db.session.commit()
        feedback_success()

def main():
    print("Starting SKISS Scanner Service...")
    
    # Initialize Camera
    # Note: On Raspberry Pi OS Bookworm, legacy camera support must be enabled 
    # for /dev/video0 to work with cv2.VideoCapture(0)
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    last_scan_time = 0
    SCAN_COOLDOWN = 3.0 # Seconds

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Could not read frame from camera.")
                time.sleep(1)
                continue

            # Pre-processing: Convert to Grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Pre-processing: Adaptive Thresholding for variable lighting
            # This helps detecting barcodes in dim or unevenly lit pantries
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # Decode using pyzbar
            # We can pass either 'gray' or 'thresh'. 'gray' often works well with pyzbar's internal binarization.
            barcodes = pyzbar.decode(gray)

            for barcode in barcodes:
                barcode_data = barcode.data.decode("utf-8")
                current_time = time.time()

                # Debounce logic to prevent rapid re-scanning
                if (current_time - last_scan_time) > SCAN_COOLDOWN:
                    print(f"Barcode Detected: {barcode_data}")
                    process_barcode(barcode_data)
                    last_scan_time = current_time
                
            # Check for physical button press to reset or trigger manual actions
            if GPIO.input(GPIO_BUTTON) == GPIO.LOW:
                print("Manual Button Pressed")
                time.sleep(0.2) # Debounce button
            
            # Small sleep to reduce CPU usage
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("Stopping scanner...")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        GPIO.cleanup()

if __name__ == "__main__":
    main()