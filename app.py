import base64
from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage

APP_USER = "kiran.dxb@marventoshipping.com"
APP_PASS = "ChangeMe123"
LOGO_FILE = Path(__file__).parent / "marvento_logo.png"

MARVENTO = {
    "name": "MARVENTO SHIPPING LLC",
    "address": "Office 210, Al Nakheel Building, Karama",
    "phone": "+97143535822",
    "email": "hello@marventoshipping.com",
    "website": "www.marventoshipping.com",
    "trn": "104851107300003",
}
PINK = "#E91E8F"
NAVY = "#0B3A82"

st.set_page_config(page_title="Marvento Rate Desk", page_icon="🚢", layout="wide")

st.markdown(
    f"""
    <style>
    .main .block-container {{max-width: 1250px; padding-top: 2rem;}}
    div.stButton > button {{background:{NAVY}; color:white; border-radius:8px; border:0;}}
    div.stDownloadButton > button {{background:{PINK}; color:white; border-radius:8px; border:0;}}
    .mv-card {{border:1px solid #e7e7ef; border-radius:14px; padding:18px; background:#ffffff; box-shadow:0 1px 4px rgba(0,0,0,0.04);}}
    .mv-total {{background:#f9fbff; border-left:6px solid {PINK}; border-radius:12px; padding:16px;}}
    .small-muted {{color:#6b7280; font-size:14px;}}
    </style>
    """,
    unsafe_allow_html=True,
)


def image_to_base64(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def header():
    c1, c2 = st.columns([1.2, 3.8])
    with c1:
        if LOGO_FILE.exists():
            st.image(str(LOGO_FILE), width=260)
        else:
            st.markdown(f"<h2 style='color:{PINK};'>MARVENTO</h2>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<h1 style='color:{NAVY}; margin-bottom:0;'>Marvento Rate Desk</h1>", unsafe_allow_html=True)
        st.markdown("<div class='small-muted'>Manual quotation builder → selling total → professional PDF quote</div>", unsafe_allow_html=True)


def login():
    header()
    st.divider()
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username.strip().lower() == APP_USER.lower() and password == APP_PASS:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Invalid username or password")


def fmt_money(v):
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "0.00"


def init_state():
    if "quote_lines" not in st.session_state:
        st.session_state.quote_lines = [
            {"Description": "Freight Charges", "Carrier": "", "Unit": 1.0, "Unit Price": 0.0, "VAT/Tax %": 0.0, "Currency": "AED"},
            {"Description": "Documentation", "Carrier": "", "Unit": 1.0, "Unit Price": 0.0, "VAT/Tax %": 0.0, "Currency": "AED"},
            {"Description": "", "Carrier": "", "Unit": 1.0, "Unit Price": 0.0, "VAT/Tax %": 0.0, "Currency": "AED"},
        ]
    if "cargo_lines" not in st.session_state:
        st.session_state.cargo_lines = [{"Equipment": "20DV", "Qty": 1, "Gross Weight KG": 0.0, "Cargo Details": ""}]


def line_total(line):
    unit = float(line.get("Unit", 0) or 0)
    price = float(line.get("Unit Price", 0) or 0)
    vat = float(line.get("VAT/Tax %", 0) or 0)
    return unit * price * (1 + vat / 100)


def make_pdf(enq, lines, totals_by_currency, total_aed):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=14*mm, leftMargin=14*mm, topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="MVTitle", parent=styles["Heading1"], textColor=colors.HexColor(NAVY), fontSize=18, leading=22))
    styles.add(ParagraphStyle(name="MVSmall", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor(NAVY)))
    styles.add(ParagraphStyle(name="MVNormal", parent=styles["Normal"], fontSize=9, leading=12))
    elements = []

    logo_obj = ""
    if LOGO_FILE.exists():
        logo_obj = RLImage(str(LOGO_FILE), width=58*mm, height=20*mm)
    company_text = Paragraph(
        f"<b>{MARVENTO['name']}</b><br/>{MARVENTO['address']}<br/>Tel: {MARVENTO['phone']}<br/>Email: {MARVENTO['email']} | {MARVENTO['website']}<br/>TRN: {MARVENTO['trn']}",
        styles["MVSmall"],
    )
    header_tbl = Table([[logo_obj, company_text]], colWidths=[78*mm, 94*mm])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ALIGN", (0,0), (0,0), "LEFT"),
        ("ALIGN", (1,0), (1,0), "RIGHT"),
    ]))
    elements.append(header_tbl)
    elements.append(Spacer(1, 8*mm))
    elements.append(Paragraph("QUOTATION", styles["MVTitle"]))
    elements.append(Spacer(1, 3*mm))

    details = [
        ["Quote No", enq.get("quote_no", ""), "Date", enq.get("quote_date", "")],
        ["Customer", enq.get("customer", ""), "Validity", enq.get("validity", "")],
        ["Mode", enq.get("mode", ""), "Service Term", enq.get("service", "")],
        ["Origin", enq.get("origin", ""), "Destination", enq.get("destination", "")],
    ]
    details_tbl = Table(details, colWidths=[27*mm, 58*mm, 27*mm, 58*mm])
    details_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke),
        ("TEXTCOLOR", (0,0), (-1,-1), colors.HexColor(NAVY)),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("LEADING", (0,0), (-1,-1), 10),
    ]))
    elements.append(details_tbl)
    elements.append(Spacer(1, 5*mm))

    quote_data = [["Description", "Carrier", "Unit", "Unit Price", "VAT/Tax %", "Currency", "Total"]]
    for l in lines:
        if str(l.get("Description", "")).strip() or float(l.get("Unit Price", 0) or 0) > 0:
            total = line_total(l)
            quote_data.append([
                str(l.get("Description", "")), str(l.get("Carrier", "")), fmt_money(l.get("Unit", 0)),
                fmt_money(l.get("Unit Price", 0)), fmt_money(l.get("VAT/Tax %", 0)), str(l.get("Currency", "AED")), fmt_money(total)
            ])
    quote_tbl = Table(quote_data, colWidths=[45*mm, 28*mm, 16*mm, 24*mm, 20*mm, 18*mm, 25*mm])
    quote_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(NAVY)),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("ALIGN", (2,1), (-1,-1), "RIGHT"),
        ("ALIGN", (5,1), (5,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    elements.append(quote_tbl)
    elements.append(Spacer(1, 5*mm))

    totals_rows = [["Currency", "Total"]] + [[cur, fmt_money(val)] for cur, val in totals_by_currency.items()]
    totals_rows.append(["Total AED Equivalent", fmt_money(total_aed)])
    totals_tbl = Table(totals_rows, colWidths=[50*mm, 45*mm], hAlign="RIGHT")
    totals_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor(PINK)),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),
        ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#FDE7F3")),
        ("GRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("ALIGN", (1,1), (1,-1), "RIGHT"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
    ]))
    elements.append(totals_tbl)
    elements.append(Spacer(1, 5*mm))

    terms = enq.get("terms", "") or "Rates are subject to space/equipment availability and final carrier confirmation."
    elements.append(Paragraph("<b>Terms & Conditions</b>", styles["MVNormal"]))
    elements.append(Paragraph(terms.replace("\n", "<br/>"), styles["MVNormal"]))
    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("Regards,<br/><b>Marvento Shipping LLC</b>", styles["MVNormal"]))
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login()
    st.stop()

init_state()

with st.sidebar:
    if LOGO_FILE.exists():
        st.image(str(LOGO_FILE), width=260)
    st.success(f"Logged in as\n{APP_USER}")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
    st.divider()
    st.caption("Manual quotation version. Tariff and auto-rate functions removed.")

header()
st.divider()

st.subheader("1. Enquiry Details")
c1, c2, c3, c4 = st.columns(4)
with c1:
    quote_no = st.text_input("Quote / Enquiry No", value=f"MRD-{date.today().strftime('%Y%m%d')}-001")
    customer = st.text_input("Customer")
with c2:
    mode = st.selectbox("Mode", ["Air", "Sea", "Courier", "Land"], index=1)
    service = st.selectbox("Service Required / Incoterm", ["EXW", "FCA", "FOB", "CIF", "CPT", "DAP", "DDU", "DDP"])
with c3:
    origin_label = "POL" if mode == "Sea" else ("AOL" if mode == "Air" else "Origin")
    dest_label = "POD" if mode == "Sea" else ("AOD" if mode == "Air" else "Destination")
    origin = st.text_input(origin_label, value="Dubai")
    destination = st.text_input(dest_label, value="")
with c4:
    quote_date = st.date_input("Quote Date", value=date.today())
    validity = st.text_input("Rate Validity", value="15 Days")

if mode == "Sea":
    st.subheader("2. Sea Cargo Details")
    if st.button("+ Add cargo detail"):
        st.session_state.cargo_lines.append({"Equipment": "20DV", "Qty": 1, "Gross Weight KG": 0.0, "Cargo Details": ""})
    equipment_options = ["20DV", "40STD", "40HC", "40RF", "40 FR"]
    for i, cargo in enumerate(st.session_state.cargo_lines):
        cc1, cc2, cc3, cc4 = st.columns([1.1, .7, 1, 2.2])
        with cc1:
            cargo["Equipment"] = st.selectbox("Equipment", equipment_options, index=equipment_options.index(cargo.get("Equipment", "20DV")) if cargo.get("Equipment") in equipment_options else 0, key=f"eq_{i}")
        with cc2:
            cargo["Qty"] = st.number_input("Qty", min_value=1, value=int(cargo.get("Qty", 1)), step=1, key=f"qty_{i}")
        with cc3:
            cargo["Gross Weight KG"] = st.number_input("Gross Weight KG", min_value=0.0, value=float(cargo.get("Gross Weight KG", 0.0)), step=100.0, key=f"gw_{i}")
        with cc4:
            cargo["Cargo Details"] = st.text_input("Cargo Details", value=cargo.get("Cargo Details", ""), key=f"cd_{i}")
else:
    st.subheader("2. Cargo Details")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        pieces = st.number_input("Pieces", min_value=0, value=1, step=1)
    with c2:
        gross_weight = st.number_input("Gross Weight KG", min_value=0.0, value=0.0, step=1.0)
    with c3:
        cbm = st.number_input("CBM", min_value=0.0, value=0.0, step=0.01)
    with c4:
        chargeable = max(gross_weight, cbm * 167 if mode == "Air" else cbm * 200)
        st.metric("Chargeable Weight", f"{chargeable:,.2f} KG")

st.subheader("3. Manual Quote Lines")
st.caption("Use Tab to move field-by-field: Description → Carrier → Unit → Unit Price → VAT/Tax → Currency → next row. No Enter button required.")

b1, b2, b3 = st.columns([1,1,5])
with b1:
    if st.button("+ Add line"):
        st.session_state.quote_lines.append({"Description": "", "Carrier": "", "Unit": 1.0, "Unit Price": 0.0, "VAT/Tax %": 0.0, "Currency": "AED"})
        st.rerun()
with b2:
    if st.button("Clear lines"):
        st.session_state.quote_lines = [{"Description": "", "Carrier": "", "Unit": 1.0, "Unit Price": 0.0, "VAT/Tax %": 0.0, "Currency": "AED"}]
        st.rerun()

st.markdown("**Description &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Carrier &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Unit &nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Unit Price &nbsp;&nbsp;&nbsp;&nbsp; VAT/Tax % &nbsp;&nbsp; Currency &nbsp;&nbsp;&nbsp; Total**")

currency_options = ["AED", "USD", "EUR", "SAR", "INR", "GBP", "CNY"]
for i, line in enumerate(st.session_state.quote_lines):
    cols = st.columns([2.6, 1.5, .75, 1.1, .85, .9, 1.05])
    with cols[0]:
        line["Description"] = st.text_input("Description", value=line.get("Description", ""), key=f"desc_{i}", label_visibility="collapsed", placeholder="Description")
    with cols[1]:
        line["Carrier"] = st.text_input("Carrier", value=line.get("Carrier", ""), key=f"carrier_{i}", label_visibility="collapsed", placeholder="Carrier")
    with cols[2]:
        line["Unit"] = st.number_input("Unit", min_value=0.0, value=float(line.get("Unit", 1.0)), step=1.0, key=f"unit_{i}", label_visibility="collapsed")
    with cols[3]:
        line["Unit Price"] = st.number_input("Unit Price", min_value=0.0, value=float(line.get("Unit Price", 0.0)), step=10.0, key=f"price_{i}", label_visibility="collapsed")
    with cols[4]:
        line["VAT/Tax %"] = st.number_input("VAT/Tax %", min_value=0.0, value=float(line.get("VAT/Tax %", 0.0)), step=1.0, key=f"vat_{i}", label_visibility="collapsed")
    with cols[5]:
        current_currency = line.get("Currency", "AED")
        idx = currency_options.index(current_currency) if current_currency in currency_options else 0
        line["Currency"] = st.selectbox("Currency", currency_options, index=idx, key=f"cur_{i}", label_visibility="collapsed")
    with cols[6]:
        st.text_input("Total", value=f"{line.get('Currency','AED')} {fmt_money(line_total(line))}", key=f"total_{i}", disabled=True, label_visibility="collapsed")

st.subheader("4. Selling Totals")
rates = {"AED": 1.0, "USD": 3.6725, "EUR": 4.0, "SAR": 0.98, "INR": 0.044, "GBP": 4.7, "CNY": 0.51}
with st.expander("Currency conversion to AED", expanded=False):
    rc = st.columns(6)
    for idx, cur in enumerate(["USD", "EUR", "SAR", "INR", "GBP", "CNY"]):
        with rc[idx % 6]:
            rates[cur] = st.number_input(f"1 {cur} = AED", value=float(rates[cur]), step=0.01, key=f"rate_{cur}")

totals_by_currency = {}
for l in st.session_state.quote_lines:
    if str(l.get("Description", "")).strip() or float(l.get("Unit Price", 0) or 0) > 0:
        cur = l.get("Currency", "AED")
        totals_by_currency[cur] = totals_by_currency.get(cur, 0.0) + line_total(l)

total_aed = sum(v * rates.get(c, 1.0) for c, v in totals_by_currency.items())
mc1, mc2, mc3 = st.columns(3)
with mc1:
    st.markdown("<div class='mv-total'>", unsafe_allow_html=True)
    st.metric("Total Selling Quote - AED Equivalent", f"AED {total_aed:,.2f}")
    st.markdown("</div>", unsafe_allow_html=True)
with mc2:
    st.metric("Quote Lines", sum(1 for l in st.session_state.quote_lines if str(l.get("Description", "")).strip() or float(l.get("Unit Price", 0) or 0) > 0))
with mc3:
    st.metric("Mode", mode)

if totals_by_currency:
    st.write("Currency totals:")
    st.dataframe(pd.DataFrame([{"Currency": k, "Total": round(v, 2), "AED Equivalent": round(v * rates.get(k, 1.0), 2)} for k, v in totals_by_currency.items()]), hide_index=True, use_container_width=True)

st.subheader("5. Prepared Quote Text")
terms = st.text_area("Terms & Conditions", value="Rates are subject to space/equipment availability and final carrier confirmation.\nDuties/taxes, inspections, demurrage/detention, storage, and destination charges are excluded unless specifically mentioned.", height=90)
quote_lines_text = "\n".join([f"- {l.get('Description','')}: {l.get('Currency','AED')} {fmt_money(line_total(l))}" for l in st.session_state.quote_lines if str(l.get("Description", "")).strip() or float(l.get("Unit Price", 0) or 0) > 0])
quote_text = f"""Dear Customer,

Thank you for your enquiry.

Please find our quotation below:

Quote No: {quote_no}
Customer: {customer}
Mode: {mode}
Service Term: {service}
Origin: {origin}
Destination: {destination}
Validity: {validity}

Charges:
{quote_lines_text}

Total AED Equivalent: AED {total_aed:,.2f}

Terms:
{terms}

Regards,
Marvento Shipping LLC
{MARVENTO['phone']} | {MARVENTO['email']}
"""
st.text_area("Copy Quote Text", value=quote_text, height=320)

enq = {"quote_no": quote_no, "quote_date": str(quote_date), "customer": customer, "validity": validity, "mode": mode, "service": service, "origin": origin, "destination": destination, "terms": terms}
pdf_bytes = make_pdf(enq, st.session_state.quote_lines, totals_by_currency, total_aed)
st.download_button("Download PDF Quotation", data=pdf_bytes, file_name=f"{quote_no}_Marvento_Quotation.pdf", mime="application/pdf")
