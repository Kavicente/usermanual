from flask import Blueprint, request, redirect, url_for, render_template, flash, jsonify
from usermanual import app  # Ensure you import the app instance
import sqlite3
import os
import csv
import os
import json
import logging
from flask import request, redirect, url_for, render_template, flash
import sqlite3
import os
import csv
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

signup_bp = Blueprint('signup', __name__)

logger = logging.getLogger(__name__)

# Load barangay.csv once


def get_db_connection():
    db_path = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), 'database', 'users_web.db'))
    if not os.path.exists(db_path):
        if not os.path.exists(os.path.dirname(db_path)):
            os.makedirs(os.path.dirname(db_path))
        open(db_path, 'a').close()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_connection_to_db():
    if os.getenv('RENDER') == 'true':  # Render sets this environment variable
        db_path = '/database/users_web.db'
    else:
        db_path = os.path.join(os.path.dirname(__file__), 'data', 'users_web.db')
    app.logger.debug(f"Database path: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def load_barangays():
    barangays = {"San Pablo City": [], "Tiaong": []}
    lat_lon_map = {}

    csv_path = os.path.join(app.static_folder, 'Barangay.csv')
    
    if not os.path.exists(csv_path):
        logger.error(f"Barangay.csv not found at {csv_path}")
        return barangays, lat_lon_map

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Skip header row (Municipality,Barangay,Latitude,Longitude)

            for row in reader:
                if len(row) >= 4:
                    municipality = row[0].strip()  # Column A
                    barangay = row[1].strip()      # Column B
                    lat = row[2].strip()           # Column C
                    lon = row[3].strip()           # Column D

                    if municipality in barangays:
                        if barangay not in barangays[municipality]:
                            barangays[municipality].append(barangay)
                        lat_lon_map[barangay] = (lat, lon)

        # Sort alphabetically
        barangays["San Pablo City"].sort()
        barangays["Tiaong"].sort()

        logger.info(f"Loaded {sum(len(v) for v in barangays.values())} barangays from CSV")
    except Exception as e:
        logger.error(f"Error loading Barangay.csv: {e}")

    return barangays, lat_lon_map

# Load once at startup — with defaults if fail
try:
    BARANGAYS_DATA, LAT_LON_DATA = load_barangays()
except:
    BARANGAYS_DATA = {"San Pablo City": [], "Tiaong": []}
    LAT_LON_DATA = {}
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

@signup_bp.route('/signup_na', methods=['GET'])
def signup_na():
    return render_template('SignUpPage.html')

# ====================== NEW: CHECK DUPLICATE ROUTE ======================
@app.route('/check_duplicate', methods=['POST'])
def check_duplicate():
    data = request.get_json()
    barangay = data.get('barangay')
    contact_no = data.get('contact_no')
    email = data.get('email')

    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM users WHERE barangay = ? AND contact_no = ? AND email = ?", 
            (barangay, contact_no, email)
        ).fetchone()
        return jsonify({'exists': existing is not None})
    finally:
        conn.close()
