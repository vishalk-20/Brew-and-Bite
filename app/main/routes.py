from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import current_user

from app.extensions import db
from app.models import Product, Category

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("main.customer_home"))
    return redirect(url_for("auth.login"))


@main_bp.route("/customer")
def customer_home():
    """Customer homepage / account dashboard."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login", next=url_for("main.customer_home")))
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))

    featured = (
        Product.query.filter_by(is_vegetarian=True, is_available=True)
        .order_by(Product.created_at.desc())
        .limit(4)
        .all()
    )
    return render_template("main/customer_home.html", featured=featured)


@main_bp.route("/menu")
def menu():
    """Customer-facing menu page with search, category filter, and sorting."""
    page = request.args.get("page", 1, type=int)
    per_page = 12
    search = (request.args.get("search") or "").strip()
    category = request.args.get("category", type=int)
    sort = request.args.get("sort", "default")

    # Only show vegetarian and available products.
    query = Product.query.filter_by(is_vegetarian=True, is_available=True)

    if search:
        query = query.filter(
            Product.name.ilike(f"%{search}%")
            | Product.description.ilike(f"%{search}%")
        )

    if category:
        query = query.filter_by(category_id=category)

    # Apply sorting.
    if sort == "price_low":
        query = query.order_by(Product.price.asc(), Product.created_at.desc())
    elif sort == "price_high":
        query = query.order_by(Product.price.desc(), Product.created_at.desc())
    elif sort == "name":
        query = query.order_by(Product.name.asc(), Product.created_at.desc())
    elif sort == "recent":
        query = query.order_by(Product.created_at.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    products = pagination.items
    categories = Category.query.order_by(Category.name).all()

    return render_template(
        "main/menu.html",
        products=products,
        pagination=pagination,
        categories=categories,
        search=search,
        category=category,
        sort=sort,
    )
