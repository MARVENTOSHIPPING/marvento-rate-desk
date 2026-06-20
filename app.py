import io
from datetime import date

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

APP_USER = "kiran.dxb@marventoshipping.com"
APP_PASSWORD = "ChangeMe123"
BRAND_BLUE = colors.HexColor("#0B2E5F")
BRAND_GREEN = colors.HexColor("#0E8F6E")

st.set_page_config(page_title="Marvento Rate Desk", page_icon="🚢", layout="wide")

st.markdown(
    """
    <style>
    .main .block-container {padding-top: 1.2rem;}
    .marvento-header {border-left: 8px solid #0E8F6E; padding: 14px 18px; background:#f7fbff; border-radius:10px; margin-bottom:18px;}
    .marvento-title {font-size:30px; font-weight:800; color:#0B2E5F; margin:0;}
    .marvento-sub {font-size:14px; color:#355; margin-top:4px;}
    .metric-box {padding:14px; border-radius:10px; background:#f5f8fb; border:1px solid #e6eef5;}
    </style>
    """,
    unsafe_allow_html=True,
)


def login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if st.session_state.logged_in:
        return True
    st.markdown('<div class="marvento-header"><p class="marvento-title">MARVENTO SHIPPING</p><p class="marvento-sub">Rate Desk Login</p></div>', unsafe_allow_html=True)
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        if username.strip().lower() == APP_USER.lower() and password == APP_PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Incorrect username or password")
    return False


def money(x):
    try:
        return f"{float(x):,.2f}"
    except Exception:
        return "0.00"


def calc_total(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["Unit", "Unit Price", "VAT/Tax"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    out["Total"] = (out["Unit"] * out["Unit Price"]) + out["VAT/Tax"]
    return out


def make_quote_text(enq, quote_df, total):
    lines = []
    lines.append("Dear Customer,")
    lines.append("")
    lines.append("Thank you for your enquiry. Please find our quotation below:")
    lines.append("")
    lines.append(f"Quote Ref: {enq['quote_ref']}")
    lines.append(f"Customer: {enq['customer']}")
    lines.append(f"Service Required: {enq['service']}")
    lines.append(f"Mode: {enq['mode']}")
    if enq["mode"] == "Air":
        lines.append(f"AOL: {enq['origin']}")
        lines.append(f"AOD: {enq['destination']}")
        lines.append(f"Chargeable Weight: {money(enq['chargeable_weight'])} KG")
    elif enq["mode"] == "Sea":
        lines.append(f"POL: {enq['origin']}")
        lines.append(f"POD: {enq['destination']}")
        lines.append(f"Gross Weight: {money(enq['gross_weight'])} KG")
        lines.append(f"Equipment: {enq['equipment_summary']}")
    else:
        lines.append(f"Origin: {enq['origin']}")
        lines.append(f"Destination: {enq['destination']}")
        lines.append(f"Chargeable Weight: {money(enq['chargeable_weight'])} KG")
    lines.append(f"Rate Validity: {enq['validity']}")
    lines.append("")
    lines.append("Charges:")
    for _, r in quote_df.iterrows():
        desc = str(r.get("Description", "")).strip()
        if not desc:
            continue
        carrier = str(r.get("Carrier", "")).strip()
        cur = str(r.get("Currency", "AED")).strip() or "AED"
        lines.append(f"- {desc} | {carrier} | {money(r['Unit'])} x {money(r['Unit Price'])} + Tax {money(r['VAT/Tax'])} = {cur} {money(r['Total'])}")
    lines.append("")
    lines.append(f"Total Selling Quote: AED {money(total)}")
    lines.append("")
    lines.append("Subject to space, equipment availability, customs approval and standard Marvento Shipping terms.")
    lines.append("")
    lines.append("Regards,")
    lines.append("Marvento Shipping")
    return "\n".join(lines)


def create_pdf(enq, quote_df, total, quote_text):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="MarventoTitle", parent=styles["Title"], fontSize=20, textColor=BRAND_BLUE, alignment=0, spaceAfter=4))
    styles.add(ParagraphStyle(name="MarventoSub", parent=styles["Normal"], fontSize=9, textColor=BRAND_GREEN, alignment=0))
    story = []
    logo_table = Table([[Paragraph("<b>MARVENTO</b>", styles["MarventoTitle"]), Paragraph("QUOTATION", styles["Title"])]], colWidths=[95*mm, 65*mm])
    logo_table.setStyle(TableStyle([
        ("TEXTCOLOR", (0,0), (0,0), BRAND_BLUE),
        ("TEXTCOLOR", (1,0), (1,0), BRAND_BLUE),
        ("LINEBELOW", (0,0), (-1,-1), 1.5, BRAND_GREEN),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(logo_table)
    story.append(Paragraph("Shipping & Logistics", styles["MarventoSub"]))
    story.append(Spacer(1, 8*mm))

    info = [
        ["Quote Ref", enq['quote_ref'], "Date", str(enq['quote_date'])],
        ["Customer", enq['customer'], "Service", enq['service']],
        ["Mode", enq['mode'], "Validity", enq['validity']],
        ["Origin", enq['origin'], "Destination", enq['destination']],
    ]
    if enq["mode"] == "Sea":
        info.append(["Gross Weight", f"{money(enq['gross_weight'])} KG", "Equipment", enq['equipment_summary']])
    else:
        info.append(["Chargeable Weight", f"{money(enq['chargeable_weight'])} KG", "", ""])
    info_table = Table(info, colWidths=[32*mm, 54*mm, 32*mm, 54*mm])
    info_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EEF5FB")),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8.5),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 8*mm))

    rows = [["Description", "Carrier", "Unit", "Unit Price", "VAT/Tax", "Currency", "Total"]]
    for _, r in quote_df.iterrows():
        if str(r.get("Description", "")).strip():
            rows.append([str(r["Description"]), str(r["Carrier"]), money(r["Unit"]), money(r["Unit Price"]), money(r["VAT/Tax"]), str(r["Currency"]), money(r["Total"])])
    if len(rows) == 1:
        rows.append(["Manual freight charge", "", "1", money(total), "0.00", "AED", money(total)])
    charge_table = Table(rows, colWidths=[48*mm, 30*mm, 18*mm, 25*mm, 22*mm, 20*mm, 25*mm])
    charge_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), BRAND_BLUE),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("ALIGN", (2,1), (-1,-1), "RIGHT"),
    ]))
    story.append(charge_table)
    story.append(Spacer(1, 5*mm))
    total_table = Table([["Total Selling Quote", f"AED {money(total)}"]], colWidths=[125*mm, 50*mm])
    total_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#EAF7F2")),
        ("TEXTCOLOR", (0,0), (-1,-1), BRAND_BLUE),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.25, BRAND_GREEN),
        ("ALIGN", (1,0), (1,0), "RIGHT"),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("Terms", styles["Heading3"]))
    story.append(Paragraph("Subject to space, equipment availability, customs approval and standard Marvento Shipping terms.", styles["Normal"]))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


if not login():
    st.stop()

st.markdown('<div class="marvento-header"><p class="marvento-title">MARVENTO RATE DESK</p><p class="marvento-sub">Manual quotation system</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.success("Logged in")
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.rerun()
    st.info("Tariff and Auto Quote options are removed in this version. Manual quote only.")

st.subheader("1. Enquiry Details")
c1, c2, c3, c4 = st.columns(4)
with c1:
    quote_ref = st.text_input("Quote Ref", value=f"MQ-{date.today().strftime('%Y%m%d')}")
    customer = st.text_input("Customer Name")
with c2:
    mode = st.selectbox("Mode", ["Air", "Sea", "Courier", "Land"])
    service = st.selectbox("Service Required", ["EXW", "FCA", "FOB", "CIF", "CPT", "DAP", "DDU", "DDP"])
with c3:
    quote_date = st.date_input("Quote Date", value=date.today())
    validity = st.text_input("Rate Validity", value="7 days")
with c4:
    salesperson = st.text_input("Prepared By", value="Marvento Shipping")
    currency_default = st.selectbox("Default Currency", ["AED", "USD", "EUR", "GBP", "INR"], index=0)

st.subheader("2. Routing & Cargo")
if mode == "Air":
    label_o, label_d = "AOL", "AOD"
elif mode == "Sea":
    label_o, label_d = "POL", "POD"
else:
    label_o, label_d = "Origin", "Destination"

r1, r2 = st.columns(2)
with r1:
    origin = st.text_input(label_o)
with r2:
    destination = st.text_input(label_d)

chargeable_weight = 0.0
gross_weight = 0.0
equipment_summary = ""

if mode == "Sea":
    s1, s2 = st.columns([1, 2])
    with s1:
        gross_weight = st.number_input("Gross Weight KG", min_value=0.0, value=0.0, step=100.0)
    with s2:
        st.write("Equipment Details")
        if "equip_rows" not in st.session_state:
            st.session_state.equip_rows = pd.DataFrame({"Equipment": ["20DV"], "Qty": [1]})
        equip_df = st.data_editor(
            st.session_state.equip_rows,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Equipment": st.column_config.SelectboxColumn("Equipment", options=["20DV", "40STD", "40HC", "40RF", "40 FR"], required=True),
                "Qty": st.column_config.NumberColumn("Qty", min_value=0, step=1, required=True),
            },
            key="equipment_editor",
        )
        st.session_state.equip_rows = equip_df
        equipment_summary = ", ".join([f"{int(row.Qty)} x {row.Equipment}" for _, row in equip_df.fillna({"Qty":0, "Equipment":""}).iterrows() if int(row.Qty or 0) > 0 and row.Equipment])
else:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        pieces = st.number_input("Pieces", min_value=0, value=1, step=1)
    with c2:
        gross_weight = st.number_input("Gross Weight KG", min_value=0.0, value=0.0, step=1.0)
    with c3:
        cbm = st.number_input("CBM", min_value=0.0, value=0.0, step=0.01)
    with c4:
        manual_cw = st.number_input("Manual Chargeable KG", min_value=0.0, value=0.0, step=1.0)
    if mode == "Air":
        volume_weight = cbm * 167
    elif mode == "Courier":
        volume_weight = cbm * 200
    else:
        volume_weight = cbm * 333
    chargeable_weight = max(gross_weight, volume_weight, manual_cw)
    st.metric("Calculated Chargeable Weight", f"{money(chargeable_weight)} KG")

st.subheader("3. Manual Quote Lines")
st.caption("Use Tab inside this table to move across the row and continue into the next row. Use the blank row at the bottom to add more lines.")

if "quote_rows" not in st.session_state:
    st.session_state.quote_rows = pd.DataFrame([
        {"Description": "Freight Charges", "Carrier": "", "Unit": 1.0, "Unit Price": 0.0, "VAT/Tax": 0.0, "Currency": currency_default, "Total": 0.0},
        {"Description": "Documentation", "Carrier": "", "Unit": 1.0, "Unit Price": 0.0, "VAT/Tax": 0.0, "Currency": currency_default, "Total": 0.0},
    ])

edited_df = st.data_editor(
    st.session_state.quote_rows,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_order=["Description", "Carrier", "Unit", "Unit Price", "VAT/Tax", "Currency", "Total"],
    disabled=["Total"],
    column_config={
        "Description": st.column_config.TextColumn("Description", width="large"),
        "Carrier": st.column_config.TextColumn("Carrier", width="medium"),
        "Unit": st.column_config.NumberColumn("Unit", min_value=0.0, step=1.0, format="%.2f"),
        "Unit Price": st.column_config.NumberColumn("Unit Price", min_value=0.0, step=10.0, format="%.2f"),
        "VAT/Tax": st.column_config.NumberColumn("VAT/Tax", min_value=0.0, step=1.0, format="%.2f"),
        "Currency": st.column_config.SelectboxColumn("Currency", options=["AED", "USD", "EUR", "GBP", "INR"], required=True),
        "Total": st.column_config.NumberColumn("Total", format="%.2f"),
    },
    key="quote_editor",
)
quote_df = calc_total(edited_df)
st.session_state.quote_rows = quote_df

# display calculated table again for totals clarity
st.write("Calculated quote lines")
st.dataframe(quote_df, use_container_width=True, hide_index=True)

total_aed = float(quote_df.loc[quote_df["Currency"].fillna("AED").eq("AED"), "Total"].sum())
non_aed = quote_df.loc[~quote_df["Currency"].fillna("AED").eq("AED")]
if not non_aed.empty:
    st.warning("Total Selling Quote below includes AED lines only. Convert non-AED lines manually or enter them in AED for final AED total.")

a, b, c = st.columns(3)
with a:
    st.metric("Total Selling Quote", f"AED {money(total_aed)}")
with b:
    st.metric("Quote Lines", len(quote_df[quote_df["Description"].astype(str).str.strip() != ""]))
with c:
    st.metric("Mode", mode)

st.subheader("4. Prepared Quote Text")
enq = {
    "quote_ref": quote_ref,
    "quote_date": quote_date,
    "customer": customer,
    "mode": mode,
    "service": service,
    "origin": origin,
    "destination": destination,
    "validity": validity,
    "gross_weight": gross_weight,
    "chargeable_weight": chargeable_weight,
    "equipment_summary": equipment_summary,
}
quote_text = make_quote_text(enq, quote_df, total_aed)
st.text_area("Copy Quote Text", value=quote_text, height=320)

st.subheader("5. PDF Quote")
pdf_bytes = create_pdf(enq, quote_df, total_aed, quote_text)
st.download_button(
    "Download PDF Quote",
    data=pdf_bytes,
    file_name=f"{quote_ref or 'marvento_quote'}.pdf",
    mime="application/pdf",
    use_container_width=True,
)
