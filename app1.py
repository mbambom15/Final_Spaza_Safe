import re
from flask import Flask, render_template, Response, request, redirect, url_for, jsonify, session
from datetime import datetime, date
from flask import url_for
import mysql.connector
from mysql.connector import Error
from flask_session import Session
import os
import os
from flask import url_for, current_app
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Add this right after your imports and email configuration
EMAIL_ADDRESS = 'ggroupm9@gmail.com'
EMAIL_PASSWORD = 'zkctodisvvjocsuo'

def send_email(to, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = 'Spaza Safe <ggroupm9@gmail.com>'
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error sending email to {to}: {str(e)}")
        return False

app = Flask(__name__, template_folder='temp', static_folder='static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'fallback-secret-key-change-me')
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

def create_connection():
    return mysql.connector.connect(
        host="spazasafeconnection.czg4wmsiihb0.eu-west-3.rds.amazonaws.com",      
        user="bambi15",    
        password="Mbambo1307#a",
        database="spaza_safe"      
    )

# Global variables for barcode scanning
scanned_data = None
camera_active = False
cap = None


@app.route('/clear_scanned_data')
def clear_scanned_data():
    global scanned_data, camera_active
    scanned_data = None
    camera_active = True  # Ensure camera stays active
    return jsonify({"status": "Scanned data cleared", "camera_active": camera_active})

#handle all new customer routes such as login and signup, plus linking pages here
@app.route('/login_customer', methods=['GET', 'POST'])
def login_customer():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not all([email, password]):
            return jsonify({"success": False, "message": "All fields are required"}), 400

        connection = None
        try:
            connection = create_connection()
            cursor = connection.cursor(dictionary=True)
            
            # Check if customer exists
            cursor.execute("""
                SELECT * FROM customer 
                WHERE email = %s AND cpassword = %s
            """, (email, password))
            
            customer = cursor.fetchone()
            
            if customer:
                # Update last login timestamp
                cursor.execute("""
                    UPDATE customer 
                    SET last_login = CURRENT_TIMESTAMP 
                    WHERE cust_id = %s
                """, (customer['cust_id'],))
                connection.commit()
                
                # Store customer ID in session
                session['customer_id'] = customer['cust_id']
                session['logged_in'] = True
                
                return jsonify({
                    "success": True,
                    "message": "Login successful",
                    "redirect": url_for('dashboard'),
                    "user": {
                        "id": customer['cust_id'],
                        "email": customer['email'],
                        "last_login": customer['last_login'].strftime('%Y-%m-%d %H:%M:%S') if customer['last_login'] else None
                    }
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "Invalid email or password"
                }), 401

        except Error as e:
            return jsonify({
                "success": False,
                "message": f"Database error: {str(e)}"
            }), 500

        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

    return render_template('login_customer.html')


@app.route('/signup_customer', methods=['GET', 'POST'])
def signup_customer():
    if request.method == 'POST':
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        # Validation
        if not all([email, phone, password, confirm]):
            return jsonify({"success": False, "message": "All fields are required"}), 400

        if password != confirm:
            return jsonify({"success": False, "message": "Passwords do not match"}), 400

        if len(phone) != 10 or not phone.isdigit():
            return jsonify({"success": False, "message": "Phone number must be 10 digits"}), 400

        # Password validation (server-side)
        if len(password) < 8 or len(password) > 12:
            return jsonify({"success": False, "message": "Password must be 8-12 characters"}), 400
        
        if not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password):
            return jsonify({"success": False, "message": "Password must contain both uppercase and lowercase letters"}), 400
        
        if not re.search(r'\d', password):
            return jsonify({"success": False, "message": "Password must contain at least one number"}), 400
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', password):
            return jsonify({"success": False, "message": "Password must contain at least one special character"}), 400

        connection = None
        try:
            connection = create_connection()
            cursor = connection.cursor(dictionary=True)

            # Check if email already exists
            cursor.execute("SELECT email FROM customer WHERE email = %s", (email,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "Email already registered"}), 400

            # Insert new customer with explicit creation date
            query = """
                INSERT INTO customer (email, telephone, cpassword, creationdate)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            """
            cursor.execute(query, (email, phone, password))
            connection.commit()
            
            # Get the newly created customer
            cursor.execute("SELECT * FROM customer WHERE email = %s", (email,))
            new_customer = cursor.fetchone()

            return jsonify({
                "success": True,
                "message": "Account created successfully!",
                "redirect": url_for('login_customer'),
                "user": {
                    "id": new_customer['cust_id'],
                    "email": new_customer['email'],
                    "created": new_customer['creationdate'].strftime('%Y-%m-%d %H:%M:%S')
                }
            })

        except Error as e:
            if connection:
                connection.rollback()
            return jsonify({
                "success": False,
                "message": f"Registration failed: {str(e)}"
            }), 500

        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    # Handle GET request - render the signup form
    return render_template('signup_customer.html')

@app.route('/reset_password', methods=['POST'])
def reset_password_customer():
    data = request.json
    email = data.get('email')
    new_password = data.get('new_password')

    if not all([email, new_password]):
        return jsonify({
            'success': False,
            'message': 'Email and new password are required'
        }), 400

    # Password validation (same as signup)
    if len(new_password) < 8 or len(new_password) > 12:
        return jsonify({
            'success': False,
            'message': 'Password must be 8-12 characters'
        }), 400
    
    if not re.search(r'[A-Z]', new_password) or not re.search(r'[a-z]', new_password):
        return jsonify({
            'success': False,
            'message': 'Password must contain both uppercase and lowercase letters'
        }), 400
    
    if not re.search(r'\d', new_password):
        return jsonify({
            'success': False,
            'message': 'Password must contain at least one number'
        }), 400
    
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', new_password):
        return jsonify({
            'success': False,
            'message': 'Password must contain at least one special character'
        }), 400

    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()

        # Check if email exists
        cursor.execute("SELECT email FROM customer WHERE email = %s", (email,))
        if not cursor.fetchone():
            return jsonify({
                'success': False,
                'message': 'Customer not found'
            }), 404

        # Update password
        query = "UPDATE customer SET cpassword = %s WHERE email = %s"
        cursor.execute(query, (new_password, email))
        connection.commit()

        return jsonify({
            'success': True,
            'message': 'Password updated successfully'
        })

    except Error as e:
        if connection:
            connection.rollback()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

#customer products and analytics
@app.route('/check_session', methods=['GET'])
def check_session():
    if 'customer_id' in session:
        return jsonify({
            "logged_in": True,
            "customer_id": session['customer_id']
        })
    else:
        return jsonify({"logged_in": False})

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'customer_id' not in session:
        return jsonify({"success": False, "message": "Please login first"}), 401
        
    data = request.get_json()
    barcode = data.get('barcode')
    business_reg_number = data.get('business_reg_number')
    quantity = data.get('quantity', 1)  # Default to 1 if not specified
    
    if not all([barcode, business_reg_number]):
        return jsonify({"success": False, "message": "Missing required fields"}), 400
    
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        # 1. Check if product exists in the store's inventory
        cursor.execute("""
            SELECT si.shop_price, si.stock_quantity 
            FROM shop_inventory si
            WHERE si.prod_barcode = %s AND si.business_reg_number = %s
        """, (barcode, business_reg_number))
        
        inventory_item = cursor.fetchone()
        
        if not inventory_item:
            return jsonify({"success": False, "message": "Product not found in store inventory"}), 404
        
        if inventory_item['stock_quantity'] < quantity:
            return jsonify({"success": False, "message": "Not enough stock available"}), 400
        
        # 2. Get or create active cart for customer at this store
        cursor.execute("""
            SELECT cart_id FROM shopping_cart
            WHERE cust_id = %s AND business_reg_number = %s AND is_active = TRUE
        """, (session['customer_id'], business_reg_number))
        
        cart = cursor.fetchone()
        
        if not cart:
            # Create new cart
            cursor.execute("""
                INSERT INTO shopping_cart (cust_id, business_reg_number)
                VALUES (%s, %s)
            """, (session['customer_id'], business_reg_number))
            cart_id = cursor.lastrowid
        else:
            cart_id = cart['cart_id']
        
        # 3. Check if product already in cart
        cursor.execute("""
            SELECT item_id, quantity FROM cart_items
            WHERE cart_id = %s AND prod_barcode = %s
        """, (cart_id, barcode))
        
        existing_item = cursor.fetchone()
        
        if existing_item:
            # Update quantity
            new_quantity = existing_item['quantity'] + quantity
            cursor.execute("""
                UPDATE cart_items
                SET quantity = %s
                WHERE item_id = %s
            """, (new_quantity, existing_item['item_id']))
        else:
            # Add new item
            cursor.execute("""
                INSERT INTO cart_items (cart_id, prod_barcode, quantity, price_per_unit)
                VALUES (%s, %s, %s, %s)
            """, (cart_id, barcode, quantity, inventory_item['shop_price']))
        
        # 4. Record analytics
        cursor.execute("""
            INSERT INTO product_analytics (cust_id, prod_barcode, action_type, store_id)
            VALUES (%s, %s, 'ADD_TO_CART', %s)
        """, (session['customer_id'], barcode, business_reg_number))
        
        connection.commit()
        
        return jsonify({
            "success": True,
            "message": "Product added to cart",
            "cart_id": cart_id
        })
        
    except Error as e:
        if connection:
            connection.rollback()
        return jsonify({
            "success": False,
            "message": f"Database error: {str(e)}"
        }), 500
        
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/get_cart', methods=['GET'])
def get_cart():
    business_reg_number = request.args.get('business_reg_number')
    
    if not business_reg_number:
        return jsonify({"success": False, "message": "Store ID is required"}), 400
    
    # Handle both logged in and not logged in cases
    customer_id = session.get('customer_id')
    
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        cart = None
        if customer_id:
            # Get active cart for logged in user
            cursor.execute("""
                SELECT cart_id FROM shopping_cart
                WHERE cust_id = %s AND business_reg_number = %s AND is_active = TRUE
            """, (customer_id, business_reg_number))
            cart = cursor.fetchone()
        
        if not cart:
            # Return empty cart for non-logged in users
            return jsonify({
                "success": True,
                "cart": None,
                "total": 0
            })
        
        # Get cart items with product details
        cursor.execute("""
            SELECT 
                ci.item_id,
                ci.prod_barcode,
                p.prod_name,
                p.prod_image_url,
                ci.quantity,
                ci.price_per_unit,
                (ci.quantity * ci.price_per_unit) AS item_total
            FROM cart_items ci
            JOIN product p ON ci.prod_barcode = p.prod_barcode
            WHERE ci.cart_id = %s
        """, (cart['cart_id'],))
        
        items = cursor.fetchall()
        
        # Calculate total
        total = sum(item['item_total'] for item in items)
        
        return jsonify({
        "success": True,
        "cart": {
            "cart_id": cart['cart_id'],
            "items": [{
                **item,
                "quantity": int(item['quantity']),
                "price_per_unit": float(item['price_per_unit']),
                "item_total": float(item['item_total'])
            } for item in items],
            "total": float(total)
        }
    })
        
    except Error as e:
        return jsonify({
            "success": False,
            "message": f"Database error: {str(e)}"
        }), 500
        
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'customer_id' not in session:
        return jsonify({"success": False, "message": "Please login first"}), 401
        
    data = request.get_json()
    cart_id = data.get('cart_id')
    
    if not cart_id:
        return jsonify({"success": False, "message": "Cart ID is required"}), 400
    
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        # 1. Verify cart belongs to customer and is active
        cursor.execute("""
            SELECT business_reg_number FROM shopping_cart
            WHERE cart_id = %s AND cust_id = %s AND is_active = TRUE
        """, (cart_id, session['customer_id']))
        
        cart = cursor.fetchone()
        
        if not cart:
            return jsonify({"success": False, "message": "Invalid cart"}), 404
        
        # 2. Get cart items to verify stock
        cursor.execute("""
            SELECT ci.prod_barcode, ci.quantity, si.stock_quantity
            FROM cart_items ci
            JOIN shop_inventory si ON ci.prod_barcode = si.prod_barcode 
                AND si.business_reg_number = %s
            WHERE ci.cart_id = %s
        """, (cart['business_reg_number'], cart_id))
        
        items = cursor.fetchall()
        
        # Check stock for all items
        out_of_stock = []
        for item in items:
            if item['stock_quantity'] < item['quantity']:
                out_of_stock.append({
                    "barcode": item['prod_barcode'],
                    "requested": item['quantity'],
                    "available": item['stock_quantity']
                })
        
        if out_of_stock:
            return jsonify({
                "success": False,
                "message": "Some items are out of stock",
                "out_of_stock": out_of_stock
            }), 400
        
        # 3. Process checkout (in a real app, this would involve payment processing)
        # For now, we'll just:
        # - Update inventory
        # - Mark cart as inactive
        # - Record analytics
        
        # Update inventory
        for item in items:
            cursor.execute("""
                UPDATE shop_inventory
                SET stock_quantity = stock_quantity - %s
                WHERE prod_barcode = %s AND business_reg_number = %s
            """, (item['quantity'], item['prod_barcode'], cart['business_reg_number']))
            
            # Record purchase analytics
            cursor.execute("""
                INSERT INTO product_analytics (cust_id, prod_barcode, action_type, store_id)
                VALUES (%s, %s, 'PURCHASED', %s)
            """, (session['customer_id'], item['prod_barcode'], cart['business_reg_number']))
        
        # Mark cart as inactive
        cursor.execute("""
            UPDATE shopping_cart
            SET is_active = FALSE
            WHERE cart_id = %s
        """, (cart_id,))
        
        connection.commit()
        
        return jsonify({
        "success": True,
        "message": "Checkout successful",
        "order_id": cart_id,  # Keep this
        "order_number": f"ORD-{cart_id:06d}"  # Add a formatted order number
    })
        
    except Error as e:
        if connection:
            connection.rollback()
        return jsonify({
            "success": False,
            "message": f"Database error: {str(e)}"
        }), 500
        
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            
def send_report_emails(report_data, customer_email):
    # Email to customer
    send_email(
        to=customer_email,
        subject="Expired Product Report Submitted",
        body=f"Thank you for reporting expired product {report_data['product_name']} at {report_data['shop_name']}."
    )

    # Email to government
    gov_email = "mbambom15@gmail.com"
    send_email(
        to=gov_email,
        subject=f"Expired Product Report - {report_data['shop_name']}",
        body=f"""
        New expired product report:
        
        Product: {report_data['product_name']} 
        Barcode: {report_data['barcode']}
        Expiry Date: {report_data['expiry_date']}
        Shop: {report_data['shop_name']} 
        Location: {report_data['shop_location']}
        Business Reg: {report_data['business_reg_number']}
        Reported by: {customer_email}
        """
    )

@app.route('/report_expired', methods=['POST'])
def report_expired_product():
    if 'customer_id' not in session:
        return jsonify({"success": False, "message": "Please login first"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400
        
    # Extract required fields
    required_fields = ['barcode', 'product_name', 'expiry_date', 
                      'business_reg_number', 'shop_name', 'shop_location']  # Added shop_location
    if not all(field in data for field in required_fields):
        return jsonify({"success": False, "message": "Missing required fields"}), 400

    # Get customer email
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT email FROM customer WHERE cust_id = %s", 
                      (session['customer_id'],))
        customer = cursor.fetchone()
        
        if not customer:
            return jsonify({"success": False, "message": "Customer not found"}), 404
            
        customer_email = customer['email']
        
        # Insert report into database
        report_query = """
        INSERT INTO expired_product_reports 
            (product_barcode, product_name, expiry_date, 
             business_reg_number, shop_name, shop_location,  # Added shop_location
             customer_id, customer_email) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)  # Added extra value
        """
        cursor.execute(report_query, (
            data['barcode'],
            data['product_name'],
            data['expiry_date'],
            data['business_reg_number'],
            data['shop_name'],
            data['shop_location'],  # New field
            session['customer_id'],
            customer_email
        ))
        connection.commit()
        
        # Send emails
        send_report_emails(data, customer_email)
        
        return jsonify({
            "success": True,
            "message": "Report submitted successfully"
        })
        
    except Error as e:
        if connection:
            connection.rollback()
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
#Report generating for customer history
@app.route('/history')
def history():
    # Ensure customer is logged in
    if 'customer_id' not in session or not session.get('logged_in'):
        return redirect(url_for('login_customer'))
    
    return render_template('customer_history.html')

@app.route('/customer_history')
def customer_history():
    # Ensure customer is logged in
    if 'customer_id' not in session or not session.get('logged_in'):
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Query the CustomerFullHistory view
        cursor.execute("""
            SELECT * FROM customerfullhistory
            WHERE cust_id = %s
            ORDER BY COALESCE(purchase_date, report_date) DESC
        """, (session['customer_id'],))
        
        history_data = cursor.fetchall()
        
        return jsonify({
            "success": True,
            "data": history_data
        })
        
    except Exception as e:
        print(f"Error fetching customer history: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
    
@app.route('/update_password_owner', methods=['GET', 'POST'])
def update_password_owner():
    if request.method == 'POST':
        username = request.form.get('owner_name')
        new_password = request.form.get('new_password')

        if not all([username, new_password]):
            return redirect(url_for('update_password_owner', message="Username and new password are required"))

        # Password validation
        if len(new_password) < 8 or len(new_password) > 12:
            return redirect(url_for('update_password_owner', message="Password must be 8-12 characters"))
        
        if not re.search(r'[A-Z]', new_password) or not re.search(r'[a-z]', new_password):
            return redirect(url_for('update_password_owner', message="Password must contain both uppercase and lowercase letters"))
        
        if not re.search(r'\d', new_password):
            return redirect(url_for('update_password_owner', message="Password must contain at least one number"))
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'"\\|,.<>\/?]', new_password):
            return redirect(url_for('update_password_owner', message="Password must contain at least one special character"))

        connection = None
        try:
            connection = create_connection()
            cursor = connection.cursor()

            # Check if owner exists
            cursor.execute("SELECT owner_id FROM spaza_owner WHERE oname = %s", (username,))
            if not cursor.fetchone():
                return redirect(url_for('update_password_owner', message="Shop owner not found"))

            # Update password
            query = "UPDATE spaza_owner SET opassword = %s WHERE oname = %s"
            cursor.execute(query, (new_password, username))
            connection.commit()

            if cursor.rowcount == 0:
                return redirect(url_for('update_password_owner', message="Password update failed"))

            return redirect(url_for('login_spazaOwner', message="Password updated successfully"))

        except Error as e:
            if connection:
                connection.rollback()
            return redirect(url_for('update_password_owner', message=f"Error: {str(e)}"))

        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

    return render_template('update_passwordo.html')

@app.route('/update_password_manufacturer', methods=['GET', 'POST'])
def update_password_manufacturer():
    if request.method == 'POST':
        license_key = request.form.get('license_key')
        new_password = request.form.get('new_password')

        if not all([license_key, new_password]):
            return redirect(url_for('update_password_manufacturer', message="License key and new password are required"))

        # Password validation
        if len(new_password) < 8 or len(new_password) > 12:
            return redirect(url_for('update_password_manufacturer', message="Password must be 8-12 characters"))
        
        if not re.search(r'[A-Z]', new_password) or not re.search(r'[a-z]', new_password):
            return redirect(url_for('update_password_manufacturer', message="Password must contain both uppercase and lowercase letters"))
        
        if not re.search(r'\d', new_password):
            return redirect(url_for('update_password_manufacturer', message="Password must contain at least one number"))
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'"\\|,.<>\/?]', new_password):
            return redirect(url_for('update_password_manufacturer', message="Password must contain at least one special character"))

        connection = None
        try:
            connection = create_connection()
            cursor = connection.cursor()

            # Check if manufacturer exists
            cursor.execute("SELECT license_key FROM manufacturer WHERE license_key = %s", (license_key,))
            if not cursor.fetchone():
                return redirect(url_for('update_password_manufacturer', message="Manufacturer not found"))

            # Update password
            query = "UPDATE manufacturer SET mpassword = %s WHERE license_key = %s"
            cursor.execute(query, (new_password, license_key))
            connection.commit()

            if cursor.rowcount == 0:
                return redirect(url_for('update_password_manufacturer', message="Password update failed"))

            return redirect(url_for('login_manufacturer', message="Password updated successfully"))

        except Error as e:
            if connection:
                connection.rollback()
            return redirect(url_for('update_password_manufacturer', message=f"Error: {str(e)}"))

        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

    return render_template('update_password.html')

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/spazalogin')
def spazalogin():
    return render_template('spazalogin.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/scan')
def scan():
    return render_template('scan.html')

@app.route('/login_spazaOwner', methods=['GET', 'POST'])
def login_spazaOwner():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not all([username, password]):
            return jsonify({"success": False, "message": "All fields are required"}), 400

        connection = None
        try:
            connection = create_connection()
            cursor = connection.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT o.*, s.business_reg_number 
                FROM spaza_owner o
                JOIN spaza_shop s ON o.business_reg_number = s.business_reg_number
                WHERE (o.oname = %s OR o.business_name = %s) AND o.opassword = %s
            """, (username, username, password))
            
            shop_owner = cursor.fetchone()
            
            if shop_owner:
                # Update last_login timestamp
                cursor.execute("""
                    UPDATE spaza_owner 
                    SET last_login = CURRENT_TIMESTAMP
                    WHERE owner_id = %s
                """, (shop_owner['owner_id'],))
                connection.commit()
                
                # Set session variables
                session['owner_id'] = shop_owner['owner_id']
                session['business_reg_number'] = shop_owner['business_reg_number']
                session['business_name'] = shop_owner['business_name']
                
                return jsonify({
                    "success": True,
                    "message": "Login successful",
                    "redirect": url_for('shopowner'),
                    "user": {
                        "id": shop_owner['owner_id'],
                        "name": shop_owner['business_name'],
                        "business_reg_number": shop_owner['business_reg_number']
                    }
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "Invalid credentials"
                }), 401

        except Error as e:
            return jsonify({
                "success": False,
                "message": f"Database error: {str(e)}"
            }), 500
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

    return render_template('login_spazaOwner.html')

@app.route('/logout_spaza_owner')
def logout_spaza_owner():
    # Clear session data
    session.pop('owner_id', None)
    session.pop('business_reg_number', None)
    session.pop('business_name', None)
    
    # Redirect to home page
    return redirect(url_for('home'))
            
@app.route('/login_manufacturer', methods=['GET', 'POST'])
def login_manufacturer():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not all([username, password]):
            return jsonify({"success": False, "message": "All fields are required"}), 400

        connection = None
        try:
            connection = create_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute("""
                SELECT license_key, company_name FROM manufacturer
                WHERE license_key = %s AND mpassword = %s
            """, (username, password))

            manufacturer = cursor.fetchone()

            if manufacturer:
                # Update last_login timestamp upon successful login
                cursor.execute("""
                    UPDATE manufacturer 
                    SET last_login = CURRENT_TIMESTAMP 
                    WHERE license_key = %s
                """, (username,))
                connection.commit()

                return jsonify({
                    "success": True,
                    "message": "Login successful",
                    "redirect": url_for('manudashboard'),
                    "user": {
                        "id": manufacturer['license_key'],
                        "name": manufacturer['company_name']
                    }
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "Invalid credentials"
                }), 401

        except Error as e:
            return jsonify({
                "success": False,
                "message": f"Database error: {str(e)}"
            }), 500
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

    return render_template('login_manufacturer.html')

@app.route('/signup_manufacturer', methods=['GET', 'POST'])
def signup_manufacturer():
    if request.method == 'POST':
        license_key = request.form.get('license_key')
        company_name = request.form.get('company_name')
        address = request.form.get('address')
        location = request.form.get('location')
        password = request.form.get('password')

        if not all([license_key, company_name, address, location, password]):
            return jsonify({
                "success": False,
                "message": "All fields are required"
            }), 400

        # Password validation
        if len(password) < 8 or len(password) > 12:
            return jsonify({
                "success": False,
                "message": "Password must be 8-12 characters"
            }), 400
        
        if not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password):
            return jsonify({
                "success": False,
                "message": "Password must contain both uppercase and lowercase letters"
            }), 400
        
        if not re.search(r'\d', password):
            return jsonify({
                "success": False,
                "message": "Password must contain at least one number"
            }), 400
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'"\\|,.<>\/?]', password):
            return jsonify({
                "success": False,
                "message": "Password must contain at least one special character"
            }), 400

        connection = None
        try:
            connection = create_connection()
            cursor = connection.cursor()

            cursor.execute("SELECT license_key FROM manufacturer WHERE license_key = %s", (license_key,))
            if cursor.fetchone():
                return jsonify({
                    "success": False,
                    "message": "License key already registered"
                }), 400

            # creationdate will be automatically set by DEFAULT CURRENT_TIMESTAMP
            query = """
                INSERT INTO manufacturer (license_key, company_name, address, location, mpassword)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (license_key, company_name, address, location, password))
            connection.commit()

            return jsonify({
                "success": True,
                "message": "Registration successful",
                "redirect": url_for('login_manufacturer')
            })

        except Error as e:
            if connection:
                connection.rollback()
            return jsonify({
                "success": False,
                "message": f"Database error: {str(e)}"
            }), 500
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

    return render_template('signup_manufacturer.html')

@app.route('/signup_spazaOwner', methods=['GET', 'POST'])
def signup_spazaOwner():
    if request.method == 'POST':
        form_data = {
            'oname': request.form.get('oname'),
            'opassword': request.form.get('opassword'),
            'phone_number': request.form.get('phone_number'),
            'business_name': request.form.get('business_name'),
            'business_reg_number': request.form.get('business_reg_number'),
            'location': request.form.get('location')
        }

        # Validate all required fields
        missing_fields = [field for field, value in form_data.items() if not value and field != 'phone_number']
        if missing_fields:
            return jsonify({
                "success": False,
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400

        # Password validation
        password = form_data['opassword']
        if len(password) < 8 or len(password) > 12:
            return jsonify({
                "success": False,
                "message": "Password must be 8-12 characters"
            }), 400
        
        if not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password):
            return jsonify({
                "success": False,
                "message": "Password must contain both uppercase and lowercase letters"
            }), 400
        
        if not re.search(r'\d', password):
            return jsonify({
                "success": False,
                "message": "Password must contain at least one number"
            }), 400
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'"\\|,.<>\/?]', password):
            return jsonify({
                "success": False,
                "message": "Password must contain at least one special character"
            }), 400

        connection = None
        try:
            connection = create_connection()
            cursor = connection.cursor()

            # Check if business registration number already exists
            cursor.execute("""
                SELECT business_reg_number 
                FROM spaza_owner 
                WHERE business_reg_number = %s
            """, (form_data['business_reg_number'],))
            
            if cursor.fetchone():
                return jsonify({
                    "success": False,
                    "message": "Business registration number already exists"
                }), 400

            # Insert new shop owner
            cursor.execute("""
                INSERT INTO spaza_owner 
                (oname, opassword, phone_number, business_name, business_reg_number)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                form_data['oname'],
                form_data['opassword'],
                form_data['phone_number'],
                form_data['business_name'],
                form_data['business_reg_number']
            ))
            
            # Get the newly created owner_id
            owner_id = cursor.lastrowid
            
            # Insert corresponding shop using the same business_reg_number
            cursor.execute("""
                INSERT INTO spaza_shop 
                (business_reg_number, sname, owner_id, location)
                VALUES (%s, %s, %s, %s)
            """, (
                form_data['business_reg_number'],
                form_data['business_name'],
                owner_id,
                form_data['location']
            ))
            
            connection.commit()

            return jsonify({
                "success": True,
                "message": "Registration successful! Redirecting to login...",
                "redirect": url_for('login_spazaOwner'),
                "business_reg_number": form_data['business_reg_number']
            })

        except Exception as e:
            if connection:
                connection.rollback()
            return jsonify({
                "success": False,
                "message": f"Registration failed: {str(e)}"
            }), 500

        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

    return render_template('signup_spazaOwner.html')

@app.route('/logout_manufacturer', methods=['POST'])
def logout_manufacturer():
    # Clear any manufacturer session data if needed
    session.pop('manufacturer_id', None)
    session.pop('license_key', None)
    return jsonify({"success": True, "message": "Logged out successfully"})
@app.route('/logout')
def logout():
    # Clear all session data
    session.clear()
    return redirect(url_for('home'))

@app.route('/manudashboard')
def manudashboard():
    return render_template('manudashboard.html')
# Product dictionary in Flask app

# Update the product database with more products
PRODUCT_DATABASE = {
    '6001052001049': {
        'prod_name': 'Bokomo Weet-Bix',
        'prod_price': 55.00,
        'prod_expiry_date': '2025-06-20',
        'prod_manu_date': '2025-03-25',
        'prod_quantity': 50,
    },
    '6001038284909': {
        'prod_name': 'Jungle Oats',
        'prod_price': 48.00,
        'prod_expiry_date': '2026-03-04',
        'prod_manu_date': '2025-03-03',
        'prod_quantity': 100
    },
    '6002310013569': {
        'prod_name': 'Pride Popcorn',
        'prod_price': 25.00,
        'prod_expiry_date': '2025-07-15',
        'prod_manu_date': '2023-04-25',
        'prod_quantity': 100
    },
    '5060335632715': {
        'prod_name': 'Monster The Doctor',
        'prod_price': 20.00,
        'prod_expiry_date': '2025-06-15',
        'prod_manu_date': '2023-06-15',
        'prod_quantity': 100
    },
    '9002490100070': {
        'prod_name': 'Red Bull  Energy Drink',
        'prod_price': 20.00,
        'prod_expiry_date': '2025-06-30',
        'prod_manu_date': '2023-06-15',
        'prod_quantity': 100
    },
    '6002100014004': {
        'prod_name': 'Paramalat EverFresh Milk',
        'prod_price': 25.00,
        'prod_expiry_date': '2025-06-09',
        'prod_manu_date': '2024-06-07',
        'prod_quantity': 100
    },
    '54490482': {
        'prod_name': 'Powerade Mountain Blast',
        'prod_price': 18.00,
        'prod_expiry_date': '2025-06-25',
        'prod_manu_date': '2024-06-07',
        'prod_quantity': 50
    },
     '6006822000536': {
        'prod_name': 'Laager Pure Rooibos',
        'prod_price': 40.00,
        'prod_expiry_date': '2026-10-16',
        'prod_manu_date': '2024-10-16',
        'prod_quantity': 100
    },
    '6001087359610': {
        'prod_name': 'Knorr Rich Oxtail Soup',
        'prod_price': 7.00,
        'prod_expiry_date': '2026-01-11',
        'prod_manu_date': '2024-01-16',
        'prod_quantity': 100
    },
    '6009708461902': {
        'prod_name': 'Nutriday Strawberry Yoghurt',
        'prod_price': 26.00,
        'prod_expiry_date': '2025-06-28',
        'prod_manu_date': '2025-04-28',
        'prod_quantity': 100
    },
    '6001323106718': {
        'prod_name': 'Golden Star Instant Yeast',
        'prod_price': 6.00,
        'prod_expiry_date': '2025-06-28',
        'prod_manu_date': '2025-04-28',
        'prod_quantity': 100
    },
    '6001056453004': {
        'prod_name': 'Blue Label Marie Biscuits',
        'prod_price': 22.00,
        'prod_expiry_date': '2025-06-30',
        'prod_manu_date': '2025-04-28',
        'prod_quantity': 50
    },
}

#duplicate get product for spazashop view
@app.route('/get_product_dataspz/<barcode>')
def get_product_dataspz(barcode):
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get product including license key
        query = "SELECT *, license_key AS manufacturer_license FROM product WHERE prod_barcode = %s"
        cursor.execute(query, (barcode,))
        product = cursor.fetchone()
        
        if product:
            return jsonify({"success": True, "product": product})
        else:
            return jsonify({"success": False, "message": "Product not found"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            

@app.route('/get_product_data/<barcode>')
def get_product_data(barcode):
    product = PRODUCT_DATABASE.get(barcode)
    if product:
        # Generate image URL and check existence
        image_filename = f"{barcode}.png"
        static_folder = current_app.static_folder
        image_path = os.path.join(static_folder, 'images', 'products', image_filename)
        image_exists = os.path.exists(image_path)
        
        # Generate URL (Flask will handle the static path)
        image_url = url_for('static', filename=f'images/products/{image_filename}')
        
        return jsonify({
            "success": True,
            "product": {
                "prod_name": product['prod_name'],
                "prod_price": product['prod_price'],
                "prod_expiry_date": product['prod_expiry_date'],
                "prod_manu_date": product['prod_manu_date'],
                "prod_quantity": product['prod_quantity'],
                "prod_image_url": image_url,
                "image_exists": image_exists
            }
        })
    return jsonify({"success": False, "message": "Product not found"})

@app.route('/stop_camera')
def stop_camera():
    global camera_active, cap
    camera_active = False
    if cap is not None:
        cap.release()
        cap = None
    return jsonify({"status": "Camera stopped"})

#Add product for manufacturrer
@app.route('/add_product', methods=['POST'])
def add_product():
    data = request.json
    connection = None

    try:
        product_info = PRODUCT_DATABASE.get(data['barcode'])
        if not product_info:
            return jsonify({"success": False, "message": "Product not found in database"}), 404

        expiry_date = datetime.strptime(product_info['prod_expiry_date'], '%Y-%m-%d').date()
        today = datetime.now().date()

        if expiry_date < today:
            return jsonify({
                "success": False,
                "message": f"Cannot add product - it expired on {product_info['prod_expiry_date']}"
            }), 400

        # Generate relative image URL (works for both local and production)
        image_filename = f"{data['barcode']}.png"
        image_url = url_for('static', filename=f'images/products/{image_filename}')  # Removed _external=True
        
        # Check if image exists in static folder
        static_folder = current_app.static_folder
        image_path = os.path.join(static_folder, 'images', 'products', image_filename)
        
        # Only store URL if image exists
        if not os.path.exists(image_path):
            image_url = ""

        connection = create_connection()
        cursor = connection.cursor()

        # Check for existing product
        cursor.execute("""
            SELECT prod_barcode FROM product 
            WHERE prod_barcode = %s AND license_key = %s
        """, (data['barcode'], data['license_key']))

        if cursor.fetchone():
            return jsonify({"success": False, "message": "You have already added this product"})

        # Insert product with image URL
        query = """
        INSERT INTO product (prod_barcode, prod_name, prod_price, 
                           prod_expiry_date, prod_manu_date, 
                           license_key, prod_quantity, time_created, prod_image_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            data['barcode'],
            product_info['prod_name'],
            product_info['prod_price'],
            product_info['prod_expiry_date'],
            product_info['prod_manu_date'],
            data['license_key'],
            product_info['prod_quantity'],
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            image_url  # Now stores relative URL or empty string
        ))

        connection.commit()
        return jsonify({
            "success": True,
            "message": "Product added successfully",
            "product": {
                "prod_barcode": data['barcode'],
                "prod_name": product_info['prod_name'],
                "prod_price": product_info['prod_price'],
                "prod_expiry_date": product_info['prod_expiry_date'],
                "prod_quantity": product_info['prod_quantity'],
                "prod_image_url": image_url  # Returns the relative URL
            }
        })
    except Error as e:
        if connection:
            connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()


#Add the update route for the manufacturer prices here
@app.route('/update_product', methods=['PUT'])
def update_product():
    data = request.json
    connection = None
    
    if not data or 'barcode' not in data or 'price' not in data or 'license_key' not in data:  # Changed here
        return jsonify({"success": False, "message": "Invalid request data"}), 400

    try:
        connection = create_connection()
        cursor = connection.cursor()

        query = """
        UPDATE product
        SET prod_price = %s
        WHERE prod_barcode = %s AND license_key = %s  # Changed here
        """
        cursor.execute(query, (
            data['price'],
            data['barcode'],
            data['license_key']  # Changed here
        ))

        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "Product not found or not owned by manufacturer"}), 404

        connection.commit()
        return jsonify({"success": True, "message": "Product updated successfully"})

    except Error as e:
        if connection:
            connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            
# ADD the delete route for the manufacturer here
@app.route('/delete_product/<barcode>', methods=['DELETE'])
def delete_product(barcode):
    license_key = request.args.get('license_key')  # Changed here
    
    if not license_key:
        return jsonify({"success": False, "message": "License key is required"}), 400  # Changed here

    try:
        connection = create_connection()
        cursor = connection.cursor()

        query = "DELETE FROM product WHERE prod_barcode = %s AND license_key = %s"  # Changed here
        cursor.execute(query, (barcode, license_key))  # Changed here

        if cursor.rowcount == 0:
            return jsonify({"success": False, "message": "Product not found or not owned by manufacturer"}), 404

        connection.commit()
        return jsonify({"success": True, "message": "Product deleted successfully"})

    except Error as e:
        if connection:
            connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/get_products')
def get_products():
    license_key = request.args.get('license_key')  # Changed from manufacturer_id
    
    if not license_key:
        return jsonify({"success": False, "message": "License key is required"}), 400

    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Verify the manufacturer exists 
        cursor.execute("SELECT license_key FROM manufacturer WHERE license_key = %s", (license_key,))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": "Invalid license key"}), 401
        
        # Get only products belonging to this manufacturer
        query = "SELECT * FROM product WHERE license_key = %s"
        cursor.execute(query, (license_key,))
        products = cursor.fetchall()
        
        return jsonify(products)
        
    except Error as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
#this is also a manufacturer getting products
@app.route('/get_product')
def get_product():
    barcode = request.args.get('barcode')
    license_key = request.args.get('license_key')  # Changed here
    
    if not all([barcode, license_key]):
        return jsonify({"success": False, "message": "Barcode and license key are required"}), 400  # Changed here
    
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        query = "SELECT * FROM product WHERE prod_barcode = %s AND license_key = %s"  # Changed here
        cursor.execute(query, (barcode, license_key))  # Changed here
        product = cursor.fetchone()
        
        if not product:
            return jsonify({"success": False, "message": "Product not found"}), 404
        
        return jsonify(product)
        
    except Error as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/order_stock')
def order_stock():
    return render_template('order_stock.html')


@app.route('/shopowner.html')
def shopowner():
    return render_template('shopowner.html')


# This route queries MySQL based on the scanned barcode
from flask import request, jsonify

@app.route('/get_stores')
def get_stores():
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute('''
            SELECT
                s.business_reg_number,
                s.sname as shop_name,
                s.location,  -- Ensure location is selected
                CONCAT(s.sname, ' (', s.business_reg_number, ')') as display_name,
                so.business_name
            FROM spaza_shop s
            JOIN spaza_owner so ON s.owner_id = so.owner_id
            WHERE s.location IS NOT NULL  -- Exclude null locations
        ''')
        stores = cursor.fetchall()
        
        if not stores:
            return jsonify({"error": "No stores found"}), 404
            
        return jsonify(stores)
        
    except Exception as e:
        print(f"Error fetching stores: {str(e)}")
        return jsonify({"error": str(e)}), 500
    finally:
        if connection:
            connection.close()
            
@app.route('/scan_barcode', methods=['POST'])
def scan_barcode():
    data = request.get_json()
    barcode = data.get("barcode")
    business_reg_number = data.get("business_reg_number")

    if not barcode:
        return jsonify({"error": "No barcode received"}), 400

    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        # First check if product exists in the selected store's inventory
        if business_reg_number:
            inventory_query = """
                SELECT 
                    p.*, 
                    m.company_name, m.address, m.location, m.license_key,
                    si.shop_price, 
                    si.stock_quantity,
                    ss.sname as shop_name
                FROM shop_inventory si
                JOIN product p ON si.prod_barcode = p.prod_barcode
                JOIN manufacturer m ON p.license_key = m.license_key
                JOIN spaza_shop ss ON si.business_reg_number = ss.business_reg_number
                WHERE si.prod_barcode = %s AND si.business_reg_number = %s
            """
            cursor.execute(inventory_query, (barcode, business_reg_number))
            result = cursor.fetchone()

            if not result:
                return jsonify({"error": "Product not found in this store's inventory"}), 404

            response = {
                "product": {
                    "prod_barcode": result['prod_barcode'],
                    "prod_name": result['prod_name'],
                    "prod_price": float(result['shop_price']),
                    "prod_expiry_date": result['prod_expiry_date'].strftime('%Y-%m-%d') if result['prod_expiry_date'] else None,
                    "prod_manu_date": result['prod_manu_date'].strftime('%Y-%m-%d') if result['prod_manu_date'] else None,
                    "prod_quantity": result['stock_quantity'],
                    "prod_image_url": result['prod_image_url'],
                    "license_key": result['license_key']
                },
                "manufacturer": {
                    "company_name": result['company_name'],
                    "address": result['address'],
                    "location": result['location'],
                    "license_key": result['license_key']
                },
                "store": {
                    "shop_name": result['shop_name'],
                    "business_reg_number": business_reg_number,
                    "shop_price": float(result['shop_price']),
                    "stock_quantity": result['stock_quantity']
                }
            }
        else:
            # Handle case when no store is selected (if needed)
            product_query = "SELECT * FROM product WHERE prod_barcode = %s"
            cursor.execute(product_query, (barcode,))
            product = cursor.fetchone()

            if not product:
                return jsonify({"error": "Product not found"}), 404
            
            manufacturer_query = "SELECT * FROM manufacturer WHERE license_key = %s"
            cursor.execute(manufacturer_query, (product['license_key'],))
            manufacturer = cursor.fetchone()

            response = {
                "product": {
                    "prod_barcode": product['prod_barcode'],
                    "prod_name": product['prod_name'],
                    "prod_price": float(product['prod_price']),
                    "prod_expiry_date": product['prod_expiry_date'].strftime('%Y-%m-%d') if product['prod_expiry_date'] else None,
                    "prod_manu_date": product['prod_manu_date'].strftime('%Y-%m-%d') if product['prod_manu_date'] else None,
                    "prod_quantity": product['prod_quantity'],
                    "prod_image_url": product['prod_image_url'],
                    "license_key": product['license_key']
                },
                "manufacturer": {
                    "company_name": manufacturer['company_name'] if manufacturer else "Unknown Manufacturer",
                    "address": manufacturer['address'] if manufacturer else "Unknown",
                    "location": manufacturer['location'] if manufacturer else "Unknown",
                    "license_key": product['license_key']
                }
            }

        return jsonify(response)
        
    except Exception as e:
        print(f"Error in scan_barcode: {str(e)}")
        return jsonify({"error": str(e)}), 500
    finally:
        if connection:
            connection.close()


@app.route('/check_expiring_products')
def check_expiring_products():
    business_reg_number = session.get('business_reg_number')
    days_threshold = request.args.get('days', default=7, type=int)
    
    if not business_reg_number:
        return jsonify({"success": False, "message": "Business registration number is required"}), 400
    
    connection = None
    try:    
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get expired products (already past expiry date)
        cursor.execute("""
            SELECT p.prod_barcode, p.prod_name, p.prod_expiry_date, 
                   si.shop_price, si.stock_quantity,
                   DATEDIFF(p.prod_expiry_date, CURDATE()) AS days_to_expiry
            FROM shop_inventory si
            JOIN product p ON si.prod_barcode = p.prod_barcode
            WHERE si.business_reg_number = %s 
            AND p.prod_expiry_date IS NOT NULL
            ORDER BY p.prod_expiry_date ASC
        """, (business_reg_number,))
        products = cursor.fetchall()
        
        # Categorize products
        expired = []
        expiring_soon = []
        safe = []
        
        for product in products:
            days = product['days_to_expiry']
            if days < 0:
                expired.append(product)
            elif days <= days_threshold:
                expiring_soon.append(product)
            else:
                safe.append(product)
        
        return jsonify({
            "success": True,
            "expired_products": expired,
            "expiring_products": expiring_soon,
            "safe_products": safe
        })
        
    except Error as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/check_manufacturer_expiry')
def check_manufacturer_expiry():
    manufacturer_id = request.args.get('manufacturer_id')
    days_threshold = request.args.get('days', default=7, type=int)
    
    if not manufacturer_id:
        return jsonify({"success": False, "message": "Manufacturer ID is required"}), 400
    
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get expired products (already past expiry date)
        cursor.execute("""
            SELECT prod_barcode, prod_name, prod_expiry_date
            FROM product
            WHERE license_key = %s 
            AND prod_expiry_date < CURDATE()
        """, (manufacturer_id,))
        expired = cursor.fetchall()
        
        # Get products expiring soon (within next 7 days)
        cursor.execute("""
            SELECT prod_barcode, prod_name, prod_expiry_date
            FROM product
            WHERE license_key = %s 
            AND prod_expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL %s DAY)
        """, (manufacturer_id, days_threshold))
        expiring_soon = cursor.fetchall()
        
        return jsonify({
            "success": True,
            "expired_products": expired,
            "expiring_products": expiring_soon
        })
        
    except Error as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

#Report generating for manufacturer
@app.route('/report_page')
def report_page():
    license_key = request.args.get('license_key')
    if not license_key:
        return "License key required", 400
    return render_template('report.html', license_key=license_key)

#Get the manufacturers report
@app.route('/manufacturer_report')
def manufacturer_report():
    license_key = request.args.get('license_key')
    if not license_key:
        return jsonify({"success": False, "error": "License key is required"}), 400

    try:
        connection = create_connection()
        if not connection:
            return jsonify({"success": False, "error": "Database connection failed"}), 500
            
        cursor = connection.cursor(dictionary=True)
        
        # Query using the ManufacturerProductsReport view
        query = """
            SELECT * FROM manufacturerproductsreport 
            WHERE license_key = %s
            ORDER BY expiry_date
        """
        
        cursor.execute(query, (license_key,))
        products = cursor.fetchall()
        
        if not products:
            return jsonify({
                "success": True,
                "data": [],
                "message": "No products found for this manufacturer"
            })
        
        # Convert datetime objects to strings
        for product in products:
            for field in ['manufacture_date', 'expiry_date', 'added_date', 
                         'manufacturer_last_login', 'manufacturer_created']:
                if product.get(field) and isinstance(product[field], (datetime, date)):
                    product[field] = product[field].isoformat()
        
        return jsonify({
            "success": True,
            "data": products
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to fetch manufacturer report"
        }), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            
#Spaza Shop new routes from new design 
@app.route('/get_shop_inventory')
def get_shop_inventory():
    business_reg_number = session.get('business_reg_number')
    if not business_reg_number:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401

    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Debug: Print the business_reg_number being used
        print(f"Fetching inventory for business: {business_reg_number}")
        
        cursor.execute("""
            SELECT 
                si.*, 
                p.prod_name, 
                p.prod_image_url, 
                p.prod_price,
                p.prod_expiry_date,
                p.license_key
            FROM shop_inventory si
            JOIN product p ON si.prod_barcode = p.prod_barcode
            WHERE si.business_reg_number = %s
        """, (business_reg_number,))
        
        inventory = cursor.fetchall()
        
        # Debug: Print the raw inventory data
        print(f"Inventory data: {inventory}")
        
        return jsonify({
            'success': True, 
            'inventory': inventory,
            'count': len(inventory)
        })
        
    except Exception as e:
        print(f"Error in get_shop_inventory: {str(e)}")
        return jsonify({
            'success': False, 
            'message': str(e),
            'error_type': type(e).__name__
        }), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
#add delete rote for expired inventory products
@app.route('/delete_expired_product', methods=['POST'])
def delete_expired_product():
    business_reg_number = session.get('business_reg_number')
    prod_barcode = request.json.get('prod_barcode')
    
    if not business_reg_number:
        return jsonify({"success": False, "message": "Business registration number is required"}), 400
    
    if not prod_barcode:
        return jsonify({"success": False, "message": "Product barcode is required"}), 400
    
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        
        # Verify the product is actually expired and belongs to this shop
        cursor.execute("""
            SELECT 1 FROM shop_inventory si
            JOIN product p ON si.prod_barcode = p.prod_barcode
            WHERE si.business_reg_number = %s 
            AND si.prod_barcode = %s
            AND p.prod_expiry_date < CURDATE()
        """, (business_reg_number, prod_barcode))
        
        if not cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Product not found or not expired"
            }), 404
        
        # Delete the product from shop inventory
        cursor.execute("""
            DELETE FROM shop_inventory
            WHERE business_reg_number = %s AND prod_barcode = %s
        """, (business_reg_number, prod_barcode))
        
        connection.commit()
        return jsonify({
            "success": True,
            "message": "Expired product removed from inventory"
        })
        
    except Error as e:
        if connection:
            connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
             
@app.route('/add_to_shop_inventory', methods=['POST'])
def add_to_shop_inventory():
    data = request.json
    business_reg_number = session.get('business_reg_number')
    prod_barcode = data.get('prod_barcode')
    shop_price = data.get('shop_price')
    stock_quantity = data.get('stock_quantity')

    if not all([business_reg_number, prod_barcode, shop_price, stock_quantity]):
        return jsonify({
            "success": False, 
            "message": "Missing required fields",
            "missing": [k for k, v in {
                'business_reg_number': business_reg_number,
                'prod_barcode': prod_barcode,
                'shop_price': shop_price,
                'stock_quantity': stock_quantity
            }.items() if not v]
        }), 400

    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()

        # Check if product exists and isn't expired
        cursor.execute("""
            SELECT prod_quantity, prod_expiry_date 
            FROM product 
            WHERE prod_barcode = %s
        """, (prod_barcode,))
        product = cursor.fetchone()
        
        if not product:
            return jsonify({
                "success": False,
                "message": "Product does not exist in system"
            }), 404
            
        available_quantity, expiry_date = product
        
        # Check if product is expired
        if expiry_date and expiry_date < datetime.now().date():
            return jsonify({
                "success": False,
                "message": "Cannot add expired product to inventory"
            }), 400
            
        # Check if requested quantity is available
        if stock_quantity > available_quantity:
            return jsonify({
                "success": False,
                "message": f"Not enough stock available. Only {available_quantity} units in system",
                "available_quantity": available_quantity
            }), 400

        # Check if this product already exists in this shop's inventory
        cursor.execute("""
            SELECT inventory_id, stock_quantity 
            FROM shop_inventory 
            WHERE business_reg_number = %s AND prod_barcode = %s
        """, (business_reg_number, prod_barcode))
        result = cursor.fetchone()

        if result:
            inventory_id, current_quantity = result
            # Update existing inventory
            update_query = """
                UPDATE shop_inventory 
                SET shop_price = %s, stock_quantity = stock_quantity + %s
                WHERE inventory_id = %s
            """
            cursor.execute(update_query, (
                shop_price,
                stock_quantity,
                inventory_id
            ))
            message = "Inventory updated"
        else:
            # Insert new inventory record
            insert_query = """
                INSERT INTO shop_inventory 
                (business_reg_number, prod_barcode, shop_price, stock_quantity)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                business_reg_number,
                prod_barcode,
                shop_price,
                stock_quantity
            ))
            message = "Product added to inventory"

        # Deduct the quantity from the main product table
        cursor.execute("""
            UPDATE product 
            SET prod_quantity = prod_quantity - %s 
            WHERE prod_barcode = %s
        """, (stock_quantity, prod_barcode))

        connection.commit()
        return jsonify({
            "success": True, 
            "message": message,
            "new_quantity": available_quantity - stock_quantity
        })

    except Exception as e:
        print("Error in add_to_shop_inventory:", str(e))
        if connection:
            connection.rollback()
        return jsonify({
            "success": False,
            "message": str(e),
            "error_type": type(e).__name__
        }), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            
@app.route('/get_all_products')
def get_all_products():
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM product"
        cursor.execute(query)
        products = cursor.fetchall()
        return jsonify({"success": True, "products": products})
    except Error as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            
@app.route('/get_manufacturer/<license_key>')
def get_manufacturer(license_key):
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM manufacturer WHERE license_key = %s"
        cursor.execute(query, (license_key,))
        manufacturer = cursor.fetchone()
        if manufacturer:
            return jsonify({"success": True, "manufacturer": manufacturer})
        else:
            return jsonify({"success": False, "message": "Manufacturer not found"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            
@app.route('/searchAvailableProducts')
def search_available_products():
    query = request.args.get('q', '').strip()
    registration_no = session.get('registration_no')
    if not registration_no:
        return jsonify({"success": False, "message": "Not logged in"}), 401

    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        if not query:
            cursor.execute("SELECT * FROM shop_inventory WHERE registration_no = %s", (registration_no,))
            products = cursor.fetchall()
            return jsonify({"success": True, "products": products})
        sql = """
            SELECT * FROM shop_inventory
            WHERE registration_no = %s AND (
                prod_name LIKE %s
                OR CAST(shop_price AS CHAR) LIKE %s
                OR CAST(last_updated AS CHAR) LIKE %s
            )
        """
        like_query = f"%{query}%"
        cursor.execute(sql, (registration_no, like_query, like_query, like_query))
        products = cursor.fetchall()
        return jsonify({"success": True, "products": products})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            
@app.route('/search_products')
def search_products():
    query = request.args.get('q', '').strip()
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        if not query:
            cursor.execute("SELECT * FROM product")
            products = cursor.fetchall()
            return jsonify({"success": True, "products": products})
        sql = """
            SELECT * FROM product
            WHERE prod_name LIKE %s
               OR CAST(prod_price AS CHAR) LIKE %s
               OR CAST(prod_expiry_date AS CHAR) LIKE %s
        """
        like_query = f"%{query}%"
        cursor.execute(sql, (like_query, like_query, like_query))
        products = cursor.fetchall()
        return jsonify({"success": True, "products": products})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    finally:
        if connection and connection.is_connected():
            cursor.close()

@app.route('/api/dashboard/summary')
def dashboard_summary():
    business_reg_number = session.get('business_reg_number')
    if not business_reg_number:
        return jsonify({"success": False, "message": "Business registration number is required"}), 401

    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get total inventory value and item count
        cursor.execute("""
            SELECT 
                SUM(si.shop_price * si.stock_quantity) AS total_value,
                SUM(si.stock_quantity) AS total_items
            FROM shop_inventory si
            WHERE si.business_reg_number = %s
        """, (business_reg_number,))
        summary = cursor.fetchone()
        
        # Get low stock count (items with stock <= 5)
        cursor.execute("""
            SELECT COUNT(*) AS low_stock_count
            FROM shop_inventory
            WHERE business_reg_number = %s 
            AND stock_quantity <= 5
        """, (business_reg_number,))
        low_stock = cursor.fetchone()
        
        # Get expiring soon count (within 7 days)
        cursor.execute("""
            SELECT COUNT(*) AS expiring_soon_count
            FROM shop_inventory si
            JOIN product p ON si.prod_barcode = p.prod_barcode
            WHERE si.business_reg_number = %s
            AND p.prod_expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
        """, (business_reg_number,))
        expiring_soon = cursor.fetchone()
        
        # Get expired count (already expired)
        cursor.execute("""
            SELECT COUNT(*) AS expired_count
            FROM shop_inventory si
            JOIN product p ON si.prod_barcode = p.prod_barcode
            WHERE si.business_reg_number = %s
            AND p.prod_expiry_date < CURDATE()
        """, (business_reg_number,))
        expired = cursor.fetchone()
        
        # Get top products (by value)
        cursor.execute("""
            SELECT 
                p.prod_name,
                SUM(si.stock_quantity) AS total_quantity,
                SUM(si.shop_price * si.stock_quantity) AS total_value
            FROM shop_inventory si
            JOIN product p ON si.prod_barcode = p.prod_barcode
            WHERE si.business_reg_number = %s
            GROUP BY p.prod_name
            ORDER BY total_value DESC
            LIMIT 5
        """, (business_reg_number,))
        top_products = cursor.fetchall()
        
        return jsonify({
            "success": True,
            "total_value": float(summary['total_value']) if summary['total_value'] else 0,
            "total_items": summary['total_items'] or 0,
            "low_stock_count": low_stock['low_stock_count'] or 0,
            "expiring_soon_count": expiring_soon['expiring_soon_count'] or 0,
            "expired_count": expired['expired_count'] or 0,  # Added expired count
            "top_products": top_products
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/dashboard/low_stock')
def dashboard_low_stock():
    business_reg_number = session.get('business_reg_number')
    if not business_reg_number:
        return jsonify({"success": False, "message": "Business registration number is required"}), 401

    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                si.inventory_id,
                si.prod_barcode,
                p.prod_name,
                p.prod_image_url,
                si.shop_price,
                si.stock_quantity,
                (si.shop_price * si.stock_quantity) AS item_value,
                p.prod_expiry_date
            FROM shop_inventory si
            JOIN product p ON si.prod_barcode = p.prod_barcode
            WHERE si.business_reg_number = %s 
            AND si.stock_quantity <= 5
            ORDER BY si.stock_quantity ASC
        """, (business_reg_number,))
        
        low_stock_items = cursor.fetchall()
        
        return jsonify({
            "success": True,
            "low_stock_items": low_stock_items
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/dashboard/expiring_soon')
def dashboard_expiring_soon():
    business_reg_number = session.get('business_reg_number')
    if not business_reg_number:
        return jsonify({"success": False, "message": "Business registration number is required"}), 401

    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                si.inventory_id,
                si.prod_barcode,
                p.prod_name,
                p.prod_image_url,
                si.shop_price,
                si.stock_quantity,
                p.prod_expiry_date,
                DATEDIFF(p.prod_expiry_date, CURDATE()) AS days_until_expiry
            FROM shop_inventory si
            JOIN product p ON si.prod_barcode = p.prod_barcode
            WHERE si.business_reg_number = %s
            AND p.prod_expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
            ORDER BY p.prod_expiry_date ASC
        """, (business_reg_number,))
        
        expiring_items = cursor.fetchall()
        
        return jsonify({
            "success": True,
            "expiring_items": expiring_items
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            
@app.route('/api/dashboard/analytics')
def dashboard_analytics():
    business_reg_number = session.get('business_reg_number')
    if not business_reg_number:
        return jsonify({"success": False, "message": "Business registration number is required"}), 401

    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get popular products
        cursor.execute("""
            SELECT 
                p.prod_barcode,
                p.prod_name,
                COUNT(pa.analytics_id) AS interaction_count,
                SUM(CASE WHEN pa.action_type = 'PURCHASED' THEN 1 ELSE 0 END) AS purchase_count,
                SUM(CASE WHEN pa.action_type = 'ADD_TO_CART' THEN 1 ELSE 0 END) AS cart_count
            FROM product_analytics pa
            JOIN product p ON pa.prod_barcode = p.prod_barcode
            WHERE pa.store_id = %s
            GROUP BY p.prod_barcode
            ORDER BY interaction_count DESC
            LIMIT 5
        """, (business_reg_number,))
        popular_products = cursor.fetchall()
        
        # Get recent activity
        cursor.execute("""
            SELECT 
                pa.action_type,
                pa.timestamp,
                p.prod_name,
                c.email AS customer_email
            FROM product_analytics pa
            JOIN product p ON pa.prod_barcode = p.prod_barcode
            JOIN customer c ON pa.cust_id = c.cust_id
            WHERE pa.store_id = %s
            ORDER BY pa.timestamp DESC
            LIMIT 10
        """, (business_reg_number,))
        recent_activity = cursor.fetchall()
        
        return jsonify({
            "success": True,
            "popular_products": popular_products,
            "recent_activity": recent_activity
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            
@app.route('/spaza_owner_report')
def spaza_owner_report():
    if 'owner_id' not in session:
        return redirect(url_for('login_spazaOwner'))
    
    business_reg_number = session['business_reg_number']
    
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)

        # Get business summary with correct DATE_FORMAT
        cursor.execute("""
            SELECT DISTINCT
                owner_id,
                owner_name,
                phone_number,
                business_name,
                business_reg_number,
                DATE_FORMAT(account_created, '%d %b %Y') AS account_created,
                DATE_FORMAT(last_login, '%d %b %Y at %h:%i %p') AS last_login,
                shop_name,
                shop_location,
                total_products,
                inventory_value,
                low_stock_items,
                expiring_soon,
                total_purchases,
                total_revenue
            FROM spazaownerfullreport
            WHERE business_reg_number = %s
        """, (business_reg_number,))
        summary = cursor.fetchone() or {}

        # Get products
        cursor.execute("""
            SELECT 
                prod_barcode,
                prod_name,
                shop_price,
                stock_quantity,
                DATE_FORMAT(prod_expiry_date, '%d %b %Y') AS prod_expiry_date,
                days_until_expiry,
                expiry_status
            FROM spazaownerfullreport
            WHERE business_reg_number = %s 
              AND prod_barcode IS NOT NULL
        """, (business_reg_number,))
        products = cursor.fetchall()

        # Get reports
        cursor.execute("""
            SELECT 
                report_id,
                reported_product,
                DATE_FORMAT(reported_expiry, '%d %b %Y') AS reported_expiry,
                reporter_email,
                DATE_FORMAT(report_date, '%d %b %Y') AS report_date,
                report_status
            FROM spazaownerfullreport
            WHERE business_reg_number = %s 
              AND report_id IS NOT NULL
        """, (business_reg_number,))
        reports = cursor.fetchall()

        # Optional: log summary to verify keys
        # print("Summary fetched:", summary)

        return render_template(
            'spaza_owner_report.html',
            summary=summary,
            products=products,
            reports=reports
        )
        
    except Error as e:
        print(f"Database error: {str(e)}")
        return f"Error loading report: {str(e)}", 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/login_government', methods=['GET', 'POST'])
def login_government():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not all([email, password]):
            return jsonify({
                "success": False,
                "message": "Both email and password are required"
            }), 400

        connection = None
        try:
            connection = create_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute("""
                SELECT registration_no, gov_name 
                FROM government_authority
                WHERE email = %s AND gpassword = %s
            """, (email, password))

            gov_user = cursor.fetchone()

            if gov_user:
                session['gov_logged_in'] = True
                session['gov_reg_no'] = gov_user['registration_no']
                session['gov_name'] = gov_user['gov_name']
                
                return jsonify({
                    "success": True,
                    "message": "Login successful",
                    "redirect": url_for('government_dashboard')
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "Invalid email or password"
                }), 401

        except Exception as e:
            app.logger.error(f"Government login error: {str(e)}")
            return jsonify({
                "success": False,
                "message": "Server error during login"
            }), 500
        
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    return render_template('login_government.html')

@app.route('/government_dashboard')
def government_dashboard():
    if not session.get('gov_logged_in'):
        return redirect(url_for('login_government'))
    
    connection = None
    cursor = None
    try:
        # Fetch reports data
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM expired_product_reports")
        reports = cursor.fetchall()
        
        return render_template('government_dashboard.html', 
                               reports=reports,
                               gov_name=session.get('gov_name'))
    
    except Exception as e:
        app.logger.error(f"Dashboard error: {str(e)}")
        # Handle error directly in the dashboard template
        return render_template('government_dashboard.html', 
                               reports=[],
                               gov_name=session.get('gov_name'),
                               error="Failed to load reports data")
    
    finally:
        if connection and connection.is_connected():
            if cursor:
                cursor.close()
            connection.close()
            
@app.route('/gov_logout')
def gov_logout():
    session.pop('gov_logged_in', None)
    session.pop('gov_reg_no', None)
    session.pop('gov_name', None)
    return redirect(url_for('home'))


@app.route('/report_details/<int:report_id>')
def report_details(report_id):
    if not session.get('gov_logged_in'):
        return "Unauthorized", 401
    
    try:
        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        
        # Get report details
        cursor.execute("""
            SELECT * FROM expired_product_reports
            WHERE report_id = %s
        """, (report_id,))
        report = cursor.fetchone()
        
        # Get investigation history
        cursor.execute("""
            SELECT status, investigation_notes, report_date
            FROM expired_product_reports
            WHERE report_id = %s
            ORDER BY report_date DESC
        """, (report_id,))
        history = cursor.fetchall()
        
        return render_template('report_details.html', 
                              report=report, 
                              history=history)
    
    except Exception as e:
        app.logger.error(f"Report details error: {str(e)}")
        return "Error loading report details", 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

# Update report status route
@app.route('/update_report_status/<int:report_id>', methods=['POST'])
def update_report_status(report_id):
    if not session.get('gov_logged_in'):
        return redirect(url_for('login_government'))
    
    new_status = request.form.get('status')
    notes = request.form.get('notes', '')
    
    if not new_status:
        return "Status is required", 400
    
    connection = None
    try:
        connection = create_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            UPDATE expired_product_reports
            SET status = %s, investigation_notes = %s
            WHERE report_id = %s
        """, (new_status, notes, report_id))
        
        connection.commit()
        return redirect(url_for('government_dashboard'))
    
    except Exception as e:
        app.logger.error(f"Update error: {str(e)}")
        return "Database error", 500
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            
if __name__ == "__main__":
    app.run()
