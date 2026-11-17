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
