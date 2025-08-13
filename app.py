from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///store.db")

def login_required(f):
    """Decorator to require login for certain routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def index():
    """Show all products"""
    products = db.execute("SELECT * FROM products ORDER BY name")
    return render_template("index.html", products=products)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validate input
        if not username:
            return render_template("register.html", error="Must provide username")
        if not email:
            return render_template("register.html", error="Must provide email")
        if not password:
            return render_template("register.html", error="Must provide password")
        if password != confirmation:
            return render_template("register.html", error="Passwords don't match")

        # Check if username already exists
        existing_user = db.execute("SELECT id FROM users WHERE username = ?", username)
        if existing_user:
            return render_template("register.html", error="Username already exists")

        # Check if email already exists
        existing_email = db.execute("SELECT id FROM users WHERE email = ?", email)
        if existing_email:
            return render_template("register.html", error="Email already registered")

        # Insert new user
        password_hash = generate_password_hash(password)
        db.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                  username, email, password_hash)

        return redirect("/login")

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    # Clear any existing session
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Validate input
        if not username:
            return render_template("login.html", error="Must provide username")
        if not password:
            return render_template("login.html", error="Must provide password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["password_hash"], password):
            return render_template("login.html", error="Invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]

        return redirect("/")

    return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    return redirect("/")

@app.route("/profile", methods=["GET", "POST"])
def profile():
    """Check user"""
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    """Show profile"""
    if request.method == "GET":
        user = db.execute("SELECT * FROM users WHERE id = ?;", user_id)[0]
        return render_template("profile.html", user=user)

    else:
        """Update password"""
        user = db.execute("SELECT * FROM users WHERE id = ?;", user_id)[0]
        new_password = request.form.get("new_password")
        if new_password and len(new_password) >= 8:
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?;", generate_password_hash(new_password), user_id)
            return render_template("profile.html",user=user, message="Password updated successfully")

        else:
            return render_template("profile.html",user=user, error="Password must be at least 8 characters")

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    """Show product details"""
    product = db.execute("SELECT * FROM products WHERE id = ?", product_id)
    if not product:
        return redirect("/")
    return render_template("product.html", product=product[0])

@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
@login_required
def add_to_cart(product_id):
    """Add product to cart"""
    quantity = int(request.form.get("quantity", 1))

    # Check if product exists
    product = db.execute("SELECT * FROM products WHERE id = ?", product_id)
    if not product:
        return redirect("/")

    # Check if item already in cart
    existing_item = db.execute("SELECT * FROM cart WHERE user_id = ? AND product_id = ?",
                              session["user_id"], product_id)

    if existing_item:
        # Update quantity
        new_quantity = existing_item[0]["quantity"] + quantity
        db.execute("UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?",
                  new_quantity, session["user_id"], product_id)
    else:
        # Add new item
        db.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)",
                  session["user_id"], product_id, quantity)

    return redirect("/cart")

@app.route("/cart")
@login_required
def cart():
    """Show shopping cart"""
    cart_items = db.execute("""
        SELECT c.id, c.quantity, p.name, p.price, p.image_url, p.id as product_id,
               (c.quantity * p.price) as total
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    """, session["user_id"])

    total_amount = sum(item["total"] for item in cart_items)

    return render_template("cart.html", cart_items=cart_items, total_amount=total_amount)

@app.route("/remove_from_cart/<int:cart_id>", methods=["POST"])
@login_required
def remove_from_cart(cart_id):
    """Remove item from cart"""
    db.execute("DELETE FROM cart WHERE id = ? AND user_id = ?", cart_id, session["user_id"])
    return redirect("/cart")

@app.route("/update_cart/<int:cart_id>", methods=["POST"])
@login_required
def update_cart(cart_id):
    """Update cart item quantity"""
    quantity = int(request.form.get("quantity", 1))
    if quantity > 0:
        db.execute("UPDATE cart SET quantity = ? WHERE id = ? AND user_id = ?",
                  quantity, cart_id, session["user_id"])
    else:
        db.execute("DELETE FROM cart WHERE id = ? AND user_id = ?", cart_id, session["user_id"])
    return redirect("/cart")

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    """Process checkout"""
    if request.method == "POST":
        # In a real application, you would process payment here
        # For now, we'll just clear the cart
        db.execute("DELETE FROM cart WHERE user_id = ?", session["user_id"])
        return render_template("success.html")

    # Get cart items for checkout display
    cart_items = db.execute("""
        SELECT c.quantity, p.name, p.price, (c.quantity * p.price) as total
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    """, session["user_id"])

    if not cart_items:
        return redirect("/cart")

    total_amount = sum(item["total"] for item in cart_items)
    return render_template("checkout.html", cart_items=cart_items, total_amount=total_amount)

if __name__ == "__main__":
    app.run(debug=True)
