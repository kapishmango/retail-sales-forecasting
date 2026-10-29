"""UCI Online Retail II ingestion. Raw data is downloaded, never vendored."""
from pathlib import Path
import hashlib
import json
import urllib.request
import zipfile
import pandas as pd

SOURCE_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
SOURCE_DOI = "https://doi.org/10.24432/C5CG6D"

def download(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "online_retail_II.xlsx"
    if target.exists():
        return target
    archive = destination / "online-retail-ii.zip.part"
    try:
        with urllib.request.urlopen(SOURCE_URL, timeout=120) as response, archive.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        with zipfile.ZipFile(archive) as bundle:
            members = [name for name in bundle.namelist() if name.lower().endswith(".xlsx")]
            if len(members) != 1:
                raise ValueError("Expected exactly one workbook in the UCI download")
            temporary = target.with_suffix(".xlsx.part")
            temporary.write_bytes(bundle.read(members[0]))
            temporary.replace(target)
    finally:
        archive.unlink(missing_ok=True)
    return target

def load_transactions(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, dtype={"Invoice": str, "StockCode": str, "Customer ID": str})
    else:
        sheets = pd.read_excel(path, sheet_name=None, dtype={"Invoice": str, "StockCode": str, "Customer ID": str})
        frame = pd.concat(sheets.values(), ignore_index=True)
    frame = frame.rename(columns={"Invoice": "invoice_id", "InvoiceNo": "invoice_id",
        "StockCode": "product_id", "Description": "description", "Quantity": "quantity",
        "InvoiceDate": "date", "Price": "unit_price", "UnitPrice": "unit_price",
        "Customer ID": "customer_id", "CustomerID": "customer_id", "Country": "country"})
    required = {"invoice_id", "product_id", "quantity", "date", "unit_price", "customer_id", "country"}
    if missing := required - set(frame.columns):
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if "description" not in frame:
        frame["description"] = ""
    return frame

def clean_transactions(frame):
    frame = frame.copy()
    audit = {"input_rows": len(frame)}
    frame = frame.drop_duplicates()
    audit["duplicate_rows"] = audit["input_rows"] - len(frame)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ["quantity", "unit_price"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ["invoice_id", "product_id", "customer_id"]:
        frame[column] = frame[column].astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    invalid = (frame["date"].isna() | frame["quantity"].isna() | frame["unit_price"].isna()
               | frame["invoice_id"].isna() | frame["product_id"].isna())
    audit["invalid_rows"] = int(invalid.sum())
    frame = frame.loc[~invalid].copy()
    # C-prefixed invoices and negative quantities are kept in their own ledger.
    returned = frame["invoice_id"].str.upper().str.startswith("C") | frame["quantity"].lt(0)
    returns = frame.loc[returned].copy()
    frame = frame.loc[~returned].copy()
    audit["return_or_cancellation_rows"] = len(returns)
    invalid_sale = frame["quantity"].le(0) | frame["unit_price"].le(0)
    audit["nonpositive_sale_rows"] = int(invalid_sale.sum())
    frame = frame.loc[~invalid_sale].copy()
    # Exclude postage, manual adjustments, discounts and non-merchandise codes.
    merchandise = frame["product_id"].str.fullmatch(r"[0-9]{5}[A-Za-z]?").fillna(False)
    audit["non_merchandise_rows"] = int((~merchandise).sum())
    frame = frame.loc[merchandise].copy()
    frame["revenue"] = frame["quantity"] * frame["unit_price"]
    returns["revenue"] = returns["quantity"] * returns["unit_price"]
    frame["description"] = frame["description"].fillna("").astype(str)
    frame["store_id"] = "UK_ONLINE"
    audit["sales_rows"] = len(frame)
    audit["sales_missing_customer_id"] = int(frame["customer_id"].isna().sum())
    return frame, returns, audit

def provenance(path):
    path = Path(path)
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            hasher.update(block)
    return {"source": "UCI Online Retail II", "doi": SOURCE_DOI,
            "license": "CC BY 4.0", "file_name": path.name,
            "sha256": hasher.hexdigest(), "bytes": path.stat().st_size}

def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False, default=str) + "\n", encoding="utf-8")
