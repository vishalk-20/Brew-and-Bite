import os
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Category, Product

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(f):
    """Role-based guard: only users with role == 'admin' may proceed."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in as admin to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    total_items = Product.query.count()
    available_items = Product.query.filter_by(is_available=True).count()
    unavailable_items = Product.query.filter_by(is_available=False).count()
    total_categories = Category.query.count()
    return render_template(
        "admin/dashboard.html",
        total_items=total_items,
        available_items=available_items,
        unavailable_items=unavailable_items,
        total_categories=total_categories,
    )


@admin_bp.route("/menu")
@login_required
@admin_required
def menu_list():
    page = request.args.get("page", 1, type=int)
    per_page = 12
    search = (request.args.get("search") or "").strip()
    category_id = request.args.get("category_id", type=int)

    query = Product.query
    if search:
        query = query.filter(
            Product.name.ilike(f"%{search}%")
            | Product.description.ilike(f"%{search}%")
        )
    if category_id:
        query = query.filter_by(category_id=category_id)

    pagination = query.order_by(Product.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    products = pagination.items
    categories = Category.query.order_by(Category.name).all()

    return render_template(
        "admin/menu_list.html",
        products=products,
        pagination=pagination,
        categories=categories,
        search=search,
        category_id=category_id,
    )


@admin_bp.route("/menu/add", methods=["GET", "POST"])
@login_required
@admin_required
def menu_add():
    categories = Category.query.order_by(Category.name).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip()
        category_id = request.form.get("category_id", type=int)
        price = request.form.get("price", type=float)
        is_vegetarian = "is_vegetarian" in request.form
        is_available = "is_available" in request.form
        image_file = request.files.get("image")

        errors = []
        if not name:
            errors.append("Product name is required.")
        if not description:
            errors.append("Description is required.")
        if not category_id:
            errors.append("Category is required.")
        if not price or price <= 0:
            errors.append("Price must be greater than zero.")
        if not image_file or image_file.filename == "":
            errors.append("Product image is required.")
        elif not allowed_file(image_file.filename):
            errors.append("Only JPG, JPEG, PNG and WEBP images are allowed.")
        if not is_vegetarian:
            errors.append("Only vegetarian products can be added.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "admin/menu_form.html", categories=categories, action="Add"
            )

        filename = secure_filename(image_file.filename)
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(
            os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        ):
            filename = f"{base}_{counter}{ext}"
            counter += 1
        image_file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))

        product = Product(
            name=name,
            description=description,
            price=price,
            category_id=category_id,
            image=filename,
            is_vegetarian=True,  # all products must be vegetarian
            is_available=is_available,
        )
        db.session.add(product)
        db.session.commit()
        flash("Menu item added successfully.", "success")
        return redirect(url_for("admin.menu_list"))

    return render_template(
        "admin/menu_form.html", categories=categories, action="Add"
    )


@admin_bp.route("/menu/edit/<int:id>", methods=["GET", "POST"])
@login_required
@admin_required
def menu_edit(id):
    product = Product.query.get_or_404(id)
    categories = Category.query.order_by(Category.name).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        description = (request.form.get("description") or "").strip()
        category_id = request.form.get("category_id", type=int)
        price = request.form.get("price", type=float)
        is_vegetarian = "is_vegetarian" in request.form
        is_available = "is_available" in request.form
        image_file = request.files.get("image")

        errors = []
        if not name:
            errors.append("Product name is required.")
        if not description:
            errors.append("Description is required.")
        if not category_id:
            errors.append("Category is required.")
        if not price or price <= 0:
            errors.append("Price must be greater than zero.")
        if not is_vegetarian:
            errors.append("Only vegetarian products can be saved.")

        old_image = product.image

        if image_file and image_file.filename != "":
            if not allowed_file(image_file.filename):
                errors.append("Only JPG, JPEG, PNG and WEBP images are allowed.")
            else:
                filename = secure_filename(image_file.filename)
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(
                    os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
                ):
                    filename = f"{base}_{counter}{ext}"
                    counter += 1
                image_file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
                product.image = filename
                # Remove the old image only if no other product references it.
                if old_image:
                    other = Product.query.filter(
                        Product.image == old_image, Product.id != id
                    ).first()
                    if not other:
                        old_path = os.path.join(
                            current_app.config["UPLOAD_FOLDER"], old_image
                        )
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except OSError:
                                pass

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "admin/menu_form.html",
                product=product,
                categories=categories,
                action="Edit",
            )

        product.name = name
        product.description = description
        product.price = price
        product.category_id = category_id
        product.is_vegetarian = True
        product.is_available = is_available
        db.session.commit()
        flash("Menu item updated successfully.", "success")
        return redirect(url_for("admin.menu_list"))

    return render_template(
        "admin/menu_form.html",
        product=product,
        categories=categories,
        action="Edit",
    )


@admin_bp.route("/menu/delete/<int:id>", methods=["POST"])
@login_required
@admin_required
def menu_delete(id):
    product = Product.query.get_or_404(id)
    # Soft-delete: disable the product so historical orders/references are preserved.
    product.is_available = False
    db.session.commit()
    flash(f'"{product.name}" has been disabled. Historical orders are preserved.', "success")
    return redirect(url_for("admin.menu_list"))


@admin_bp.route("/menu/toggle-availability/<int:id>", methods=["POST"])
@login_required
@admin_required
def toggle_availability(id):
    product = Product.query.get_or_404(id)
    product.is_available = not product.is_available
    db.session.commit()
    status = "available" if product.is_available else "unavailable"
    flash(f'"{product.name}" is now {status}.', "success")
    return redirect(url_for("admin.menu_list"))
