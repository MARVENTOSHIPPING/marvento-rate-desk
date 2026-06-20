import io
import re
import math
import hashlib
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

st.set_page_config(page_title="Marvento Rate Desk", page_icon="🚢", layout="wide")

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
    ["SkyLine Air", "Air", "Dubai", "Riyadh", "Airport-Airport", "AED", 180, 4.2, 0, 0, 35, 12, 50, 2, "2026-01-01", "2026-12-31", "General cargo"],
    ["Gulf Courier", "Courier", "Dubai", "Riyadh", "Door-Door", "AED", 95, 5.1, 0, 0, 25, 18, 35, 3, "2026-01-01", "2026-12-31", "Express"],
    ["Desert Road", "Land", "Dubai", "Dammam", "LTL", "AED", 250, 0.8, 90, 0, 40, 0, 80, 4, "2026-01-01", "2026-12-31", "LTL road"],
    ["Ocean Box", "Sea", "Jebel Ali", "Mombasa", "20FT", "AED", 0, 0, 0, 4200, 150, 0, 250, 18, "2026-01-01", "2026-12-31", "20FT base"],
    ["Ocean Box", "Sea", "Jebel Ali", "Mombasa", "40FT", "AED", 0, 0, 0, 6200, 150, 0, 250, 18, "2026-01-01", "2026-12-31", "40FT base"],
], columns=TARIFF_COLUMNS)

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
    return round(max(gross_kg, volumetric), 2)


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
            return "Image OCR is not available on this computer/server. Please paste the enquiry text manually."
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


def clean_tariff(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    aliases = {"carrier":"vendor", "agent":"vendor", "pol":"origin", "pod":"destination", "from":"origin", "to":"destination", "tt":"transit_days", "validity_from":"valid_from", "validity_to":"valid_to"}
    df = df.rename(columns={k:v for k,v in aliases.items() if k in df.columns})
    for col in TARIFF_COLUMNS:
        if col not in df.columns:
            df[col] = 0 if col in ["min_charge", "rate_per_kg", "rate_per_cbm", "rate_per_container", "doc_fee", "fuel_pct", "other_charges", "transit_days"] else ""
    num_cols = ["min_charge", "rate_per_kg", "rate_per_cbm", "rate_per_container", "doc_fee", "fuel_pct", "other_charges", "transit_days"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df[TARIFF_COLUMNS]


def rate_total(row, chargeable_kg: float, cbm: float, containers: int) -> float:
    freight_options = [float(row.min_charge)]
    if float(row.rate_per_kg) > 0:
        freight_options.append(float(row.rate_per_kg) * chargeable_kg)
    if float(row.rate_per_cbm) > 0:
        freight_options.append(float(row.rate_per_cbm) * cbm)
    if float(row.rate_per_container) > 0:
        freight_options.append(float(row.rate_per_container) * max(containers, 1))
    freight = max(freight_options)
    fuel = freight * float(row.fuel_pct) / 100
    return round(freight + fuel + float(row.doc_fee) + float(row.other_charges), 2)


def match_rates(tariffs: pd.DataFrame, mode: str, origin: str, destination: str, chargeable_kg: float, cbm: float, containers: int) -> pd.DataFrame:
    df = tariffs.copy()
    mask = df.apply(lambda r: contains_match(r["mode"], mode) and contains_match(r["origin"], origin) and contains_match(r["destination"], destination), axis=1)
    out = df[mask].copy()
    if out.empty:
        return out
    out["buying_total_aed"] = out.apply(lambda r: rate_total(r, chargeable_kg, cbm, containers), axis=1)
    out = out.sort_values("buying_total_aed").reset_index(drop=True)
    out.insert(0, "rank", range(1, len(out) + 1))
    return out


def make_quote_text(enq: Dict[str, str], best: pd.Series, buying: float, margin_pct: float, selling: float, chargeable_kg: float, cbm: float, margin_aed: float) -> str:
    return f"""Dear {enq.get('customer') or 'Customer'},

Thank you for your enquiry. Please find our freight quote below:

Enquiry No: {enq['enquiry_no']}
Mode: {enq['mode']}
Origin: {enq['origin']}
Destination: {enq['destination']}
Gross Weight: {enq['gross_kg']} kg
CBM: {cbm:.3f}
Chargeable Weight: {chargeable_kg:.2f} kg
Service: {best.get('service', '')}
Transit Time: {int(best.get('transit_days', 0)) if float(best.get('transit_days', 0)) else 'TBA'} days

Selling Quote: AED {selling:,.2f}

Remarks: Subject to space, carrier acceptance, customs approval, and final cargo details. Duties, taxes, storage, demurrage, inspection, destination charges, and insurance are excluded unless specifically mentioned.

Best regards,
Marvento Rate Desk"""

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
    tariff_upload = st.file_uploader("Import real tariff rates by CSV/Excel", type=["csv", "xlsx", "xls"])

st.title("Marvento Rate Desk")
st.caption("Enquiry → AI-assisted cargo extraction → chargeable weight → tariff match → ranked rates → margin → quote text")

if tariff_upload:
    if tariff_upload.name.lower().endswith(".csv"):
        tariffs = clean_tariff(pd.read_csv(tariff_upload))
    else:
        tariffs = clean_tariff(pd.read_excel(tariff_upload))
else:
    tariffs = clean_tariff(SAMPLE_TARIFFS)

tab1, tab2, tab3 = st.tabs(["Rate Desk", "Tariff Table", "Help"])

with tab1:
    st.subheader("1. Enter Enquiry Details")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        enquiry_no = st.text_input("Enquiry No", value=f"MRD-{date.today().strftime('%Y%m%d')}-001")
        customer = st.text_input("Customer")
    with c2:
        mode = st.selectbox("Mode", ["Air", "Courier", "Land", "Sea"])
        service = st.text_input("Service Required", value="Door-Door")
    with c3:
        origin = st.text_input("Origin", value="Dubai")
        destination = st.text_input("Destination", value="Riyadh")
    with c4:
        containers = st.number_input("Containers", min_value=0, value=0, step=1)
        margin_method = st.radio("Margin Method", ["% Markup on Buying", "Fixed AED Margin"], horizontal=False)

    margin_pct = 15.0
    fixed_margin = 0.0
    if margin_method == "% Markup on Buying":
        margin_pct = st.number_input("Margin %", min_value=0.0, value=15.0, step=0.5)
    else:
        fixed_margin = st.number_input("Fixed Margin AED", min_value=0.0, value=250.0, step=50.0)

    st.subheader("2. Source Dimensions and Weight")
    source_file = st.file_uploader("Upload screenshot/image, email, PDF, CSV, Excel, TXT or EML", type=["pdf", "txt", "eml", "csv", "xlsx", "xls", "png", "jpg", "jpeg", "webp"])
    pasted = st.text_area("Or paste enquiry/email text here", height=120, placeholder="Example: 3 pcs x 60 x 50 x 40 cm, gross weight 85 kg")

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
            st.text_area("Extracted text", value=extracted_text[:15000], height=180)
            if not parsed_dims.empty:
                st.dataframe(parsed_dims, use_container_width=True)

    m1, m2, m3 = st.columns(3)
    with m1:
        gross_kg = st.number_input("Gross Weight KG", min_value=0.0, value=float(parsed_summary["gross_kg"]), step=1.0)
    with m2:
        cbm = st.number_input("CBM", min_value=0.0, value=float(parsed_summary["cbm"]), step=0.01, format="%.4f")
    with m3:
        pieces = st.number_input("Pieces", min_value=0, value=int(parsed_summary["pieces"]), step=1)

    with st.expander("Manual dimension calculator"):
        st.write("Enter one cargo line. Copy the calculated CBM into the CBM field above if required.")
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

    st.subheader("3. Matching Tariff Rates")
    ranked = match_rates(tariffs, mode, origin, destination, chargeable_kg, cbm, containers)

    if ranked.empty:
        st.warning("No matching tariff found. Check mode/origin/destination spelling or upload a tariff file with matching lanes.")
    else:
        st.success(f"{len(ranked)} matching tariff(s) found. Ranked by lowest total AED cost.")
        st.dataframe(ranked, use_container_width=True)
        best_index = st.selectbox("Choose rate for quote", ranked.index, format_func=lambda i: f"Rank {ranked.loc[i, 'rank']} - {ranked.loc[i, 'vendor']} - AED {ranked.loc[i, 'buying_total_aed']:,.2f}")
        best = ranked.loc[best_index]
        buying = float(best["buying_total_aed"])
        if margin_method == "% Markup on Buying":
            selling = round(buying * (1 + margin_pct / 100), 2)
        else:
            selling = round(buying + fixed_margin, 2)
        margin_aed = round(selling - buying, 2)
        actual_margin_pct = round((margin_aed / selling * 100), 2) if selling else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Buying Cost", f"AED {buying:,.2f}")
        k2.metric("Selling Quote", f"AED {selling:,.2f}")
        k3.metric("Margin AED", f"AED {margin_aed:,.2f}")
        k4.metric("Margin on Selling", f"{actual_margin_pct:.2f}%")

        st.subheader("4. Prepared Quote Text")
        enq = {"enquiry_no": enquiry_no, "customer": customer, "mode": mode, "origin": origin, "destination": destination, "gross_kg": gross_kg}
        quote_text = make_quote_text(enq, best, buying, margin_pct, selling, chargeable_kg, cbm, margin_aed)
        st.text_area("Quote text", quote_text, height=320)
        st.download_button("Download quote as TXT", quote_text, file_name=f"{enquiry_no}_quote.txt", mime="text/plain")

with tab2:
    st.subheader("Imported / Active Tariff Table")
    st.dataframe(tariffs, use_container_width=True)
    st.download_button("Download active tariff table", tariffs.to_csv(index=False), file_name="active_marvento_tariffs.csv", mime="text/csv")

with tab3:
    st.subheader("How to use")
    st.markdown("""
1. Enter customer, mode, origin and destination.  
2. Upload enquiry email/PDF/Excel/text/image or paste the enquiry text.  
3. Confirm gross weight, CBM and pieces.  
4. Upload real tariff CSV/Excel from the left side, or use the sample data.  
5. The app matches lanes and ranks rates by lowest AED buying cost.  
6. Enter margin and copy/download the quote text.  

**Security:** Change `APP_USERNAME` and `APP_PASSWORD` in Streamlit Cloud secrets. You may set them to the same login you personally use elsewhere, but the app cannot read your ChatGPT password automatically.
""")
