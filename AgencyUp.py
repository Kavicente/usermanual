from flask import request, redirect, url_for, render_template
import sqlite3
import os
from AlertNow import app  # Import the Flask app instance from AlertNow.py
import logging  # Added for debugging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'users_web.db')
    if not os.path.exists(os.path.dirname(db_path)):
        os.makedirs(os.path.dirname(db_path))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def construct_unique_id(role, assigned_municipality, contact_no):
    """Constructs a unique identifier for CDRRMO or PNP users."""
    return f"{role}_{assigned_municipality}_{contact_no}"

def signup_agency():
    if request.method == 'POST':
        role = request.form['role'].lower()
        assigned_municipality = request.form['municipality']
        contact_no = request.form['contact_no']
        password = request.form['password']
        assigned_hospital = request.form.get('assigned_hospital', '').lower() if role == 'hospital' else None
        unique_id = construct_unique_id(role, assigned_municipality=assigned_municipality, contact_no=contact_no)
        
        conn = get_db_connection()
        try:
            existing_user = conn.execute('SELECT * FROM users WHERE contact_no = ?', (contact_no,)).fetchone()
            if existing_user:
                logger.error("Signup failed: Contact number %s already exists", contact_no)
                return render_template('AgencyUp.html', error="Contact number already exists"), 400
            
            conn.execute('''
                INSERT INTO users (role, contact_no, assigned_municipality, password, assigned_hospital)
                VALUES (?, ?, ?, ?, ?)
            ''', (role, contact_no, assigned_municipality, password, assigned_hospital))
            conn.commit()
            logger.debug("User signed up successfully: %s", unique_id)
            return redirect(url_for('login_agency'))
        except sqlite3.IntegrityError as e:
            logger.error("IntegrityError during signup: %s", e)
            return render_template('AgencyUp.html', error="User already exists"), 400
        except Exception as e:
            logger.error(f"Signup failed for {unique_id}: {e}")
            return render_template('AgencyUp.html', error=f"Signup failed: {e}"), 500
        finally:
            conn.close()
    return render_template('AgencyUp.html')

def signup_muna():
    return render_template('AgencyUp.html')


