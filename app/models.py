from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="customer")  # 'admin' or 'customer'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"

    def __repr__(self):
        return f"<User {self.email}>"


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    products = db.relationship(
        "Product", backref="category", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Category {self.name}>"


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id"), nullable=False
    )
    image = db.Column(db.String(300))  # stored filename
    is_vegetarian = db.Column(db.Boolean, default=True, nullable=False)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Product {self.name}>"


class Cart(db.Model):
    __tablename__ = "carts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", backref=db.backref("cart", uselist=False, lazy=True))
    items = db.relationship(
        "CartItem", backref="cart", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def item_count(self):
        """Total quantity of all line items in the cart."""
        return sum(item.quantity for item in self.items)

    @property
    def subtotal(self):
        """Sum of current product prices multiplied by quantities."""
        return sum(item.subtotal for item in self.items)

    def __repr__(self):
        return f"<Cart {self.id} user={self.user_id}>"


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("carts.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product", lazy=True)

    __table_args__ = (
        db.UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),
    )

    @property
    def subtotal(self):
        """Line subtotal using the current database price."""
        return self.product.price * self.quantity

    def __repr__(self):
        return f"<CartItem {self.id} product={self.product_id} qty={self.quantity}>"


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    delivery_address = db.Column(db.Text, nullable=False)
    landmark = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    pin_code = db.Column(db.String(10), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    delivery_fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_method = db.Column(db.String(40), nullable=False, default="cod")
    payment_status = db.Column(db.String(40), nullable=False, default="pending")
    order_status = db.Column(db.String(40), nullable=False, default="pending")
    delivery_instructions = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("orders", lazy=True))
    items = db.relationship(
        "OrderItem", backref="order", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def item_count(self):
        """Total quantity of all line items in the order."""
        return sum(item.quantity for item in self.items)

    def __repr__(self):
        return f"<Order {self.order_number}>"


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id"), nullable=False
    )
    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=True
    )
    product_name = db.Column(db.String(200), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    special_instructions = db.Column(db.Text, nullable=True)

    product = db.relationship("Product", lazy=True)

    def __repr__(self):
        return (
            f"<OrderItem {self.id} order={self.order_id} "
            f"product={self.product_name} qty={self.quantity}>"
        )
