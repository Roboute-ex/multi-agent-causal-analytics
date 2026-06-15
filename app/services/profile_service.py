from __future__ import annotations

import pandas as pd

from app.core.schemas import DataProfile


def build_profile(df: pd.DataFrame) -> DataProfile:
    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    categorical_columns = [column for column in df.columns if column not in numeric_columns]

    return DataProfile(
        n_rows=len(df),
        n_cols=len(df.columns),
        numeric_columns=numeric_columns,
        categorical_columns=categorical_columns,
        missing_rate={key: float(value) for key, value in df.isna().mean().round(4).items()},
        dtypes={column: str(dtype) for column, dtype in df.dtypes.items()},
        preview_rows=df.head(5).to_dict(orient="records"),
    )
