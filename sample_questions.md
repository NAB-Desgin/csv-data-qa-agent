# 10 Demo Questions and Answers

Run these against `data/sample_sales.csv`.

1. **Which region grew fastest in the last quarter?**  
   **Answer:** East grew fastest at approximately 11.21%. sales growth from 2025-Q4 to 2026-Q1.

2. **What was total sales in the latest quarter?**  
   **Answer:** Total sales in 2026-Q1 were ₹582,000.

3. **Which region had the highest profit in 2025?**  
   **Answer:** North had the highest 2025 profit at ₹85,100.

4. **Which region had the most customers in 2026-Q1?**  
   **Answer:** North had the most customers, with 1,140.

5. **What is the average order value by region in 2026-Q1?**  
   **Answer:** North ₹104.43, South ₹100.74, East ₹102.38, West ₹102.03 approximately.

6. **What was the total profit in 2025-Q4?**  
   **Answer:** ₹79,700.

7. **Which region had the highest sales across the full dataset?**  
   **Answer:** North, with ₹707,000 total sales.

8. **How many orders were placed in 2026-Q1?**  
   **Answer:** 5,680 orders.

9. **What is the profit margin by region in 2026-Q1?**  
   **Answer:** North 16.36%, South 15.26%, East 15.00%, West 15.36% approximately.

10. **Compare North and West sales in 2026-Q1.**  
    **Answer:** North generated ₹165,000 versus West's ₹151,000, so North was ₹14,000 higher.

## Important

The displayed wording is not hard-coded into the agent. Each question is translated into pandas code, executed on the dataset, and the final language answer is generated from the returned computation/evidence.
