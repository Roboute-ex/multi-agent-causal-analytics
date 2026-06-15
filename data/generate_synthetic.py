from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent / "sample_marketing.csv"


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def make_synthetic_marketing_data(n: int = 1200, seed: int = 42) -> pd.DataFrame:
    """生成一份包含二元处理变量和结果变量的营销样例数据。"""
    rng = np.random.default_rng(seed)

    user_id = np.arange(1, n + 1)
    age = rng.integers(18, 70, size=n)
    income = np.clip(rng.normal(65000, 20000, size=n), 20000, 160000).round(2)
    prior_spend = np.clip(rng.gamma(shape=2.2, scale=120, size=n), 0, 2000).round(2)
    visits = rng.poisson(lam=5, size=n)
    region = rng.choice(["north", "south", "east", "west"], size=n)

    coupon_score = (
        -0.7
        + 0.010 * (age - 40)
        + 0.000010 * (income - 65000)
        + 0.070 * visits
        + 0.0008 * prior_spend
    )
    coupon = rng.binomial(1, _sigmoid(coupon_score))

    region_effect = pd.Series(region).map(
        {"north": 0.04, "south": -0.04, "east": 0.02, "west": 0.0}
    ).to_numpy()
    high_engagement = (visits >= 6).astype(float)
    heterogeneous_lift = 0.30 + 0.55 * high_engagement + 0.025 * np.clip(visits - 5, 0, None)
    purchase_score = (
        -3.1
        + 0.014 * (age - 40)
        + 0.000012 * (income - 65000)
        + 0.0032 * prior_spend
        + 0.075 * visits
        + region_effect
        + coupon * heterogeneous_lift
    )
    purchase = rng.binomial(1, _sigmoid(purchase_score))

    revenue_when_purchased = rng.normal(
        loc=75 + 0.035 * prior_spend + 8 * coupon,
        scale=18,
        size=n,
    )
    revenue = np.where(purchase == 1, np.clip(revenue_when_purchased, 5, None), 0)

    return pd.DataFrame(
        {
            "user_id": user_id,
            "age": age,
            "income": income,
            "prior_spend": prior_spend,
            "visits": visits,
            "region": region,
            "coupon": coupon,
            "purchase": purchase,
            "revenue": revenue.round(2),
        }
    )


def main(
    n: int = 1200,
    seed: int = 42,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    df = make_synthetic_marketing_data(n=n, seed=seed)
    df.to_csv(output, index=False)
    print(f"已写入 {len(df)} 行数据到 {output}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成营销样例 CSV 数据。")
    parser.add_argument("--n", type=int, default=1200, help="生成的数据行数。")
    parser.add_argument("--seed", type=int, default=42, help="随机种子。")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="输出 CSV 路径。",
    )
    args = parser.parse_args()
    main(n=args.n, seed=args.seed, output_path=args.output)
