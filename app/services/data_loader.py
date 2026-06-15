from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd


EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm"}
CSV_EXTENSIONS = {".csv"}
SUPPORTED_EXTENSIONS = CSV_EXTENSIONS | EXCEL_EXTENSIONS


def read_dataset(source: str | Path | BinaryIO, sheet_name: str | int | None = None) -> pd.DataFrame:
    extension = _extension_from_source(source)
    if extension in CSV_EXTENSIONS:
        return pd.read_csv(source)
    if extension in EXCEL_EXTENSIONS:
        return _read_excel(source, sheet_name=sheet_name)
    raise ValueError(f"暂不支持该文件格式：{extension or '未知格式'}。请上传 CSV、XLSX、XLS 或 XLSM 文件。")


def list_excel_sheets(source: str | Path | BinaryIO) -> list[str]:
    try:
        excel_file = pd.ExcelFile(source)
    except ImportError as exc:
        raise ImportError("读取 Excel 文件需要安装 openpyxl 或 xlrd。") from exc
    return list(excel_file.sheet_names)


def is_excel_file(file_name: str | Path) -> bool:
    return Path(str(file_name)).suffix.lower() in EXCEL_EXTENSIONS


def is_supported_file(file_name: str | Path) -> bool:
    return Path(str(file_name)).suffix.lower() in SUPPORTED_EXTENSIONS


def _read_excel(source: str | Path | BinaryIO, sheet_name: str | int | None = None) -> pd.DataFrame:
    try:
        selected_sheet = 0 if sheet_name is None else sheet_name
        return pd.read_excel(source, sheet_name=selected_sheet)
    except ImportError as exc:
        raise ImportError("读取 Excel 文件需要安装 openpyxl；旧版 .xls 可能还需要 xlrd。") from exc


def _extension_from_source(source: str | Path | BinaryIO) -> str:
    if isinstance(source, (str, Path)):
        return Path(source).suffix.lower()
    name = getattr(source, "name", "")
    return Path(str(name)).suffix.lower()
