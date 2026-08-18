import pandas as pd
import pytest

from agent import execute_code, load_data, validate_code


def test_safe_pandas_code():
    df = pd.DataFrame({"Region": ["A", "B"], "Sales": [10, 20]})
    code = """
evidence = df.groupby("Region", as_index=False)["Sales"].sum()
result = evidence.sort_values("Sales", ascending=False).head(1)
note = "Grouped sales by region and selected the maximum."
"""
    result, evidence, note = execute_code(code, df)
    assert result.iloc[0]["Region"] == "B"
    assert result.iloc[0]["Sales"] == 20


def test_import_is_blocked():
    with pytest.raises(ValueError):
        validate_code("import os\nresult = df.head()")


def test_exec_is_blocked():
    with pytest.raises(ValueError):
        validate_code("result = exec('print(1)')")


def test_unknown_name_is_blocked():
    with pytest.raises(ValueError):
        validate_code("result = secret_data")


def test_csv_load(tmp_path):
    file = tmp_path / "demo.csv"
    file.write_text("A,B\n1,2\n3,4\n", encoding="utf-8")
    with file.open("rb") as f:
        df = load_data(type("Upload", (), {"name": "demo.csv", "read": f.read})())
    assert list(df.columns) == ["A", "B"]
