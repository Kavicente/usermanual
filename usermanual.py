from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_socketio import SocketIO
import sqlite3
import os
import csv
import json
import logging
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'alertnow_secret_key_2026'

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

socketio = SocketIO(app, async_mode='threading', cors_allowed_origins="*", max_http_buffer_size=10000000)

# ====================== DATABASE ======================
def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'users_web.db')
    if not os.path.exists(os.path.dirname(db_path)):
        os.makedirs(os.path.dirname(db_path))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# ====================== LOAD BARANGAYS ======================
def load_barangays():
    barangays = {"San Pablo City": [], "Tiaong": []}
    lat_lon_map = {}
    csv_path = os.path.join(app.static_folder, 'Barangay.csv')
    
    if not os.path.exists(csv_path):
        logger.error(f"Barangay.csv not found")
        return barangays, lat_lon_map

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 4:
                    municipality = row[0].strip()
                    barangay = row[1].strip()
                    lat = row[2].strip()
                    lon = row[3].strip()
                    if municipality in barangays:
                        if barangay not in barangays[municipality]:
                            barangays[municipality].append(barangay)
                        lat_lon_map[barangay] = (lat, lon)
        barangays["San Pablo City"].sort()
        barangays["Tiaong"].sort()
    except Exception as e:
        logger.error(f"Error loading Barangay.csv: {e}")
    return barangays, lat_lon_map

BARANGAYS_DATA, LAT_LON_DATA = load_barangays()

# ====================== ROUTES ======================
@app.route('/')
def index():
    return render_template('usermanual.html')

@app.route('/signup')
def signup():
    signup_type = request.args.get('type')
    if signup_type == 'barangay':
        return redirect(url_for('signup_barangay'))
    return redirect(url_for('signup_agency'))

# ====================== SEND OTP ======================
@app.route('/send_otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'status': 'failed', 'error': 'No email provided'}), 400

    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    session['otp_email'] = email

    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    smtp_user = os.getenv('SMTP_USERNAME')
    smtp_pass = os.getenv('SMTP_PASSWORD')

    if not smtp_user or not smtp_pass:
        logger.error("Gmail SMTP credentials missing in .env")
        return jsonify({'status': 'failed', 'error': 'Email not configured'}), 500

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = email
    msg['Subject'] = "Alert Now - Your OTP Code"
    body = f"Your OTP code is: {otp}\nThis code is valid for 5 minutes."
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, email, msg.as_string())
        server.quit()
        logger.info(f"✅ OTP sent successfully to {email} via Gmail")
        return jsonify({'status': 'sent'})
    except Exception as e:
        logger.error(f"❌ OTP email failed: {e}")
        return jsonify({'status': 'failed', 'error': str(e)}), 500

# ====================== BARANGAY SIGNUP ======================
# ====================== SIGNUP BARANGAY ROUTE ======================
@app.route('/signup_barangay', methods=['GET', 'POST'])
def signup_barangay():
    if request.method == 'POST':
        barangay = request.form['barangay']
        assigned_municipality = request.form['municipality']
        province = request.form['province']
        contact_no = request.form['contact_no']
        password = request.form['password']
        email = request.form.get('email', '')

        conn = get_db_connection()
        try:
            # CHECK FOR DUPLICATE barangay + contact_no
            existing = conn.execute(
                "SELECT * FROM users WHERE barangay = ? AND contact_no = ?", 
                (barangay, contact_no)
            ).fetchone()

            if existing:
                flash('This Email and Contact Number already being used', 'error')
                return render_template('SignUpPage.html',
                                       barangays=BARANGAYS_DATA,
                                       lat_lon_map=json.dumps(LAT_LON_DATA),
                                       email=email)
            else:
                # INSERT NEW USER
                conn.execute('''
                    INSERT INTO users (barangay, role, contact_no, assigned_municipality, province, password, email)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (barangay, 'barangay', contact_no, assigned_municipality, province, password, email))
                conn.commit()

                # SEND SUCCESS EMAIL
                if email:
                    try:
                        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
                        smtp_port = int(os.getenv('SMTP_PORT', 587))
                        smtp_user = os.getenv('SMTP_USERNAME')
                        smtp_pass = os.getenv('SMTP_PASSWORD')

                        msg = MIMEMultipart()
                        msg['From'] = smtp_user
                        msg['To'] = email
                        msg['Subject'] = "Log In"

                        body = """You've successfully signed up to login to your account click the link below
https://now-alert-o6l9.onrender.com/login"""

                        msg.attach(MIMEText(body, 'plain'))

                        server = smtplib.SMTP(smtp_server, smtp_port)
                        server.starttls()
                        server.login(smtp_user, smtp_pass)
                        server.sendmail(smtp_user, email, msg.as_string())
                        server.quit()
                        logger.info(f"✅ Success email sent to {email}")
                    except Exception as e:
                        logger.error(f"❌ Failed to send success email: {e}")

                flash('Account created successfully!', 'success')
                return redirect(url_for('index'))  # or wherever your login page is

        except Exception as e:
            logger.error(f"Signup failed: {e}")
            flash(f'Signup failed: {e}', 'error')
        finally:
            conn.close()

    # GET request (with pre-filled email from OTP)
    email = request.args.get('email', '')
    return render_template('SignUpPage.html',
                           barangays=BARANGAYS_DATA,
                           lat_lon_map=json.dumps(LAT_LON_DATA),
                           email=email)

# ====================== AGENCY SIGNUP ======================
@app.route('/signup_agency', methods=['GET', 'POST'])
def signup_agency():
    if request.method == 'POST':
        role = request.form.get('role', '').lower()
        municipality = request.form.get('municipality')
        contact_no = request.form.get('contact_no')
        password = request.form.get('password')
        hospital = request.form.get('assigned_hospital') if role == 'hospital' else None

        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT INTO users (role, contact_no, assigned_municipality, password, assigned_hospital)
                VALUES (?, ?, ?, ?, ?)
            ''', (role, contact_no, municipality, password, hospital))
            conn.commit()
            flash(f'{role.upper()} account created successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash('User already exists or error occurred', 'error')
        finally:
            conn.close()
    return render_template('AgencyUp.html')

# ====================== CHECK EMAIL DUPLICATE ======================
@app.route('/check_email_duplicate', methods=['POST'])
def check_email_duplicate():
    data = request.get_json()
    email = data.get('email')

    conn = get_db_connection()
    try:
        existing = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return jsonify({'exists': existing is not None})
    finally:
        conn.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True, allow_unsafe_werkzeug=True)
    # For Fly.io production
if os.environ.get('FLY_APP_NAME'):
    # Use gunicorn + eventlet on Fly.io
    from gunicorn.app.base import BaseApplication
    # (Fly.io will handle this via Procfile-like behavior)
    pass