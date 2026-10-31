# Cart Customization Popup — Design Doc

**Date:** 2026-10-31  
**Status:** Implemented  
**Size:** Small change (extension of existing Feature 4 cart)

## Intent and why

When a customer clicks "Add to Cart" on the menu, a modal popup should open first so the customer can set quantity and add special instructions before the item is actually added to the cart. This gives customers control over their order before commitment, matching the behavior of food-delivery sites like Zomato/Domino's.

## Goals

- Every "Add to Cart" click opens a customization modal first — nothing is added until the customer confirms in the modal.
- Customer can set quantity with +/− controls (minimum 1, default 1).
- Customer can add special instructions / notes (free text).
- Product image, name, and price are shown read-only in the modal.
- Item is added to cart only when the customer clicks "Add to Cart" in the modal.
- Logged-out customers are still redirected to login first (intent preserved via session).
- All existing cart validation preserved: vegetarian-only, available-only, ownership, CSRF, server-side price validation.

## Non-goals

- Full pizza-style size/crust/topping customization (not supported by the current Product model).
- Checkout or payment processing.
- Saving customizations as reusable product variants.

## Anti-goals

- Adding item to cart immediately without modal confirmation.
- Storing client-submitted prices or totals.
- Allowing zero or negative quantities.

## Constraints

- Reuse existing `Product` model — no new size/crust/topping tables.
- Reuse existing `Cart`/`CartItem` models; add a `notes` column to `CartItem` for special instructions.
- Server-side validation of every field; never trust frontend-submitted prices.
- Maintain Brew & Bite design system: coffee-brown buttons, warm cream ground, white cards, square buttons.
- No new dependencies.

## Approaches considered

| Approach | Description | Trade-off |
|----------|-------------|-----------|
| **A. Modal on every Add to Cart click** (chosen) | Modal opens on every click; item added only on confirm. | Guarantees customization step; one extra click per item. |
| B. One-click add + optional customize | Adds 1 item immediately; "Customize" button opens modal. | Faster for single items, but doesn't guarantee customization. |
| C. Slide-out drawer | Same fields in a side panel. | Keeps menu visible; more complex layout and close handling. |

## Decisions (my calls)

- **Approach A:** modal opens on every "Add to Cart" click.
- Quantity defaults to 1; min 1 enforced server-side and client-side.
- Notes stored as a new `notes TEXT` column on `CartItem`.
- Modal submits via POST to the existing `/cart/add/<product_id>` route, sending `quantity` and `notes` form fields.
- Escape key or clicking the overlay closes the modal without adding.
- "Cancel" button closes without adding.

## What's left to the builder

- Add `notes` column to `cart_items` table (migration/init strategy, preserving existing data).
- Create the modal HTML (partial template included by `menu.html`, or inline).
- Write modal CSS: overlay backdrop, centered panel, focus handling, responsive mobile layout.
- Update `menu.html` so the Add to Cart button opens the modal instead of POSTing directly.
- Update `/cart/add` route to read `quantity` and `notes` from the form and store them.
- Add client-side quantity validation (min 1, integer) in the modal.
- Test: add with qty + notes, add with default qty, cancel without adding, logged-out redirect, totals correct.

---

**Approval needed:** Please confirm this design before I build. Once approved, I'll implement it and run the test suite.
