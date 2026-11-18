"""
Generate a synthetic hijab retail dataset (customers, products, orders, order items).

The data is synthetic, built with realistic patterns so the SQL analysis has something
meaningful to find:
  - fabrics with different price ranges and seasonal demand (chiffon in summer, wool blends in winter)
  - demand spikes before Eid (Ramadan and Eid al-Adha) and back-to-school
  - a mix of loyal repeat customers and one-time buyers who churn over time
  - colour demand that shifts by collection (light shades for Ramadan & Eid and summer,
    deep shades for fall and winter), more discounting on out-of-season colours, and
    higher return rates on shades that are hard to judge on screen
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
OUT = Path(__file__).parent

FABRICS = {
    # fabric: (price range, monthly demand weights Jan..Dec)
    "Chiffon":    ((18, 35), [0.6, 0.7, 1.2, 1.3, 1.5, 1.6, 1.6, 1.3, 0.9, 0.7, 0.6, 0.6]),
    "Jersey":     ((15, 28), [1.0, 1.0, 1.2, 1.2, 1.0, 1.0, 1.0, 1.4, 1.5, 1.1, 1.0, 1.0]),
    "Modal":      ((20, 38), [0.9, 0.9, 1.1, 1.1, 1.1, 1.1, 1.1, 1.2, 1.2, 1.0, 0.9, 0.9]),
    "Silk":       ((40, 85), [0.6, 0.7, 1.6, 1.8, 0.8, 1.4, 0.7, 0.6, 0.6, 0.7, 1.0, 1.5]),
    "Satin":      ((25, 50), [0.6, 0.7, 1.5, 1.6, 0.8, 1.3, 0.7, 0.6, 0.7, 0.8, 1.0, 1.4]),
    "Wool Blend": ((30, 60), [1.7, 1.4, 0.9, 0.5, 0.3, 0.2, 0.2, 0.4, 0.9, 1.4, 1.8, 1.9]),
}
COLOURS = ["Black", "Nude", "Navy", "Sage", "Dusty Rose", "Ivory", "Mocha", "Burgundy"]
COLOUR_WEIGHTS = [3.0, 2.5, 1.5, 1.2, 1.3, 1.0, 1.4, 0.9]
# Colour demand multiplier by collection (1.0 = the colour's normal demand)
COLOUR_SEASON = {
    "Winter":         {"Black": 1.2, "Nude": 0.9, "Navy": 1.3, "Sage": 0.6, "Dusty Rose": 0.7, "Ivory": 0.6, "Mocha": 1.5, "Burgundy": 1.8},
    "Ramadan & Eid":  {"Black": 0.9, "Nude": 1.0, "Navy": 0.9, "Sage": 1.4, "Dusty Rose": 1.6, "Ivory": 1.9, "Mocha": 0.9, "Burgundy": 1.2},
    "Spring":         {"Black": 0.9, "Nude": 1.1, "Navy": 0.9, "Sage": 1.4, "Dusty Rose": 1.4, "Ivory": 1.2, "Mocha": 0.8, "Burgundy": 0.7},
    "Summer":         {"Black": 0.8, "Nude": 1.3, "Navy": 0.9, "Sage": 1.5, "Dusty Rose": 1.2, "Ivory": 1.4, "Mocha": 0.7, "Burgundy": 0.5},
    "Back to School": {"Black": 1.3, "Nude": 1.1, "Navy": 1.4, "Sage": 0.9, "Dusty Rose": 0.8, "Ivory": 0.8, "Mocha": 1.1, "Burgundy": 0.9},
    "Fall":           {"Black": 1.1, "Nude": 1.0, "Navy": 1.1, "Sage": 0.8, "Dusty Rose": 0.8, "Ivory": 0.7, "Mocha": 1.6, "Burgundy": 1.5},
}
# Share of units returned, by colour (some shades look different in person than on screen)
RETURN_RATE = {"Black": 0.05, "Nude": 0.08, "Navy": 0.15, "Sage": 0.12,
               "Dusty Rose": 0.07, "Ivory": 0.13, "Mocha": 0.07, "Burgundy": 0.06}
STAPLES = {"Black", "Nude"}  # first-time buyers of staples come back more often
COLLECTIONS = {  # month -> seasonal collection
    1: "Winter", 2: "Winter", 3: "Ramadan & Eid", 4: "Ramadan & Eid", 5: "Spring",
    6: "Summer", 7: "Summer", 8: "Back to School", 9: "Back to School",
    10: "Fall", 11: "Fall", 12: "Winter",
}

def write(name, header, rows):
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

# Products: each style is a fabric + colour combination
products, pid = [], 1
for fabric, ((lo, hi), _) in FABRICS.items():
    for colour in COLOURS:
        products.append((pid, f"{colour} {fabric} Hijab", fabric, colour, round(random.uniform(lo, hi), 2)))
        pid += 1
write("products.csv", ["product_id", "product_name", "fabric", "colour", "unit_price"], products)

# Customers
start, end = date(2024, 1, 1), date(2025, 12, 31)
customers = []
for cid in range(1, 2001):
    signup = start + timedelta(days=random.randint(0, 600))
    customers.append((cid, signup.isoformat(), random.choice(["Ontario", "Quebec", "BC", "Alberta", "Other"])))
write("customers.csv", ["customer_id", "signup_date", "region"], customers)

# Orders + items
orders, items, oid, iid = [], [], 1, 1
loyalty = {c[0]: random.random() ** 2 for c in customers}
colour_w = dict(zip(COLOURS, COLOUR_WEIGHTS))
for cid, signup, _ in customers:
    d = date.fromisoformat(signup)
    active_until = min(end, d + timedelta(days=int(random.expovariate(1 / 240))))
    first = True
    while d <= active_until:
        if first or random.random() < 0.1 + 0.6 * loyalty[cid]:
            collection = COLLECTIONS[d.month]
            orders.append((oid, cid, d.isoformat(), d.strftime("%Y-%m"), collection))
            first_colours = set()
            for _ in range(random.randint(1, 4)):
                weights = [FABRICS[p[2]][1][d.month - 1] * colour_w[p[3]]
                           * COLOUR_SEASON[collection][p[3]] for p in products]
                p = random.choices(products, weights=weights)[0]
                qty = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]
                # Out-of-season colours need deeper and more frequent discounts to move
                in_season = COLOUR_SEASON[collection][p[3]] >= 1.0
                disc_w = [0.65, 0.2, 0.12, 0.03] if in_season else [0.35, 0.25, 0.25, 0.15]
                discount = random.choices([0, 0.1, 0.2, 0.3], weights=disc_w)[0]
                returned = sum(random.random() < RETURN_RATE[p[3]] for _ in range(qty))
                items.append((iid, oid, p[0], qty, round(p[4] * (1 - discount), 2), returned))
                first_colours.add(p[3])
                iid += 1
            if first and first_colours & STAPLES:
                loyalty[cid] = min(1.0, loyalty[cid] + 0.15)
            first = False
            oid += 1
        d += timedelta(days=random.randint(20, 90))
write("orders.csv", ["order_id", "customer_id", "order_date", "order_month", "collection"], orders)
write("order_items.csv", ["order_item_id", "order_id", "product_id", "quantity", "sale_price", "returned_quantity"], items)
print(f"{len(customers)} customers, {len(products)} styles, {len(orders)} orders, {len(items)} order items")
