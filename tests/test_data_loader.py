from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.services.data_loader import is_excel_file, is_supported_file, list_excel_sheets, read_dataset
from data.generate_synthetic import make_synthetic_marketing_data

ARTIFACT_DIR = Path("test_artifacts")


def test_read_csv_dataset():
    ARTIFACT_DIR.mkdir(exist_ok=True)
    csv_path = ARTIFACT_DIR / "sample.csv"
    expected = make_synthetic_marketing_data(n=20, seed=7)
    expected.to_csv(csv_path, index=False)

    actual = read_dataset(csv_path)

    assert actual.shape == expected.shape
    assert is_supported_file(csv_path)
    assert not is_excel_file(csv_path)


def test_read_xlsx_dataset():
    if importlib.util.find_spec("openpyxl") is None:
        pytest.skip("openpyxl 未安装，跳过 Excel 读取测试。")

    ARTIFACT_DIR.mkdir(exist_ok=True)
    xlsx_path = ARTIFACT_DIR / "sample.xlsx"
    expected = make_synthetic_marketing_data(n=20, seed=8)
    expected.to_excel(xlsx_path, sheet_name="marketing", index=False)

    sheets = list_excel_sheets(xlsx_path)
    actual = read_dataset(xlsx_path, sheet_name="marketing")

    assert sheets == ["marketing"]
    assert actual.shape == expected.shape
    assert is_supported_file(xlsx_path)
    assert is_excel_file(xlsx_path)
