# Design: Vegetarian Menu Items with Images

Date: 2026-11-03
Topic: Adding a full vegetarian menu (30 items, six categories) with images

## Intent and why

The customer-facing menu at `/menu` renders only vegetarian, available products. Until now, only four real items existed in the database
(Veggie Margherita Pizza, Paneer Tikka Burger, Cold Brew Coffee, Chocolate Brownie), so the menu felt thin and the ordering flow had little
to sell. The goal is to populate a full vegetarian menu of 30 items across six categories (5 each) with images so the menu is substantive
and orderable.

## Goals / Non-goals / Anti-goals

- Goals: 30 products across Pizzas, Burgers, Shakes, Beverages, Desserts, Snacks; five per category; each with description, price, vegetarian
  flag, availability, and image file in `app/static/uploads/`.
- Non-goals: no changes to cart, checkout, or order logic; no new categories beyond the six.
- Anti-goals: no non-vegetarian items; no redesign of the menu page or product card layout.

## Constraints

- Admin add/edit requires product image (JPG/PNG/WEBP) and description; only vegetarian allowed; price must be > 0.
- Customer menu filters `is_vegetarian=True` and `is_available=True`; paginated 12 per page; category filter via `category_id`.
- Uploads served at `/static/uploads/<filename>`; `secure_filename` plus collision suffix; `MAX_CONTENT_LENGTH = 16MB`.
- Prices stored as `Numeric(10,2)`; template renders `₹%.2f`.

## Approaches considered

1. Admin-driven adds — use `/admin/menu/add` per item with image upload. Dropped: would require 30 manual re-uploads of image files that already exist on disk, and works against the goal of a fast, repeatable setup.
2. DB seed + direct image file placement. Chosen: images already exist in `app/static/uploads/`; script links each product to its existing file without re-uploading.

## Decision

- Approach 2 (DB seed + direct image file placement) chosen: all 30 image files already exist in `app/static/uploads/` (matching the menu content in this doc). A one-time, idempotent seed script inserts each product linked to its existing image file, without re-uploading. Content stays admin-managed going forward via the existing `/admin/menu/add` flow; new products can still be added through the admin UI.

## Menu content (decided)

- Pizzas: Margherita ₹199; Farmhouse Veg ₹279; Corn & Cheese ₹249; Paneer Tikka ₹299; Veggie Supreme ₹299.
- Burgers: Classic Veg ₹149; Aloo Tikki ₹129; Crispy Veg ₹169; Paneer ₹199; Mexican Veg ₹189.
- Shakes: Classic Chocolate ₹149; Oreo ₹179; KitKat ₹179; Strawberry ₹149; Brownie ₹199.
- Beverages: Classic Cold Coffee ₹149; Iced Lemon Tea ₹99; Virgin Mojito ₹129; Blue Lagoon ₹129; Hot Chocolate ₹149.
- Desserts: Chocolate Brownie ₹119; Brownie w/ Vanilla Ice Cream ₹179; Chocolate Lava Cake ₹179; Cheesecake Slice ₹199; Belgian Chocolate Waffle ₹199.
- Snacks: Peri-Peri Fries ₹129; Cheesy Garlic Bread ₹149; Loaded Nachos ₹179; Mozzarella Cheese Sticks ₹189; Jalapeño Poppers ₹179.

## Remaining

- Update `app/scripts/seed_menu_items.py` (one-time): remove all 6 original placeholder/test products (nulling their OrderItem FK refs first, preserving order history via `product_name` snapshots), then insert all 30 vegetarian products into the six existing categories, linked to existing image files, idempotent with no duplicates on re-run; verifies each image exists before inserting.
- Get human approval of the design doc and the script before running.
- Run the script and verify all 30 products appear on `/menu` and in the admin menu list.
- Confirm descriptions/availability per item.
- Run the test suite.
