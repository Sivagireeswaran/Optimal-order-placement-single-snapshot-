# Optimal-order-placement-single-snapshot-
# Smart Order Router Backtest – Rama Cont \&  Arseniy Kukanov Model

This project implements and evaluates a **Smart Order Router (SOR)** using the static cost optimization framework introduced by **Cont & Kukanov** in *"Optimal Order Placement in Limit Order Markets"*. The router aims to minimize the total cost of executing a 5000-share buy order across multiple venues using a configurable penalty-based allocation strategy.

# Objective
Configure the optimal execution strategy for a sequential 5000-share buy order by splitting it optimally across multiple venues to minimize total execution cost. Taking into account:
•	Penalties from overfilling and underfilling
•	Liquidity shown at the best ask level
•	Per venue fees and rebates
Comparing the router’s performance against:
•	Best Ask: Lowest available market ask always gets executed instantly
•	TWAP: Time-weighted average price calculated per minute
•	VWAP: Volume-weighted averaging executed price based on displayed volume
________________________________________
# Approach
The goal was to implement the allocator as pseudocode provided to us with Level-1 snapshots data from l1_day.csv. Per timestamp:
•	Generation of feasible order splits
•	Each split along with penalties computed
•	Split is chosen based on total cost minimum
Any non-filled quantity rolls forward from the last snapshot till the entire 5000-share order is filled or data is exhausted.
________________________________________
# Grid Search Calibration
The router executes an exhaustive search for the following set of parameters:
| Parameter | Values | | lambda_over | 0.01, 0.05 | | theta_queue | 0.0, 0.001 |
Parameter combination yielding the lowest total cost is selected as optimal.

