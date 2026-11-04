"""One-time seed script: replace placeholder menu items with the full 30-item menu.

Steps:
1. Removes all 6 original placeholder/test products. Before deleting each product,
   any OrderItem rows referencing it have their product_id set to NULL so order
   history is preserved (OrderItem stores product_name/unit_price snapshots).
2. Inserts all 30 vegetarian products into the six existing categories, linked to
   existing image files in app/static/uploads/ (no re-uploading or copying).

Idempotent: re-running will not create duplicate products.
Verifies each referenced image file exists before inserting.
Leaves customer orders (names, prices, totals) intact.
"""

import os

from app import create_app
from app.extensions import db
from app.models import Category, OrderItem, Product

# (category_name, product_name, description, price, image_filename)
MENU_ITEMS = [
    # Pizzas
    ("Pizzas", "Margherita", "Classic tomato, mozzarella and basil pizza.", 199.00, "Margherita pizza.jpg"),
    ("Pizzas", "Farmhouse Veg", "Loaded with seasonal farm-fresh vegetables.", 279.00, "Farmhouse Veg pizza.jpg"),
    ("Pizzas", "Corn & Cheese", "Sweet corn and cheese on a cheesy base.", 249.00, "Corn & Cheese pizza.jpg"),
    ("Pizzas", "Paneer Tikka", "Tandoori paneer tikka with onions and capsicum.", 299.00, "Paneer Tikka pizza.jpg"),
    ("Pizzas", "Veggie Supreme", "Supreme medley of garden vegetables.", 299.00, "Veggie Supreme pizza.jpg"),
    # Burgers
    ("Burgers", "Classic Veg", "Classic vegetable patty with house sauce.", 149.00, "Classic Veg Burger.jpg"),
    ("Burgers", "Aloo Tikki", "Spiced potato patty burger.", 129.00, "Aloo Tikki Burger.jpg"),
    ("Burgers", "Crispy Veg", "Crispy vegetable patty with lettuce and mayo.", 169.00, "Crispy Veg Burger.jpg"),
    ("Burgers", "Paneer", "Grilled paneer patty burger.", 199.00, "Paneer Burger.jpg"),
    ("Burgers", "Mexican Veg", "Mexican-spiced veggie patty with salsa.", 189.00, "Mexican Veg Burger.jpg"),
    # Shakes
    ("Shakes", "Classic Chocolate", "Rich chocolate milkshake.", 149.00, "Classic Chocolate Shake.jpg"),
    ("Shakes", "Oreo", "Cookies and cream milkshake.", 179.00, "Oreo Shake.jpg"),
    ("Shakes", "KitKat", "KitKat crunch milkshake.", 179.00, "KitKat Shake.jpg"),
    ("Shakes", "Strawberry", "Fresh strawberry milkshake.", 149.00, "Strawberry Shake.jpg"),
    ("Shakes", "Brownie", "Chocolate brownie milkshake.", 199.00, "Brownie Shake.jpg"),
    # Beverages
    ("Beverages", "Classic Cold Coffee", "Chilled coffee with milk.", 149.00, "Classic Cold Coffee.jpg"),
    ("Beverages", "Iced Lemon Tea", "Refreshing iced lemon tea.", 99.00, "Iced Lemon Tea.jpg"),
    ("Beverages", "Virgin Mojito", "Minty lime mocktail.", 129.00, "Virgin Mojito.jpg"),
    ("Beverages", "Blue Lagoon", "Blue curacao-style mocktail.", 129.00, "Blue Lagoon.jpg"),
    ("Beverages", "Hot Chocolate", "Warm creamy hot chocolate.", 149.00, "Hot Chocolate.jpg"),
    # Desserts
    ("Desserts", "Chocolate Brownie", "Fudgy chocolate brownie.", 119.00, "Chocolate Brownie.jpg"),
    ("Desserts", "Brownie w/ Vanilla Ice Cream", "Warm brownie with vanilla ice cream.", 179.00, "Brownie with Vanilla Ice Cream.jpg"),
    ("Desserts", "Chocolate Lava Cake", "Molten chocolate lava cake.", 179.00, "Chocolate Lava Cake.jpg"),
    ("Desserts", "Cheesecake Slice", "Classic New York cheesecake slice.", 199.00, "Cheesecake Slice.jpg"),
    ("Desserts", "Belgian Chocolate Waffle", "Belgian waffle with chocolate drizzle.", 199.00, "Belgian Chocolate Waffle.jpg"),
    # Snacks
    ("Snacks", "Peri-Peri Fries", "Peri-peri seasoned fries.", 129.00, "Peri-Peri Fries.jpg"),
    ("Snacks", "Cheesy Garlic Bread", "Garlic bread with melted cheese.", 149.00, "Cheesy Garlic Bread.jpg"),
    ("Snacks", "Loaded Nachos", "Nachos with salsa and cheese.", 179.00, "Loaded Nachos with Salsa & Cheese.jpg"),
    ("Snacks", "Mozzarella Cheese Sticks", "Crispy mozzarella sticks.", 189.00, "Mozzarella Cheese Sticks.jpg"),
    ("Snacks", "Jalapeño Poppers", "Stuffed jalapeño poppers.", 179.00, "Jalapeño Poppers.jpg"),
]

# Original placeholder/test products to remove, matched by name + original
# image/price so the newly seeded "Chocolate Brownie" (Dessert, Chocolate Brownie.jpg)
# is not mistaken for the old placeholder product.
ORIGINAL_PRODUCTS = [
    ("Veggie Margherita Pizza", "placeholder.jpg", 249.00),
    ("Paneer Tikka Burger", "placeholder.jpg", 199.00),
    ("Cold Brew Coffee", "placeholder.jpg", 99.00),
    ("Chocolate Brownie", "placeholder.jpg", 149.00),
    ("Unavailable Pizza", "placeholder.jpg", 299.00),
    ("Non-Veg Test Item", None, 9.99),
]


def remove_original_products():
    """Delete the 6 original products, nulling OrderItem FK refs first.

    Originals are matched by name + original image filename + price so that
    re-running the script does not delete newly seeded items that happen to
    share a name (e.g. the Chocolate Brownie dessert).
    """
    removed = 0
    order_items_repointed = 0
    for name, orig_image, orig_price in ORIGINAL_PRODUCTS:
        product = Product.query.filter_by(name=name).first()
        if not product:
            continue
        if product.image != orig_image or abs(float(product.price) - orig_price) > 0.001:
            # Not an original placeholder (e.g. already-replaced Chocolate Brownie).
            continue
        # Preserve order history: drop the FK link but keep product_name snapshot.
        repointed = OrderItem.query.filter_by(product_id=product.id).update(
            {"product_id": None}, synchronize_session=False
        )
        order_items_repointed += repointed or 0
        db.session.delete(product)
        removed += 1
        print(f"  Removed product {name!r} (id={product.id}); repointed {repointed or 0} order items.")
    db.session.commit()
    print(f"Removed {removed} original products; repointed {order_items_repointed} order items.")
    return removed


def main():
    app = create_app()
    with app.app_context():
        upload_folder = app.config["UPLOAD_FOLDER"]
        categories = {c.name: c for c in Category.query.all()}

        # Step 1: remove originals.
        remove_original_products()

        # Step 2: insert the 30 menu items.
        to_add = []
        skipped = 0
        failed = []

        for category_name, product_name, description, price, image_filename in MENU_ITEMS:
            category = categories.get(category_name)
            if not category:
                failed.append((product_name, f"category '{category_name}' not found"))
                continue

            image_path = os.path.join(upload_folder, image_filename)
            if not os.path.exists(image_path):
                failed.append((product_name, f"image '{image_filename}' not found on disk"))
                continue

            existing = Product.query.filter_by(name=product_name).first()
            if existing:
                skipped += 1
                continue

            to_add.append(
                Product(
                    name=product_name,
                    description=description,
                    price=price,
                    category_id=category.id,
                    image=image_filename,
                    is_vegetarian=True,
                    is_available=True,
                )
            )

        added = 0
        try:
            db.session.add_all(to_add)
            db.session.commit()
            added = len(to_add)
        except Exception as exc:
            db.session.rollback()
            failed.append(("database commit", str(exc)))

        print(f"Seed summary: {added} added, {skipped} skipped (already exist), {len(failed)} failed")
        for name, reason in failed:
            print(f"  FAILED: {name} — {reason}")


if __name__ == "__main__":
    main()
