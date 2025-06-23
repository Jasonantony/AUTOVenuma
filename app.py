from flask import *
from flask import request, session, jsonify
from  flask_sqlalchemy import SQLAlchemy
from werkzeug.security import *
from twilio.rest import Client
from flask import session, request, redirect, url_for, render_template


app=Flask(__name__)



#configuring the database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
# app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///driver.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "your-secret-key"
db = SQLAlchemy(app)
#database model
class User(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(100), nullable=False)
    name     = db.Column(db.String(100))
    email    = db.Column(db.String(100))
    age      = db.Column(db.String(10))
    sex      = db.Column(db.String(10))
    phone    = db.Column(db.String(20))
    address  = db.Column(db.Text)
    score    = db.Column(db.Integer, default=0)


    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)
# ---------- Driver DB Model ----------
class Driver(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(15), unique=True)
    vehicle_number = db.Column(db.String(20))
    available = db.Column(db.Boolean, default=True)
    confirmed = db.Column(db.Boolean, default=False)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


# ---------- Fare Calculation ----------
def calculate_fare(pickup, drop):
    distance = 10  # Dummy fixed distance (KM)
    fare_per_km = 15
    return distance * fare_per_km

# ---------- Nearest Driver Selection ----------
def get_nearest_driver():
    return Driver.query.filter_by(available=True, confirmed=False).first()

# ---------- Send SMS to Driver ----------
def send_sms_to_driver(driver, user, pickup, drop, fare):
    body_msg = f"""🚖 New Booking Request 🚖

👤 Name: {user['name']}
📞 Phone: {user['phone']}
📍 Pickup: {pickup}
🏁 Drop: {drop}
💰 Amount: ₹{fare}

Reply YES if you can take this booking.
"""

    account_sid = 'AC6780d2965c578f1cb5a17c6442fee61a'
    auth_token = 'dc47034f8462d1fa2341d961087871a3'
    client = Client(account_sid, auth_token)

    try:
        message = client.messages.create(
            messaging_service_sid='MG31c1c086b7c35b41c1b83359e46744b8',
            from_='+17622659080',  # Replace with your Twilio number
            body=body_msg,
            to='+18777804236'
        )
        print(f"SMS sent: {message.sid}")
    except Exception as e:
        print(f"SMS sending failed: {e}")

# ---------- Booking Endpoint ----------
@app.route('/billing', methods=['POST'])
def billing():
    name = request.form.get('name')
    phone = request.form.get('phone')
    pickup = request.form.get('pickup')
    drop = request.form.get('drop')
    fare = calculate_fare(pickup, drop)

    driver = get_nearest_driver()

    if driver:
        send_sms_to_driver(driver, user={'name': name, 'phone': phone}, pickup=pickup, drop=drop, fare=fare)
        return '', 204  # No content, as JS will handle UI
    else:
        return "No drivers available", 503

# ---------- SMS Reply Handler ----------
@app.route('/sms_reply', methods=['POST'])
def sms_reply():
    from_number = request.form.get('From')
    body = request.form.get('Body').strip().upper()

    if body == "YES":
        driver_obj = Driver.query.filter_by(phone=from_number).first()
        if driver_obj:
            driver_obj.confirmed = True
            driver_obj.available = False
            db.session.commit()
            return "Booking confirmed"
    return "Reply not understood"

# ---------- Polling: Check Driver Confirmation ----------
@app.route('/check_driver_status')
def check_driver_status():
    driver = Driver.query.filter_by(confirmed=True).first()
    if driver:
        return jsonify({"status": "confirmed"})
    return jsonify({"status": "waiting"})

# ---------- Fetch Confirmed Driver Info ----------
@app.route('/get_confirmed_driver')
def get_confirmed_driver():
    driver = Driver.query.filter_by(confirmed=True).first()
    if driver:
        return jsonify({
            "name": driver.name,
            "phone": driver.phone,
            "vehicle": driver.vehicle_number,
            "eta": "15 mins"
        })
    return jsonify({"error": "No confirmed driver"}), 404

# ---------- Optional: Driver Registration ----------
@app.route("/driver_register", methods=["GET", "POST"])
def driver_register():
    if request.method == "POST":
        name = request.form.get("name")
        phone = request.form.get("phone")
        vehicle_number = request.form.get("vehicle_number")

        if not name or not phone or not vehicle_number:
            return "All fields are required", 400

        existing_driver = Driver.query.filter_by(phone=phone).first()
        if existing_driver:
            return "Driver already registered", 400

        new_driver = Driver(name=name, phone=phone, vehicle_number=vehicle_number)
        db.session.add(new_driver)
        db.session.commit()
        return "Driver registered successfully!"
    return render_template("driver_register.html")



@app.route('/update_score', methods=['POST'])
def update_score():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'User not logged in'}), 401

    user_id = session['user_id']
    data = request.get_json()
    fare = data.get('fare')

    if fare is None:
        return jsonify({'status': 'error', 'message': 'Fare not provided'}), 400

    user = User.query.get(user_id)
    if user:
        added_score = (int(fare) // 50) * 10
        user.score = min(user.score + added_score, 500)
        db.session.commit()
        return jsonify({'status': 'success', 'new_score': user.score})
    return jsonify({'status': 'error', 'message': 'User not found'}), 404


@app.before_request
def create_tables():
    db.create_all()

@app.route('/profile', methods=["GET", "POST"])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=session['username']).first()

    if request.method == 'POST':
        user.name    = request.form.get('name')
        user.email   = request.form.get('email')
        user.age     = request.form.get('age')
        user.sex     = request.form.get('sex')
        user.phone   = request.form.get('phone')
        user.address = request.form.get('address')
        db.session.commit()
        return render_template('dashboard.html', user=user, message="Profile updated!")

    # If profile already filled, just show it
    if user.name and user.age and user.sex and user.phone and user.address:
        return render_template('dashboard.html', user=user)
    else:
        return render_template('profile.html', user=user)

# booking auto

@app.route("/booking", methods=["GET", "POST"])
def booking():
    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            return redirect(url_for('login'))

        return render_template('booking.html', user=user)
    else:
        return redirect(url_for('login'))




@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['username'] = username

            # Check if profile is complete (modify based on your required fields)
            if user.name and user.age and user.sex and user.phone and user.address:
                return redirect(url_for('dashboard'))  # Redirect to dashboard if profile is complete
            else:
                return redirect(url_for('profile'))  # Same route handles form fill if data is missing
        else:
            return "Invalid credentials", 401

    return render_template('login.html')




@app.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        print("Form submitted")  
        print(f"Username: {username}, Email: {email}")  

        user = User.query.filter_by(username=username).first()
        if user:
            return render_template("login.html", error="User already exists")

        new_user = User(username=username, email=email)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        session['username'] = username
        return redirect(url_for('dashboard'))

    # ❌ Don't use username/email outside POST
    return render_template("signin.html")





@app.route("/book")
def book():
    return render_template("booking.html")

@app.route("/dashboard")
def dashboard():
    if 'username' in session:
        user = User.query.filter_by(username=session['username']).first()
        if not user:
            return redirect(url_for('login'))
        return render_template("dashboard.html", user=user)

    return redirect(url_for('login'))



@app.route('/logout')
def logout():
    session.pop('username', None)  # Remove 'username' from session if it exists
    return redirect(url_for('login'))  # Redirect to login page (or any page you want)






if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)