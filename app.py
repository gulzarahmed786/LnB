from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector as connector
from werkzeug.utils import secure_filename
import os
from ultralytics import YOLO
from collections import Counter
from dotenv import load_dotenv

config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Ahmed@123',
    'database': 'car_damage_detection'
}

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
# Paths and YOLO model initialization
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def connect_to_db():
    try:
        connection = connector.connect(**config)
        return connection
    except connector.Error as e:
        print(f"Error connecting to database: {e}")
        return None

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        password = request.form.get('password')
        email = request.form.get('email')
        vehicle_id = request.form.get('vehicle_id')
        contact_number = request.form.get('contact_number')
        address = request.form.get('address')
        car_brand = request.form.get('car_brand')
        model = request.form.get('model')

        print(f"Name: {name}")
        print(f"Password: {password}")
        print(f"Email: {email}")
        print(f"Vehicle ID: {vehicle_id}")
        print(f"Contact Number: {contact_number}")
        print(f"Address: {address}")
        print(f"Car Brand: {car_brand}")
        print(f"Model: {model}")


        if not all([name, password, email, vehicle_id, contact_number, address, car_brand, model]):
            flash("All fields are required!", "error")
            return render_template('signup.html')

        connection = connect_to_db()
        if connection:
            try:
                with connection.cursor() as cursor:
                    query = '''
                    INSERT INTO user_info (name, password, email, vehicle_id, contact_number, address, car_brand, model)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    '''
                    cursor.execute(query, (name, password, email, vehicle_id, contact_number, address, car_brand, model))
                    connection.commit()
                flash("Signup successful!", "success")
                return redirect(url_for('login'))
            except connector.IntegrityError as e:
                if 'Duplicate entry' in str(e):
                    flash("Email already exists. Please use a different email.", "error")
                else:
                    flash("An error occurred while signing up. Please try again.", "error")
            except connector.Error as e:
                print(f"Error executing query: {e}")
                flash("An error occurred while signing up. Please try again.", "error")
        else:
            flash("Database connection failed. Please try again later.", "error")

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash("Email and password are required!", "error")
            return render_template('login.html')

        connection = connect_to_db()
        if connection:
            try:
                with connection.cursor() as cursor:
                    query = "SELECT password FROM user_info WHERE email = %s"
                    cursor.execute(query, (email,))
                    result = cursor.fetchone()
                    if result and result[0] == password:
                        flash("Login successful!", "success")
                        return redirect(url_for('dashboard'))
                    else:
                        flash("Invalid email or password.", "error")
            except connector.Error as e:
                print(f"Error executing query: {e}")
                flash("An error occurred during login. Please try again.", "error")
        else:
            flash("Database connection failed. Please try again later.", "error")

    return render_template('login.html')

# Load YOLO model
model_path = "model/best.pt"
model = YOLO(model_path)

def get_part_prices(class_counts):
    prices = {}
    connection = None
    cursor = None
    
    try:
        connection = connect_to_db()
        cursor = connection.cursor(dictionary=True)
        
        for class_id, count in class_counts.items():
            part_name = get_part_name_from_id(int(class_id))
            if part_name:
                print(f"Querying price for part: {part_name}")
                
                cursor.execute("SELECT price FROM car_models WHERE part = %s", (part_name,))
                price_data = cursor.fetchone()
                cursor.fetchall()  # Consume any remaining results
                
                print(f"Price data retrieved: {price_data}")
                
                if price_data:
                    price_per_part = float(price_data['price'])
                    total_price = price_per_part * count
                    prices[part_name] = {
                        'count': count,
                        'price': round(price_per_part, 2),
                        'total': round(total_price, 2)
                    }
                else:
                    print(f"No price found for part: {part_name}")
        
        print(f"Final prices dictionary: {prices}")
        return prices
            
    except connector.Error as e:
        print(f"Database error: {e}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_part_name_from_id(class_id):
    class_names = ['Bonnet', 'Bumper', 'Dickey', 'Door', 'Fender', 'Light', 'Windshield']
    if 0 <= class_id < len(class_names):
        return class_names[int(class_id)]
    return None

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if request.method == 'POST':
        try:
            file = request.files.get('image')
            if not file:
                flash('Please upload an image.', 'error')
                return render_template('dashboard.html')

            filename = secure_filename(file.filename)
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                flash('Invalid file type. Please upload an image.', 'error')
                return render_template('dashboard.html')

            # Save the uploaded image
            image_path = os.path.join(UPLOAD_FOLDER, 'uploaded_image.jpg')
            file.save(image_path)
            print(f"Image saved at: {image_path}")
            
            # Make predictions
            result = model(image_path)
            detected_objects = result[0].boxes
            class_ids = [int(box.cls.item()) for box in detected_objects]
            class_counts = Counter(class_ids)
            print(f"Detected class counts: {class_counts}")
            
            # Save detected image
            detected_image_path = os.path.join(UPLOAD_FOLDER, 'detected_image.jpg')
            result[0].save(detected_image_path)
            
            # Get part prices
            part_prices = get_part_prices(class_counts)
            print(f"Part prices calculated: {part_prices}")
            
            if not part_prices:
                flash('No price information available for detected parts.', 'warning')
            
            return render_template(
                'estimate.html',
                original_image='uploads/uploaded_image.jpg',
                detected_image='uploads/detected_image.jpg',
                part_prices=part_prices
            )
            
        except Exception as e:
            flash(f'Error processing image: {str(e)}', 'error')
            print(f"Error: {e}")
            return render_template('dashboard.html')

    return render_template('dashboard.html')

if __name__ == '__main__':
    app.run(debug=True)
