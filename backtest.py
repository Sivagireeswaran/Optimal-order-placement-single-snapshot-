import pandas as pd
import numpy as np
import json
import itertools

ORDER_SIZE = 5000
STEP_SIZE = 100
FEE = 0.002  
REBATE = 0.001  
PARAM_GRID = {
    "lambda_under": [0.01, 0.05],
    "lambda_over": [0.01, 0.05],
    "theta_queue": [0.0, 0.001]
}
DATA_PATH = "\l1_day.csv"

def load_snapshots(path):
    df = pd.read_csv(path)
    df = df.sort_values(by="ts_event")
    df = df.drop_duplicates(subset=["ts_event", "publisher_id"])
    snapshots = []
    for ts, group in df.groupby("ts_event"):
        venues = []
        for _, row in group.iterrows():
            venues.append({
                "venue": row["publisher_id"],
                "ask": row["ask_px_00"],
                "ask_size": row["ask_sz_00"],
                "fee": FEE,
                "rebate": REBATE
            })
        snapshots.append((ts, venues))
    return snapshots


def compute_cost(split, venues, order_size, λo, λu, θ):
    executed = 0
    cash_spent = 0
    for i, q in enumerate(split):
        venue = venues[i]
        exe = min(q, venue["ask_size"])
        executed += exe
        cash_spent += exe * (venue["ask"] + venue["fee"])
        cash_spent -= max(q - exe, 0) * venue["rebate"]
    underfill = max(order_size - executed, 0)
    overfill = max(executed - order_size, 0)
    risk_pen = θ * (underfill + overfill)
    cost_pen = λu * underfill + λo * overfill
    return cash_spent + risk_pen + cost_pen

def allocate(order_size, venues, λo, λu, θ):
    splits = [[]]
    for v in range(len(venues)):
        new_splits = []
        for alloc in splits:
            used = sum(alloc)
            max_v = min(order_size - used, venues[v]["ask_size"])
            for q in range(0, max_v + 1, STEP_SIZE):
                new_splits.append(alloc + [q])
        splits = new_splits
    best_cost = float("inf")
    best_split = []
    for alloc in splits:
        if sum(alloc) != order_size:
            continue
        cost = compute_cost(alloc, venues, order_size, λo, λu, θ)
        if cost < best_cost:
            best_cost = cost
            best_split = alloc
    return best_split, best_cost


def run_strategy(snapshots, λo, λu, θ):
    unfilled = ORDER_SIZE
    total_cost = 0
    cumulative_cost = []
    for _, venues in snapshots:
        if unfilled == 0:
            break
        alloc, _ = allocate(min(unfilled, ORDER_SIZE), venues, λo, λu, θ)
        filled = 0
        cost = 0
        for i, q in enumerate(alloc):
            venue = venues[i]
            exe = min(q, venue["ask_size"])
            cost += exe * (venue["ask"] + venue["fee"])
            cost -= max(q - exe, 0) * venue["rebate"]
            filled += exe
        total_cost += cost
        unfilled -= filled
        cumulative_cost.append(total_cost)
    avg_price = total_cost / (ORDER_SIZE - unfilled) if ORDER_SIZE - unfilled > 0 else 0
    return total_cost, avg_price, cumulative_cost


def run_best_ask(snapshots):
    unfilled = ORDER_SIZE
    total_cost = 0
    for _, venues in snapshots:
        if unfilled == 0:
            break
        best = min(venues, key=lambda v: v["ask"])
        fill = min(unfilled, best["ask_size"])
        total_cost += fill * (best["ask"] + best["fee"])
        unfilled -= fill
    avg_price = total_cost / (ORDER_SIZE - unfilled)
    return total_cost, avg_price
def run_twap(snapshots):
    num_buckets = max(1, len(snapshots) // 60)
    chunk_size = ORDER_SIZE // num_buckets
    total_cost = 0
    total_filled = 0
    snapshot_chunks = len(snapshots) // num_buckets
    for i in range(num_buckets):
        start = i * snapshot_chunks
        end = (i + 1) * snapshot_chunks if i < num_buckets - 1 else len(snapshots)
        chunk = snapshots[start:end]
        remaining = chunk_size
        for _, venues in chunk:
            if remaining == 0:
                break
            best = min(venues, key=lambda v: v["ask"])
            fill = min(remaining, best["ask_size"])
            total_cost += fill * (best["ask"] + best["fee"])
            total_filled += fill
            remaining -= fill
    remaining = ORDER_SIZE - total_filled
    if remaining > 0:
        for _, venues in snapshots:
            if remaining == 0:
                break
            best = min(venues, key=lambda v: v["ask"])
            fill = min(remaining, best["ask_size"])
            total_cost += fill * (best["ask"] + best["fee"])
            total_filled += fill
            remaining -= fill

    avg_price = total_cost / total_filled if total_filled > 0 else 0
    return round(total_cost, 2), round(avg_price, 4), total_filled
def run_vwap(snapshots):
    unfilled = ORDER_SIZE
    total_cost = 0
    total_filled = 0

    for _, venues in snapshots:
        if unfilled == 0:
            break
        total_sz = sum(v["ask_size"] for v in venues)
        if total_sz == 0:
            continue
        for v in venues:
            weight = v["ask_size"] / total_sz
            qty = round(unfilled * weight)
            qty = min(qty, v["ask_size"], unfilled)
            total_cost += qty * (v["ask"] + v["fee"])
            total_filled += qty
            unfilled -= qty
            if unfilled == 0:
                break

    avg_price = total_cost / total_filled if total_filled > 0 else 0
    return total_cost, avg_price


if __name__ == "__main__":
    snapshots = load_snapshots(DATA_PATH)

    best = {"params": None, "cost": float("inf")}
    best_cumcost = []
    for λu, λo, θ in itertools.product(
        PARAM_GRID["lambda_under"],
        PARAM_GRID["lambda_over"],
        PARAM_GRID["theta_queue"]
    ):
        cost, avg_price, cum_cost = run_strategy(snapshots, λo, λu, θ)
        if cost < best["cost"]:
            best.update({
                "params": {"lambda_under": λu, "lambda_over": λo, "theta_queue": θ},
                "cost": cost,
                "avg_price": avg_price
            })
            best_cumcost = cum_cost

    
    bestask_cost, bestask_avg = run_best_ask(snapshots)
    twap_cost, twap_avg, twap_filled = run_twap(snapshots)
    vwap_cost, vwap_avg = run_vwap(snapshots)

    
    def bps_savings(ref_cost):
        return 1000 * (ref_cost - best["cost"]) / ORDER_SIZE

    result = {
        "best_parameters": best["params"],
        "smart_router": {
            "total_cash": round(best["cost"], 2),
            "avg_price": round(best["avg_price"], 4)
        },
        "best_ask": {
            "total_cash": round(bestask_cost, 2),
            "avg_price": round(bestask_avg, 4),
            "savings_bps": round(bps_savings(bestask_cost), 2)
        },
        "twap": {
            "total_cash": round(twap_cost, 2),
            "avg_price": round(twap_avg, 4),
            "savings_bps": round(bps_savings(twap_cost), 2) if twap_filled == ORDER_SIZE else None

        }, 

        "vwap": {
            "total_cash": round(vwap_cost, 2),
            "avg_price": round(vwap_avg, 4),
            "savings_bps": round(bps_savings(vwap_cost), 2)
        }
    }
   
    print(json.dumps(result, indent=2))
    with open("results.json", "w") as f:
        json.dump(result, f, indent=2)
