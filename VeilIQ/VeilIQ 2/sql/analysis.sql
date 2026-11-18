-- name: fabric_revenue_share
-- Revenue and share of total revenue by fabric
SELECT
    p.fabric,
    ROUND(SUM(oi.quantity * oi.sale_price), 2) AS revenue,
    ROUND(100.0 * SUM(oi.quantity * oi.sale_price)
          / SUM(SUM(oi.quantity * oi.sale_price)) OVER (), 1) AS pct_of_total
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
GROUP BY p.fabric
ORDER BY revenue DESC;

-- name: monthly_fabric_trend
-- Seasonal trend: monthly revenue per fabric with month-over-month change (LAG window function)
WITH monthly AS (
    SELECT
        o.order_month,
        p.fabric,
        SUM(oi.quantity * oi.sale_price) AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    JOIN products p     ON p.product_id = oi.product_id
    GROUP BY o.order_month, p.fabric
)
SELECT
    order_month,
    fabric,
    ROUND(revenue, 2) AS revenue,
    ROUND(revenue - LAG(revenue) OVER (PARTITION BY fabric ORDER BY order_month), 2) AS mom_change
FROM monthly
ORDER BY fabric, order_month;

-- name: top_styles_per_fabric
-- Top 3 styles (colours) in each fabric by revenue (RANK window function)
WITH product_revenue AS (
    SELECT
        p.fabric,
        p.product_name,
        SUM(oi.quantity * oi.sale_price) AS revenue,
        SUM(oi.quantity) AS units
    FROM order_items oi
    JOIN products p ON p.product_id = oi.product_id
    GROUP BY p.fabric, p.product_name
),
ranked AS (
    SELECT *,
           RANK() OVER (PARTITION BY fabric ORDER BY revenue DESC) AS rnk
    FROM product_revenue
)
SELECT fabric, product_name, ROUND(revenue, 2) AS revenue, units, rnk
FROM ranked
WHERE rnk <= 3
ORDER BY fabric, rnk;

-- name: repeat_purchase_rate
-- Share of customers who ordered more than once
WITH per_customer AS (
    SELECT customer_id, COUNT(*) AS n_orders
    FROM orders
    GROUP BY customer_id
)
SELECT
    COUNT(*) AS customers,
    SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END) AS repeat_customers,
    ROUND(100.0 * SUM(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS repeat_rate_pct
FROM per_customer;

-- name: cohort_retention
-- Retention by first-purchase cohort: % of each cohort that ordered again in a later month
WITH first_order AS (
    SELECT customer_id, MIN(order_month) AS cohort_month
    FROM orders
    GROUP BY customer_id
),
returned AS (
    SELECT DISTINCT f.customer_id, f.cohort_month
    FROM first_order f
    JOIN orders o ON o.customer_id = f.customer_id
    WHERE o.order_month > f.cohort_month
)
SELECT
    f.cohort_month,
    COUNT(*) AS cohort_size,
    COUNT(r.customer_id) AS returned,
    ROUND(100.0 * COUNT(r.customer_id) / COUNT(*), 1) AS retention_pct
FROM first_order f
LEFT JOIN returned r ON r.customer_id = f.customer_id
GROUP BY f.cohort_month
ORDER BY f.cohort_month;

-- name: customer_value_tiers
-- Split customers into quartiles by lifetime spend (NTILE window function)
WITH spend AS (
    SELECT o.customer_id, SUM(oi.quantity * oi.sale_price) AS lifetime_spend
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    GROUP BY o.customer_id
),
tiered AS (
    SELECT *, NTILE(4) OVER (ORDER BY lifetime_spend DESC) AS tier
    FROM spend
)
SELECT
    tier,
    COUNT(*) AS customers,
    ROUND(AVG(lifetime_spend), 2) AS avg_spend,
    ROUND(SUM(lifetime_spend), 2) AS total_spend
FROM tiered
GROUP BY tier
ORDER BY tier;

-- name: colour_performance
-- Units and revenue by colour, ranked (RANK window function)
SELECT
    p.colour,
    SUM(oi.quantity) AS units,
    ROUND(SUM(oi.quantity * oi.sale_price), 2) AS revenue,
    RANK() OVER (ORDER BY SUM(oi.quantity) DESC) AS units_rank
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
GROUP BY p.colour
ORDER BY units_rank;

-- name: collection_performance
-- Average monthly revenue and order size per seasonal collection
WITH monthly AS (
    SELECT
        o.collection,
        o.order_month,
        SUM(oi.quantity * oi.sale_price) AS revenue,
        COUNT(DISTINCT o.order_id) AS orders
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    GROUP BY o.collection, o.order_month
)
SELECT
    collection,
    ROUND(AVG(revenue), 2) AS avg_monthly_revenue,
    ROUND(SUM(revenue) / SUM(orders), 2) AS avg_order_value
FROM monthly
GROUP BY collection
ORDER BY avg_monthly_revenue DESC;

-- ============================================================
-- Colour intelligence
-- ============================================================

-- name: colour_collection_index
-- Seasonal colour demand index: a colour's share of units in a collection, divided by its
-- share across the whole year. 100 = normal, 150 = sells 50% more than usual in that collection.
WITH cu AS (
    SELECT o.collection, p.colour, SUM(oi.quantity) AS units
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    JOIN products p     ON p.product_id = oi.product_id
    GROUP BY o.collection, p.colour
),
shares AS (
    SELECT
        collection,
        colour,
        units,
        1.0 * units / SUM(units) OVER (PARTITION BY collection) AS share_in_collection,
        1.0 * SUM(units) OVER (PARTITION BY colour) / SUM(units) OVER () AS share_overall
    FROM cu
)
SELECT
    collection,
    colour,
    units,
    ROUND(100.0 * share_in_collection / share_overall, 0) AS demand_index,
    RANK() OVER (PARTITION BY collection ORDER BY share_in_collection / share_overall DESC) AS rank_in_collection
FROM shares
ORDER BY collection, rank_in_collection;

-- name: colour_off_season_discounting
-- Do colours need discounts when they're out of season? Each sale is tagged in-season or
-- off-season using the demand index (index >= 100 in that collection = in season), then
-- discount rates are compared.
WITH cu AS (
    SELECT o.collection, p.colour, SUM(oi.quantity) AS units
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    JOIN products p     ON p.product_id = oi.product_id
    GROUP BY o.collection, p.colour
),
season_fit AS (
    SELECT
        collection,
        colour,
        CASE WHEN (1.0 * units / SUM(units) OVER (PARTITION BY collection))
                  / (1.0 * SUM(units) OVER (PARTITION BY colour) / SUM(units) OVER ()) >= 1
             THEN 'In season' ELSE 'Off season' END AS season_fit
    FROM cu
)
SELECT
    sf.season_fit,
    SUM(oi.quantity) AS units,
    ROUND(100.0 * SUM(CASE WHEN oi.sale_price < p.unit_price THEN oi.quantity ELSE 0 END)
          / SUM(oi.quantity), 1) AS pct_units_discounted,
    ROUND(100.0 * (1 - SUM(oi.quantity * oi.sale_price) / SUM(oi.quantity * p.unit_price)), 1)
        AS avg_markdown_pct,
    ROUND(SUM(oi.quantity * (p.unit_price - oi.sale_price)), 2) AS markdown_dollars
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
JOIN products p     ON p.product_id = oi.product_id
JOIN season_fit sf  ON sf.collection = o.collection AND sf.colour = p.colour
GROUP BY sf.season_fit
ORDER BY sf.season_fit;

-- name: colour_return_rate
-- Return rate by colour, and the revenue refunded on returns
SELECT
    p.colour,
    SUM(oi.quantity) AS units_sold,
    SUM(oi.returned_quantity) AS units_returned,
    ROUND(100.0 * SUM(oi.returned_quantity) / SUM(oi.quantity), 1) AS return_rate_pct,
    ROUND(SUM(oi.returned_quantity * oi.sale_price), 2) AS refunded_revenue,
    RANK() OVER (ORDER BY 1.0 * SUM(oi.returned_quantity) / SUM(oi.quantity) DESC) AS return_rank
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
GROUP BY p.colour
ORDER BY return_rank;

-- name: first_colour_repeat_rate
-- Does the colour a customer buys first predict whether they come back?
-- (a customer whose first order has two colours counts toward both)
WITH first_order AS (
    SELECT customer_id, MIN(order_id) AS first_order_id
    FROM orders
    GROUP BY customer_id
),
n_orders AS (
    SELECT customer_id, COUNT(*) AS n
    FROM orders
    GROUP BY customer_id
),
first_colours AS (
    SELECT DISTINCT f.customer_id, p.colour
    FROM first_order f
    JOIN order_items oi ON oi.order_id = f.first_order_id
    JOIN products p     ON p.product_id = oi.product_id
)
SELECT
    fc.colour AS first_colour,
    COUNT(*) AS customers,
    SUM(CASE WHEN n.n > 1 THEN 1 ELSE 0 END) AS repeat_customers,
    ROUND(100.0 * SUM(CASE WHEN n.n > 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS repeat_rate_pct
FROM first_colours fc
JOIN n_orders n ON n.customer_id = fc.customer_id
GROUP BY fc.colour
ORDER BY repeat_rate_pct DESC;
