import io
import os
import re
import math
from datetime import date, datetime
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    from PIL import Image
    import pytesseract
except Exception:
    Image = None
    pytesseract = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
except Exception:
    SimpleDocTemplate = None

st.set_page_config(page_title="Marvento Rate Desk", page_icon="🚢", layout="wide")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
TARIFF_STORE = os.path.join(DATA_DIR, "saved_tariffs.csv")

AIR_DIVISOR = 6000
COURIER_DIVISOR = 5000
LAND_DIVISOR = 3333
SEA_KG_PER_CBM = 1000

TARIFF_COLUMNS = [
    "vendor", "mode", "origin", "destination", "service", "currency",
    "min_charge", "rate_per_kg", "rate_per_cbm", "rate_per_container",
    "doc_fee", "fuel_pct", "other_charges", "transit_days", "valid_from", "valid_to", "remarks"
]

SAMPLE_TARIFFS = pd.DataFrame([
    ["SkyLine Air", "Air", "Dubai", "Riyadh", "EXW", "AED", 180, 4.2, 0, 0, 35, 12, 50, 2, "2026-01-01", "2026-12-31", "Air general cargo"],
    ["Gulf Courier", "Courier", "Dubai", "Riyadh", "DDP", "AED", 95, 5.1, 0, 0, 25, 18, 35, 3, "2026-01-01", "2026-12-31", "Express courier"],
    ["Desert Road", "Land", "Dubai", "Dammam", "DAP", "AED", 250, 0.8, 90, 0, 40, 0, 80, 4, "2026-01-01", "2026-12-31", "LTL road"],
    ["Ocean Box", "Sea", "Jebel Ali", "Mombasa", "FOB", "AED", 0, 0, 0, 4200, 150, 0, 250, 18, "2026-01-01", "2026-12-31", "20FT base"],
    ["Ocean Box", "Sea", "Jebel Ali", "Mombasa", "CIF", "AED", 0, 0, 0, 6200, 150, 0, 250, 18, "2026-01-01", "2026-12-31", "40FT base"],
], columns=TARIFF_COLUMNS)

INCOTERMS = ["EXW", "FCA", "FOB", "CIF", "CPT", "DAP", "DDU", "DDP"]
CURRENCIES = ["AED", "USD", "EUR", "GBP", "SAR", "INR"]

# ---------------- Login ----------------
def get_secret(name: str, default: str) -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default

APP_USERNAME = get_secret("APP_USERNAME", "kiran.dxb@marventoshipping.com")
APP_PASSWORD = get_secret("APP_PASSWORD", "ChangeMe123")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("Marvento Rate Desk Login")
    st.info("Default username: kiran.dxb@marventoshipping.com | Default password: ChangeMe123. Change it in Streamlit secrets before sharing the app.")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        if username.strip() == APP_USERNAME and password == APP_PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Wrong username or password")
    st.stop()

# ---------------- Helpers ----------------
def normalize(s: object) -> str:
    return str(s or "").strip().lower()


def contains_match(value: object, query: object) -> bool:
    v = normalize(value)
    q = normalize(query)
    if not q:
        return True
    if not v:
        return False
    return q in v or v in q


def cbm_from_cm(length_cm: float, width_cm: float, height_cm: float, pieces: int) -> float:
    return (length_cm * width_cm * height_cm * pieces) / 1_000_000


def chargeable_weight(mode: str, gross_kg: float, cbm: float) -> float:
    mode_l = normalize(mode)
    if mode_l == "air":
        volumetric = cbm * 1_000_000 / AIR_DIVISOR
    elif mode_l == "courier":
        volumetric = cbm * 1_000_000 / COURIER_DIVISOR
    elif mode_l == "land":
        volumetric = cbm * 1_000_000 / LAND_DIVISOR
    else:
        volumetric = cbm * SEA_KG_PER_CBM
    return round(max(float(gross_kg or 0), float(volumetric or 0)), 2)


def extract_text_from_upload(file) -> str:
    name = file.name.lower()
    data = file.getvalue()
    if name.endswith(".pdf"):
        if pdfplumber is None:
            return "PDF extraction unavailable. Install pdfplumber."
        text = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                text.append(page.extract_text() or "")
        return "\n".join(text)
    if name.endswith((".png", ".jpg", ".jpeg", ".webp")):
        if Image is None or pytesseract is None:
            return "Image OCR is not available on this server. Please paste the enquiry text manually."
        try:
            image = Image.open(io.BytesIO(data))
            return pytesseract.image_to_string(image)
        except Exception as e:
            return f"Image OCR failed: {e}"
    if name.endswith((".csv", ".txt", ".eml")):
        return data.decode("utf-8", errors="ignore")
    if name.endswith((".xlsx", ".xls")):
        try:
            sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
            parts = []
            for sheet, frame in sheets.items():
                parts.append(f"Sheet: {sheet}\n" + frame.astype(str).to_csv(index=False))
            return "\n".join(parts)
        except Exception as e:
            return f"Excel extraction failed: {e}"
    return data.decode("utf-8", errors="ignore")


def clean_tariff(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_").replace("/", "_") for c in df.columns]
    aliases = {
        "carrier": "vendor", "agent": "vendor", "shipping_line": "vendor", "airline": "vendor",
        "aol": "origin", "aod": "destination", "pol": "origin", "pod": "destination",
        "from": "origin", "to": "destination", "origin_port": "origin", "destination_port": "destination",
        "origin_airport": "origin", "destination_airport": "destination",
        "tt": "transit_days", "transit_time": "transit_days",
        "validity_from": "valid_from", "validity_to": "valid_to", "valid_until": "valid_to",
        "rate_kg": "rate_per_kg", "per_kg": "rate_per_kg", "kg_rate": "rate_per_kg",
        "rate_cbm": "rate_per_cbm", "per_cbm": "rate_per_cbm", "cbm_rate": "rate_per_cbm",
        "container_rate": "rate_per_container", "rate_20ft": "rate_per_container", "rate_40ft": "rate_per_container",
        "minimum": "min_charge", "minimum_charge": "min_charge", "min": "min_charge",
        "fuel": "fuel_pct", "fuel_surcharge": "fuel_pct", "doc": "doc_fee", "documentation": "doc_fee",
        "charges": "other_charges", "other": "other_charges", "remarks_notes": "remarks"
    }
    df = df.rename(columns={k: v for k, v in aliases.items() if k in df.columns})
    for col in TARIFF_COLUMNS:
        if col not in df.columns:
            df[col] = 0 if col in ["min_charge", "rate_per_kg", "rate_per_cbm", "rate_per_container", "doc_fee", "fuel_pct", "other_charges", "transit_days"] else ""
    num_cols = ["min_charge", "rate_per_kg", "rate_per_cbm", "rate_per_container", "doc_fee", "fuel_pct", "other_charges", "transit_days"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in [c for c in TARIFF_COLUMNS if c not in num_cols]:
        df[col] = df[col].fillna("").astype(str)
    if "currency" in df.columns:
        df["currency"] = df["currency"].replace("", "AED")
    return df[TARIFF_COLUMNS]


def read_tariff_file(file) -> Tuple[pd.DataFrame, str]:
    name = file.name.lower()
    data = file.getvalue()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(io.BytesIO(data)), ""
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(io.BytesIO(data)), ""
        if name.endswith(".pdf"):
            if pdfplumber is None:
                return pd.DataFrame(), "PDF tariff reading needs pdfplumber."
            frames = []
            text_parts = []
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables() or []:
                        if table and len(table) > 1:
                            header = [str(x or "").strip() for x in table[0]]
                            rows = table[1:]
                            frames.append(pd.DataFrame(rows, columns=header))
                    text_parts.append(page.extract_text() or "")
            if frames:
                return pd.concat(frames, ignore_index=True), ""
            text = "\n".join(text_parts).strip()
            if text:
                return pd.DataFrame([{
                    "vendor": "PDF Tariff Upload", "mode": "", "origin": "", "destination": "", "service": "",
                    "currency": "AED", "remarks": text[:1500]
                }]), "PDF text was extracted but no structured table was found. Use manual quote or convert to Excel/CSV for auto matching."
            return pd.DataFrame(), "No readable text/table found in this PDF. It may be scanned."
    except Exception as e:
        return pd.DataFrame(), f"Could not read {file.name}: {e}"
    return pd.DataFrame(), f"Unsupported file type: {file.name}"


def load_saved_tariffs() -> pd.DataFrame:
    if os.path.exists(TARIFF_STORE):
        try:
            return clean_tariff(pd.read_csv(TARIFF_STORE))
        except Exception:
            return pd.DataFrame(columns=TARIFF_COLUMNS)
    return pd.DataFrame(columns=TARIFF_COLUMNS)


def save_tariffs(df: pd.DataFrame):
    clean_tariff(df).to_csv(TARIFF_STORE, index=False)


def add_uploaded_tariffs(files) -> List[str]:
    messages = []
    frames = [load_saved_tariffs()]
    for file in files or []:
        raw, msg = read_tariff_file(file)
        if msg:
            messages.append(f"{file.name}: {msg}")
        if raw is not None and not raw.empty:
            try:
                cleaned = clean_tariff(raw)
                cleaned["remarks"] = cleaned["remarks"].astype(str) + f" | Source: {file.name}"
                frames.append(cleaned)
            except Exception as e:
                messages.append(f"{file.name}: columns could not be mapped to tariff template ({e})")
    if len(frames) > 1:
        out = pd.concat(frames, ignore_index=True)
        out = out.drop_duplicates(subset=TARIFF_COLUMNS, keep="last")
        save_tariffs(out)
        messages.append(f"Saved {len(out)} active tariff row(s). They will remain after logout/login on this Streamlit app instance.")
    return messages


def active_tariffs() -> pd.DataFrame:
    saved = load_saved_tariffs()
    if saved.empty:
        return clean_tariff(SAMPLE_TARIFFS)
    return saved


def parse_dimensions_and_weight(text: str) -> Tuple[pd.DataFrame, Dict[str, float]]:
    rows: List[Dict[str, float]] = []
    t = text.replace("×", "x").replace("*", "x")
    dim_pattern = re.compile(
        r"(?:(\d+)\s*(?:pcs?|pieces?|ctns?|cartons?)\s*[xX@-]?\s*)?"
        r"(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*(cm|mm|m|inch|in)?",
        re.IGNORECASE,
    )
    for m in dim_pattern.finditer(t):
        pieces = int(m.group(1) or 1)
        l, w, h = float(m.group(2)), float(m.group(3)), float(m.group(4))
        unit = (m.group(5) or "cm").lower()
        if unit == "mm":
            l, w, h = l / 10, w / 10, h / 10
        elif unit == "m":
            l, w, h = l * 100, w * 100, h * 100
        elif unit in ("inch", "in"):
            l, w, h = l * 2.54, w * 2.54, h * 2.54
        rows.append({"pieces": pieces, "length_cm": round(l, 2), "width_cm": round(w, 2), "height_cm": round(h, 2), "cbm": round(cbm_from_cm(l, w, h, pieces), 4)})
    weights = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*(?:kgs?|kg|kilograms?)\b", t, flags=re.I)]
    gross_kg = max(weights) if weights else 0.0
    total_cbm_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:cbm|m3|cubic meter|cubic metres)\b", t, flags=re.I)
    total_cbm = float(total_cbm_matches[-1]) if total_cbm_matches else sum(r["cbm"] for r in rows)
    df = pd.DataFrame(rows)
    summary = {"gross_kg": gross_kg, "cbm": round(total_cbm, 4), "pieces": int(sum(r["pieces"] for r in rows)) if rows else 0}
    return df, summary


def rate_total(row, chargeable_kg: float, cbm: float, containers: int) -> float:
    freight_options = [float(row.get("min_charge", 0) or 0)]
    if float(row.get("rate_per_kg", 0) or 0) > 0:
        freight_options.append(float(row.rate_per_kg) * chargeable_kg)
    if float(row.get("rate_per_cbm", 0) or 0) > 0:
        freight_options.append(float(row.rate_per_cbm) * cbm)
    if float(row.get("rate_per_container", 0) or 0) > 0:
        freight_options.append(float(row.rate_per_container) * max(int(containers or 0), 1))
    freight = max(freight_options)
    fuel = freight * float(row.get("fuel_pct", 0) or 0) / 100
    return round(freight + fuel + float(row.get("doc_fee", 0) or 0) + float(row.get("other_charges", 0) or 0), 2)


def match_rates(tariffs: pd.DataFrame, mode: str, origin: str, destination: str, chargeable_kg: float, cbm: float, containers: int, service: str = "") -> pd.DataFrame:
    df = tariffs.copy()
    mask = df.apply(lambda r: contains_match(r["mode"], mode) and contains_match(r["origin"], origin) and contains_match(r["destination"], destination), axis=1)
    out = df[mask].copy()
    if out.empty:
        # fallback: match origin and destination only, useful when uploaded tariffs have blank mode
        mask = df.apply(lambda r: contains_match(r["origin"], origin) and contains_match(r["destination"], destination), axis=1)
        out = df[mask].copy()
    if out.empty:
        return out
    out["buying_total_aed"] = out.apply(lambda r: rate_total(r, chargeable_kg, cbm, containers), axis=1)
    out = out.sort_values("buying_total_aed").reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    return out


def default_manual_quote_lines() -> pd.DataFrame:
    return pd.DataFrame([
        {"Description": "Freight Charges", "Carrier": "", "Unit": "Shipment", "Unit Price": 0.0, "VAT/Tax": 0.0, "Currency": "AED", "Total": 0.0},
        {"Description": "Documentation", "Carrier": "", "Unit": "Shipment", "Unit Price": 0.0, "VAT/Tax": 0.0, "Currency": "AED", "Total": 0.0},
    ])


def calculate_manual_totals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["Unit Price", "VAT/Tax", "Total"]:
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    calc_total = out["Unit Price"] + out["VAT/Tax"]
    out["Total"] = out["Total"].where(out["Total"] > 0, calc_total)
    return out


def manual_total_aed(df: pd.DataFrame) -> float:
    df = calculate_manual_totals(df)
    return float(df[df["Currency"].astype(str).str.upper().eq("AED")]["Total"].sum())


def make_quote_text(enq: Dict[str, object], quote_lines: pd.DataFrame, total: float, validity: str) -> str:
    rows = []
    for _, r in quote_lines.iterrows():
        desc = str(r.get("Description", "")).strip()
        if not desc:
            continue
        rows.append(f"- {desc} | Carrier: {r.get('Carrier', '') or 'TBA'} | Unit: {r.get('Unit', '')} | Unit Price: {r.get('Currency', 'AED')} {float(r.get('Unit Price', 0) or 0):,.2f} | VAT/Tax: {r.get('Currency', 'AED')} {float(r.get('VAT/Tax', 0) or 0):,.2f} | Total: {r.get('Currency', 'AED')} {float(r.get('Total', 0) or 0):,.2f}")
    location_label_from = enq.get("origin_label", "Origin")
    location_label_to = enq.get("destination_label", "Destination")
    return f"""Dear {enq.get('customer') or 'Customer'},

Thank you for your enquiry. Please find our quote below:

Enquiry No: {enq.get('enquiry_no')}
Mode: {enq.get('mode')}
Service Required: {enq.get('service')}
Rate Validity: {validity or 'TBA'}
{location_label_from}: {enq.get('origin')}
{location_label_to}: {enq.get('destination')}
Gross Weight: {float(enq.get('gross_kg') or 0):,.2f} kg
CBM: {float(enq.get('cbm') or 0):,.4f}
Chargeable Weight: {float(enq.get('chargeable_kg') or 0):,.2f} kg

Quote Lines:
{chr(10).join(rows) if rows else '- TBA'}

Total Selling Quote: AED {total:,.2f}

Remarks: Subject to space, carrier acceptance, customs approval, and final cargo details. Duties, taxes, storage, demurrage, inspection, destination charges, and insurance are excluded unless specifically mentioned.

Best regards,
Marvento Rate Desk"""


def build_auto_quote_lines(best: pd.Series, selling: float) -> pd.DataFrame:
    return pd.DataFrame([{
        "Description": f"Freight Charges - {best.get('service', '')}",
        "Carrier": str(best.get("vendor", "")),
        "Unit": "Shipment",
        "Unit Price": float(selling),
        "VAT/Tax": 0.0,
        "Currency": "AED",
        "Total": float(selling),
    }])


def make_pdf(enq: Dict[str, object], quote_lines: pd.DataFrame, total: float, validity: str) -> bytes:
    if SimpleDocTemplate is None:
        return b""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    story = []
    logo = Table([[Paragraph("<b>MARVENTO SHIPPING</b>", styles["Title"])]], colWidths=[170*mm])
    logo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0B2545")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(logo)
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("<b>Freight Quotation</b>", styles["Heading1"]))
    details = [
        ["Enquiry No", str(enq.get("enquiry_no", "")), "Date", date.today().strftime("%d-%b-%Y")],
        ["Customer", str(enq.get("customer", "")), "Mode", str(enq.get("mode", ""))],
        ["Service", str(enq.get("service", "")), "Validity", validity or "TBA"],
        [str(enq.get("origin_label", "Origin")), str(enq.get("origin", "")), str(enq.get("destination_label", "Destination")), str(enq.get("destination", ""))],
        ["Gross Weight", f"{float(enq.get('gross_kg') or 0):,.2f} kg", "CBM", f"{float(enq.get('cbm') or 0):,.4f}"],
        ["Chargeable Weight", f"{float(enq.get('chargeable_kg') or 0):,.2f} kg", "Containers", str(enq.get("containers", 0))],
    ]
    table = Table(details, colWidths=[35*mm, 55*mm, 35*mm, 45*mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF0F7")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EAF0F7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("<b>Quote Lines</b>", styles["Heading2"]))
    q = calculate_manual_totals(quote_lines)
    data = [["Description", "Carrier", "Unit", "Unit Price", "VAT/Tax", "Currency", "Total"]]
    for _, r in q.iterrows():
        if str(r.get("Description", "")).strip():
            data.append([
                str(r.get("Description", "")), str(r.get("Carrier", "")), str(r.get("Unit", "")),
                f"{float(r.get('Unit Price', 0) or 0):,.2f}", f"{float(r.get('VAT/Tax', 0) or 0):,.2f}", str(r.get("Currency", "AED")), f"{float(r.get('Total', 0) or 0):,.2f}"
            ])
    data.append(["", "", "", "", "", "Total AED", f"{total:,.2f}"])
    qt = Table(data, colWidths=[43*mm, 25*mm, 22*mm, 24*mm, 22*mm, 20*mm, 24*mm])
    qt.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B2545")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (-2, -1), (-1, -1), colors.HexColor("#EAF0F7")),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
    ]))
    story.append(qt)
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("Remarks: Subject to space, carrier acceptance, customs approval, and final cargo details. Duties, taxes, storage, demurrage, inspection, destination charges, and insurance are excluded unless specifically mentioned.", styles["Normal"]))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("Best regards,<br/><b>Marvento Rate Desk</b>", styles["Normal"]))
    doc.build(story)
    return buffer.getvalue()

# ---------------- UI ----------------
with st.sidebar:
    st.image("https://dummyimage.com/420x90/0B2545/ffffff&text=MARVENTO+RATE+DESK", use_container_width=True)
    st.success(f"Logged in as {APP_USERNAME}")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
    st.divider()
    st.header("Tariff Data")
    st.download_button("Download tariff CSV template", data=pd.DataFrame(columns=TARIFF_COLUMNS).to_csv(index=False), file_name="marvento_tariff_template.csv", mime="text/csv")
    st.download_button("Download sample tariff CSV", data=SAMPLE_TARIFFS.to_csv(index=False), file_name="marvento_sample_tariffs.csv", mime="text/csv")
    tariff_uploads = st.file_uploader("Import tariff rates: CSV / Excel / PDF", type=["csv", "xlsx", "xls", "pdf"], accept_multiple_files=True)
    if st.button("Save uploaded tariff files"):
        msgs = add_uploaded_tariffs(tariff_uploads)
        for m in msgs:
            st.info(m)
        st.rerun()
    if st.button("Clear saved tariff database"):
        if os.path.exists(TARIFF_STORE):
            os.remove(TARIFF_STORE)
        st.warning("Saved tariffs cleared. Sample tariffs will show until you upload real tariffs again.")
        st.rerun()

st.title("Marvento Rate Desk")
st.caption("Enquiry -> cargo extraction -> chargeable weight -> tariff match -> ranked rates -> margin -> quote text/PDF")

tariffs = active_tariffs()

tab1, tab2, tab3 = st.tabs(["Rate Desk", "Tariff Table", "Help"])

with tab1:
    st.subheader("1. Enter Enquiry Details")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        enquiry_no = st.text_input("Enquiry No", value=f"MRD-{date.today().strftime('%Y%m%d')}-001")
        customer = st.text_input("Customer")
    with c2:
        mode = st.selectbox("Mode", ["Air", "Courier", "Land", "Sea"])
        service = st.selectbox("Service Required / Incoterm", INCOTERMS)
    if mode == "Air":
        origin_label, destination_label = "AOL", "AOD"
        origin_default, dest_default = "DXB", "RUH"
    elif mode == "Sea":
        origin_label, destination_label = "POL", "POD"
        origin_default, dest_default = "Jebel Ali", "Mombasa"
    else:
        origin_label, destination_label = "Origin", "Destination"
        origin_default, dest_default = "Dubai", "Riyadh"
    with c3:
        origin = st.text_input(origin_label, value=origin_default)
        destination = st.text_input(destination_label, value=dest_default)
    with c4:
        containers = st.number_input("Containers", min_value=0, value=0, step=1)
        rate_validity = st.text_input("Rate Validity", value="Valid for 7 days")

    mcol1, mcol2 = st.columns(2)
    with mcol1:
        margin_method = st.radio("Margin Method", ["% Markup on Buying", "Fixed AED Margin"], horizontal=True)
    with mcol2:
        if margin_method == "% Markup on Buying":
            margin_pct = st.number_input("Margin %", min_value=0.0, value=15.0, step=0.5)
            fixed_margin = 0.0
        else:
            fixed_margin = st.number_input("Fixed Margin AED", min_value=0.0, value=250.0, step=50.0)
            margin_pct = 0.0

    st.subheader("2. Source Dimensions and Weight")
    source_file = st.file_uploader("Upload screenshot/image, email, PDF, CSV, Excel, TXT or EML", type=["pdf", "txt", "eml", "csv", "xlsx", "xls", "png", "jpg", "jpeg", "webp"])
    pasted = st.text_area("Or paste enquiry/email text here", height=110, placeholder="Example: 3 pcs x 60 x 50 x 40 cm, gross weight 85 kg")
    extracted_text = ""
    if source_file:
        extracted_text = extract_text_from_upload(source_file)
    if pasted:
        extracted_text += "\n" + pasted
    parsed_dims = pd.DataFrame()
    parsed_summary = {"gross_kg": 0.0, "cbm": 0.0, "pieces": 0}
    if extracted_text.strip():
        parsed_dims, parsed_summary = parse_dimensions_and_weight(extracted_text)
        with st.expander("View extracted text and detected dimensions"):
            st.text_area("Extracted text", value=extracted_text[:15000], height=160)
            if not parsed_dims.empty:
                st.dataframe(parsed_dims, use_container_width=True)
    w1, w2, w3 = st.columns(3)
    with w1:
        gross_kg = st.number_input("Gross Weight KG", min_value=0.0, value=float(parsed_summary["gross_kg"]), step=1.0)
    with w2:
        cbm = st.number_input("CBM", min_value=0.0, value=float(parsed_summary["cbm"]), step=0.01, format="%.4f")
    with w3:
        pieces = st.number_input("Pieces", min_value=0, value=int(parsed_summary["pieces"]), step=1)
    with st.expander("Manual dimension calculator"):
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            p = st.number_input("Pieces per line", min_value=1, value=1, step=1)
        with d2:
            l = st.number_input("Length cm", min_value=0.0, value=0.0, step=1.0)
        with d3:
            w = st.number_input("Width cm", min_value=0.0, value=0.0, step=1.0)
        with d4:
            h = st.number_input("Height cm", min_value=0.0, value=0.0, step=1.0)
        manual_cbm = cbm_from_cm(l, w, h, p) if l and w and h else 0.0
        st.info(f"Manual line CBM: {manual_cbm:.4f}")
    chargeable_kg = chargeable_weight(mode, gross_kg, cbm)
    v1, v2, v3 = st.columns(3)
    v1.metric("Gross Weight", f"{gross_kg:,.2f} kg")
    v2.metric("CBM", f"{cbm:,.4f}")
    v3.metric("Chargeable Weight", f"{chargeable_kg:,.2f} kg")

    enq = {
        "enquiry_no": enquiry_no, "customer": customer, "mode": mode, "service": service,
        "origin": origin, "destination": destination, "origin_label": origin_label, "destination_label": destination_label,
        "gross_kg": gross_kg, "cbm": cbm, "chargeable_kg": chargeable_kg, "containers": containers
    }

    st.subheader("3. Quote Source")
    quote_source = st.radio("Choose quotation method", ["Auto quote from saved tariff", "Manual quote"], horizontal=True)

    final_quote_lines = pd.DataFrame()
    final_total = 0.0

    if quote_source == "Auto quote from saved tariff":
        st.subheader("4. Auto Quote - Matching Tariff Rates")
        ranked = match_rates(tariffs, mode, origin, destination, chargeable_kg, cbm, containers, service)
        if ranked.empty:
            st.warning("No matching tariff found. Check AOL/AOD or POL/POD names, or upload tariff files with matching lanes.")
        else:
            st.success(f"{len(ranked)} matching tariff(s) found. Select the option to quote.")
            st.dataframe(ranked, use_container_width=True)
            option = st.selectbox(
                "Select rate option for quote",
                list(ranked.index),
                format_func=lambda i: f"Rank {int(ranked.loc[i, 'rank'])} | {ranked.loc[i, 'vendor']} | {ranked.loc[i, 'service']} | Buying AED {float(ranked.loc[i, 'buying_total_aed']):,.2f}"
            )
            best = ranked.loc[option]
            buying = float(best["buying_total_aed"])
            if margin_method == "% Markup on Buying":
                selling = round(buying * (1 + margin_pct / 100), 2)
            else:
                selling = round(buying + fixed_margin, 2)
            margin_aed = selling - buying
            margin_on_selling = (margin_aed / selling * 100) if selling else 0
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Buying Cost", f"AED {buying:,.2f}")
            k2.metric("Selling Quote", f"AED {selling:,.2f}")
            k3.metric("Margin AED", f"AED {margin_aed:,.2f}")
            k4.metric("Margin on Selling", f"{margin_on_selling:.2f}%")
            final_quote_lines = build_auto_quote_lines(best, selling)
            final_total = float(selling)
            st.write("Quote line used for PDF/text:")
            st.dataframe(final_quote_lines, use_container_width=True)
    else:
        st.subheader("4. Manual Quote Option")
        st.info("Enter quote lines manually. Total is calculated as Unit Price + VAT/Tax when Total is left as 0.")
        manual_df = st.data_editor(
            default_manual_quote_lines(),
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Description": st.column_config.TextColumn("Description"),
                "Carrier": st.column_config.TextColumn("Carrier"),
                "Unit": st.column_config.TextColumn("Unit"),
                "Unit Price": st.column_config.NumberColumn("Unit Price", min_value=0.0, step=1.0),
                "VAT/Tax": st.column_config.NumberColumn("VAT/Tax", min_value=0.0, step=1.0),
                "Currency": st.column_config.SelectboxColumn("Currency", options=CURRENCIES),
                "Total": st.column_config.NumberColumn("Total", min_value=0.0, step=1.0),
            },
            key="manual_quote_lines_v3",
        )
        final_quote_lines = calculate_manual_totals(manual_df)
        st.write("Calculated manual quote totals:")
        st.dataframe(final_quote_lines, use_container_width=True)
        final_total = manual_total_aed(final_quote_lines)
        st.metric("Manual Quote Total AED", f"AED {final_total:,.2f}")

    st.subheader("5. Prepared Quote Text and PDF")
    quote_text = make_quote_text(enq, final_quote_lines, final_total, rate_validity)
    st.text_area("Prepared Quote Text", quote_text, height=340)
    st.download_button("Download quote text", quote_text, file_name=f"{enquiry_no}_quote.txt", mime="text/plain")
    pdf_bytes = make_pdf(enq, final_quote_lines, final_total, rate_validity)
    if pdf_bytes:
        st.download_button("Create / Download PDF quote with Marvento logo", pdf_bytes, file_name=f"{enquiry_no}_marvento_quote.pdf", mime="application/pdf")
    else:
        st.error("PDF package is not installed. Please ensure reportlab is in requirements.txt.")

with tab2:
    st.subheader("Active Tariff Table")
    st.caption("Saved uploaded tariffs are shown here. They remain after logout/login on the same Streamlit app instance.")
    edited = st.data_editor(tariffs, num_rows="dynamic", use_container_width=True, key="tariff_editor")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Save tariff table changes"):
            save_tariffs(edited)
            st.success("Tariff table saved.")
            st.rerun()
    with col_b:
        st.download_button("Download active tariff table", clean_tariff(edited).to_csv(index=False), file_name="active_marvento_tariffs.csv", mime="text/csv")

with tab3:
    st.subheader("How to use V3")
    st.markdown("""
1. Upload one or many tariff files from the left side, then click **Save uploaded tariff files**. Supported: CSV, Excel, PDF. PDF table extraction is best-effort.
2. Tariffs now save to the app's tariff database, so they do not disappear when you logout/login.
3. For **Air**, use **AOL/AOD**. For **Sea**, use **POL/POD**.
4. Choose service term: EXW, FCA, FOB, CIF, CPT, DAP, DDU, or DDP. Add rate validity.
5. Use **Auto quote from saved tariff** to select one matched option, or use **Manual quote** to enter your own lines.
6. Manual quote line headers are: Description, Carrier, Unit, Unit Price, VAT/Tax, Currency, Total.
7. PDF quote can be downloaded with Marvento branding.

Important: Streamlit free hosting has basic file storage. For a proper multi-user production system, the tariff database should be moved to SharePoint, OneDrive, SQL, or another permanent database.
""")
