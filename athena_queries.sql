-- =========================================================================
-- Amazon Athena Queries for Project SpecialsID
-- Target Database: <Project-name>_db (as defined in Terraform)
-- Target Table: pnp (automatically inferred by Glue Crawler)
-- =========================================================================

-- 1. 🔥 TOP 10 BIGGEST SAVINGS
-- Identifies the deepest percentage discounts currently available across all provinces.
SELECT 
    product_name, 
    brand, 
    current_price, 
    was_price, 
    discount_pct, 
    province, 
    date_range
FROM "specialsid_db"."pnp"
WHERE discount_pct > 0
ORDER BY discount_pct DESC
LIMIT 10;


-- 2. 🏆 BRAND DOMINANCE
-- Shows which brands have the most active specials in the dataset.
SELECT 
    brand, 
    COUNT(*) as deal_count,
    ROUND(AVG(discount_pct), 2) as avg_savings_pct
FROM "specialsid_db"."pnp"
GROUP BY brand
HAVING COUNT(*) > 1
ORDER BY deal_count DESC;


-- 3. 📍 PROVINCIAL SAVINGS COMPARISON
-- Compares the average discount intensity between different South African regions.
SELECT 
    province, 
    COUNT(*) as total_deals,
    ROUND(AVG(current_price), 2) as avg_deal_price,
    ROUND(AVG(discount_pct), 2) as avg_discount_pct
FROM "specialsid_db"."pnp"
GROUP BY province
ORDER BY avg_discount_pct DESC;


-- 4. 🏃 LAST CHANCE (EXPIRING SOON)
-- Finds active deals that are closing in the next few days.
-- Note: partition_1/date_range extraction depends on Glue's crawler configuration.
SELECT 
    product_name, 
    brand, 
    current_price, 
    date_range,
    province
FROM "specialsid_db"."pnp"
-- Assuming today's date is relevant to the end of the date_range string
WHERE date_range LIKE '%2026'
ORDER BY date_range ASC
LIMIT 20;


-- 5. 🛒 CATEGORY SEARCH: ESSENTIALS (Alcohol & Meat)
-- Emulating the dashboard's AI expansion for a specific group of keywords.
SELECT 
    product_name, 
    brand, 
    current_price, 
    province
FROM "specialsid_db"."pnp"
WHERE product_name LIKE '%Wine%' 
   OR product_name LIKE '%Beer%' 
   OR product_name LIKE '%Steak%' 
   OR product_name LIKE '%Chicken%'
ORDER BY current_price ASC;


-- 6. 📉 PRICING TIERS ANALYSIS
-- Breakdown of deals into budget-friendly price buckets.
SELECT 
    CASE 
        WHEN current_price < 20 THEN '1. Under R20'
        WHEN current_price BETWEEN 20 AND 50 THEN '2. R20 - R50'
        WHEN current_price BETWEEN 50 AND 100 THEN '3. R50 - R100'
        ELSE '4. Over R100'
    END as price_tier,
    COUNT(*) as deal_count
FROM "specialsid_db"."pnp"
GROUP BY 1
ORDER BY 1;
