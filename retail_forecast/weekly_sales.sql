SELECT store_id, product_id, week,
       SUM(quantity) AS units,
       SUM(revenue) AS revenue
FROM sales
GROUP BY store_id, product_id, week
ORDER BY store_id, product_id, week;
