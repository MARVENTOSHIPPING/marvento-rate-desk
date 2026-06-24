import datetime as dt
import io
import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

APP_TITLE = "Marvento Rate Desk Pro"
DB_PATH = Path("marvento_pro.db")
LOGO_PATH = Path("marvento_logo.png")

NAVY = "#0B3A82"
PINK = "#E91E8F"

COMPANY = {
    "name": "MARVENTO SHIPPING LLC",
    "address": "Office 210, Al Nakheel Building, Karama",
    "phone": "+97143535822",
    "email": "hello@marventoshipping.com",
    "website": "www.marventoshipping.com",
    "trn": "104851107300003",
}

USERS = {
    "kiran.dxb@marventoshipping.com": {"password": "ChangeMe123", "role": "Admin", "name": "Kiran"},
    "sales1@marventoshipping.com": {"password": "ChangeMe123", "role": "Sales", "name": "Sales 1"},
    "sales2@marventoshipping.com": {"password": "ChangeMe123", "role": "Sales", "name": "Sales 2"},
    "ops@marventoshipping.com": {"password": "ChangeMe123", "role": "Operations", "name": "Operations"},
    "management@marventoshipping.com": {"password": "ChangeMe123", "role": "Management", "name": "Management"},
}

st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown(
    f"""
<style>
.block-container {{padding-top: 1.2rem; max-width: 1400px;}}
.stButton>button {{background-color:{NAVY}; color:white; border-radius:8px;}}
.stDownloadButton>button {{background-color:{PINK}; color:white; border-radius:8px;}}
div[data-testid="stMetricValue"] {{color:{NAVY};}}
.small-note {{color:#666; font-size:13px;}}
</style>
""",
    unsafe_allow_html=True,
)


def conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def ensure_column(cur, table, column, definition):
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    c = conn()
    cur = c.cursor()

    cur.execute(
        """CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        contact_person TEXT,
        email TEXT,
        phone TEXT,
        address TEXT,
        credit_terms TEXT,
        salesperson TEXT,
        created_at TEXT
    )"""
    )

    cur.execute(
        """CREATE TABLE IF NOT EXISTS enquiries(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enquiry_no TEXT UNIQUE,
        customer_id INTEGER,
        customer_name TEXT,
        mode TEXT,
        service TEXT,
        origin TEXT,
        destination TEXT,
        cargo_summary TEXT,
        status TEXT,
        salesperson TEXT,
        created_at TEXT
    )"""
    )

    cur.execute(
        """CREATE TABLE IF NOT EXISTS quotes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_no TEXT UNIQUE,
        enquiry_no TEXT,
        customer_name TEXT,
        mode TEXT,
        origin TEXT,
        destination TEXT,
        service TEXT,
        validity TEXT,
        currency TEXT,
        total REAL,
        status TEXT,
        salesperson TEXT,
        quote_json TEXT,
        pdf BLOB,
        created_at TEXT
    )"""
    )

    ensure_column(cur, "customers", "country", "TEXT")
    ensure_column(cur, "customers", "industry", "TEXT")
    ensure_column(cur, "customers", "trn", "TEXT")

    ensure_column(cur, "enquiries", "source", "TEXT")
    ensure_column(cur, "enquiries", "cargo_ready_date", "TEXT")
    ensure_column(cur, "enquiries", "follow_up_date", "TEXT")
    ensure_column(cur, "enquiries", "win_probability", "REAL")

    c.commit()
    c.close()


def qdf(query, params=()):
    c = conn()
    try:
        return pd.read_sql_query(query, c, params=params)
    finally:
        c.close()


def next_no(prefix, table, col):
    year = dt.datetime.now().year
    c = conn()
    cur = c.cursor()
    cur.execute(
        f"SELECT {col} FROM {table} WHERE {col} LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{prefix}-{year}-%",),
    )
    row = cur.fetchone()
    c.close()
    n = 1 if not row else int(row[0].split("-")[-1]) + 1
    return f"{prefix}-{year}-{n:04d}"


def add_logo(width=240):
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=width)
    else:
        st.markdown(f"### {COMPANY['name']}")


def login():
    if st.session_state.get("logged_in"):
        return True

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        add_logo(260)
        st.subheader("Rate Desk Pro Login")
        u = st.text_input("Username", key="login_username")
        p = st.text_input("Password", type="password", key="login_password")

        if st.button("Login", use_container_width=True, key="login_button"):
            if u in USERS and USERS[u]["password"] == p:
                st.session_state.logged_in = True
                st.session_state.user = u
                st.session_state.role = USERS[u]["role"]
                st.session_state.name = USERS[u]["name"]
                st.rerun()
            else:
                st.error("Invalid username or password")
    return False


def customer_options():
    df = qdf("SELECT name FROM customers ORDER BY name")
    return df["name"].tolist() if not df.empty else []


def get_customer(name):
    if not name:
        return {}
    df = qdf("SELECT * FROM customers WHERE name=?", (name,))
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


def save_customer(name, contact, email, phone, address, credit_terms, salesperson, country, industry, trn):
    c = conn()
    cur = c.cursor()
    cur.execute(
        """INSERT INTO customers(
            name, contact_person, email, phone, address, credit_terms,
            salesperson, country, industry, trn, created_at
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(name) DO UPDATE SET
            contact_person=excluded.contact_person,
            email=excluded.email,
            phone=excluded.phone,
            address=excluded.address,
            credit_terms=excluded.credit_terms,
            salesperson=excluded.salesperson,
            country=excluded.country,
            industry=excluded.industry,
            trn=excluded.trn
        """,
        (
            name,
            contact,
            email,
            phone,
            address,
            credit_terms,
            salesperson,
            country,
            industry,
            trn,
            dt.datetime.now().isoformat(timespec="seconds"),
        ),
    )
    c.commit()
    c.close()


def ai_cargo_upload_section():
    st.markdown("#### AI Cargo Extraction from Document")
    st.caption("Phase 2 preparation: upload PDF/image now. AI reading engine can be connected later.")

    cargo_file = st.file_uploader(
        "Upload packing list / customer PDF / screenshot",
        type=["pdf", "png", "jpg", "jpeg"],
        key="ai_cargo_file_uploader",
    )

    if cargo_file:
        st.success(f"Uploaded: {cargo_file.name}")
        st.info(
            "Next Phase 2 engine will extract pieces, dimensions, gross weight, CBM and chargeable weight automatically."
        )

        with st.expander("Example output expected from uploaded packing list"):
            st.write(
                {
                    "Packages": "1",
                    "Pieces": "60",
                    "Dimensions CM": "121 x 101 x 78",
                    "Gross Weight KG": "74.8",
                    "CBM": "1.00",
                    "Air Chargeable KG": "159",
                }
            )


def cargo_section(mode):
    st.markdown("#### Cargo Details")

    if "cargo_rows" not in st.session_state:
        st.session_state.cargo_rows = 1

    if st.button("+ Add Cargo Row", key="add_cargo_row_button"):
        st.session_state.cargo_rows += 1
        st.rerun()

    rows = []

    if mode == "Sea":
        total_cbm = 0.0
        total_gw = 0.0
        total_containers = 0

        for i in range(st.session_state.cargo_rows):
            st.markdown(f"Cargo Row {i + 1}")
            a, b, c, d, e = st.columns([1.2, 1.1, 1.2, 1.2, 2.5])

            eq = a.selectbox(
                "Equipment",
                ["LCL", "20DV", "40STD", "40HC", "40RF", "40FR", "45HC"],
                key=f"sea_equipment_{i}",
            )

            if eq == "LCL":
                cbm = b.number_input("CBM", min_value=0.0, value=0.0, key=f"sea_cbm_{i}")
                gw = c.number_input("Gross Weight KG", min_value=0.0, value=0.0, key=f"sea_gw_{i}")
                packages = d.number_input("Packages", min_value=1, value=1, key=f"sea_pkg_{i}")
                desc = e.text_input("Cargo Description", key=f"sea_desc_{i}")

                total_cbm += cbm
                total_gw += gw

                rows.append(
                    {
                        "equipment": "LCL",
                        "cbm": cbm,
                        "packages": packages,
                        "gross_weight": gw,
                        "description": desc,
                    }
                )

            else:
                qty = b.number_input("Container Qty", min_value=1, value=1, key=f"sea_container_qty_{i}")
                gw = c.number_input("Gross Weight KG", min_value=0.0, value=0.0, key=f"sea_fcl_gw_{i}")
                desc = e.text_input("Cargo Description", key=f"sea_fcl_desc_{i}")

                total_containers += qty
                total_gw += gw

                rows.append(
                    {
                        "equipment": eq,
                        "qty": qty,
                        "gross_weight": gw,
                        "description": desc,
                    }
                )

        st.info(
            f"Sea Summary: Total CBM {total_cbm:.3f} | Total Gross Weight {total_gw:.2f} KG | Total Containers {total_containers}"
        )

    else:
        total_cbm = 0.0
        total_gw = 0.0
        total_chw = 0.0

        for i in range(st.session_state.cargo_rows):
            st.markdown(f"Cargo Row {i + 1}")
            a, b, c, d, e, f, g = st.columns([0.8, 1, 1, 1, 1, 1, 1])

            pcs = a.number_input("Pcs", min_value=1, value=1, key=f"air_pcs_{i}")
            l = b.number_input("L cm", min_value=0.0, value=0.0, key=f"air_l_{i}")
            w = c.number_input("W cm", min_value=0.0, value=0.0, key=f"air_w_{i}")
            h = d.number_input("H cm", min_value=0.0, value=0.0, key=f"air_h_{i}")
            gw = e.number_input("Gross KG", min_value=0.0, value=0.0, key=f"air_gw_{i}")

            cbm = (l * w * h * pcs) / 1_000_000 if l and w and h else 0.0
            divisor = 6000
            vol = (l * w * h * pcs) / divisor if l and w and h else 0.0
            chw = max(gw, vol)

            f.metric("CBM", f"{cbm:.3f}")
            g.metric("Chg KG", f"{chw:.2f}")

            total_cbm += cbm
            total_gw += gw
            total_chw += chw

            rows.append(
                {
                    "pcs": pcs,
                    "l": l,
                    "w": w,
                    "h": h,
                    "gross_weight": gw,
                    "cbm": cbm,
                    "chargeable_weight": chw,
                }
            )

        st.info(
            f"Total Gross Weight: {total_gw:.2f} KG | Total CBM: {total_cbm:.3f} | Total Chargeable Weight: {total_chw:.2f} KG"
        )

    return rows


def quote_lines_section(usd_to_aed=3.675):
    st.markdown("#### Manual Quote Lines")

    if "line_rows" not in st.session_state:
        st.session_state.line_rows = 4

    lines = []
    totals_by_currency = {}
    total_aed_equivalent = 0.0

    # Header only once
    h1, h2, h3, h4, h5, h6, h7, h8 = st.columns(
        [2.0, 1.3, 0.8, 1.0, 0.8, 0.8, 1.0, 1.8]
    )

    h1.markdown("**Description**")
    h2.markdown("**Carrier**")
    h3.markdown("**Unit**")
    h4.markdown("**Unit Price**")
    h5.markdown("**VAT %**")
    h6.markdown("**Currency**")
    h7.markdown("**Total**")
    h8.markdown("**Remarks**")

    for i in range(st.session_state.line_rows):

        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(
            [2.0, 1.3, 0.8, 1.0, 0.8, 0.8, 1.0, 1.8]
        )

        desc = c1.text_input(
            "Description",
            key=f"quote_desc_{i}",
            label_visibility="collapsed"
        )

        carrier = c2.text_input(
            "Carrier",
            key=f"quote_carrier_{i}",
            label_visibility="collapsed"
        )

        unit = c3.number_input(
            "Unit",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key=f"quote_unit_{i}",
            label_visibility="collapsed"
        )

        price = c4.number_input(
            "Unit Price",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key=f"quote_price_{i}",
            label_visibility="collapsed"
        )

        vat = c5.number_input(
            "VAT %",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key=f"quote_vat_{i}",
            label_visibility="collapsed"
        )

        curr = c6.selectbox(
            "Currency",
            ["AED", "USD", "EUR", "SAR", "INR", "GBP", "CNY"],
            key=f"quote_curr_{i}",
            label_visibility="collapsed"
        )

        total = unit * price
        total = total + (total * vat / 100)

        if curr == "AED":
            aed_value = total
        else:
            aed_value = total * exchange_rate

        c7.text_input(
            "Total",
            value=f"{total:,.2f}",
            key=f"quote_total_display_{i}",
            disabled=True,
            label_visibility="collapsed"
        )

        remarks = c8.text_input(
            "Remarks",
            key=f"quote_remarks_{i}",
            label_visibility="collapsed"
        )

        if desc or carrier or unit > 0 or price > 0 or remarks:
            lines.append(
                {
                    "description": desc,
                    "carrier": carrier,
                    "unit": unit,
                    "unit_price": price,
                    "vat": vat,
                    "currency": curr,
                    "total": total,
                    "aed_value": aed_value,
                    "remarks": remarks,
                }
            )

            totals_by_currency[curr] = totals_by_currency.get(curr, 0) + total
            total_aed_equivalent += aed_value

    if st.button("+ Add Quote Line", key="add_quote_line_button"):
        st.session_state.line_rows += 1
        st.rerun()

    if totals_by_currency:
        summary = []
        for curr, value in totals_by_currency.items():
            summary.append(f"{curr} {value:,.2f}")

        st.success(
            "Total Selling Quote : "
            + " | ".join(summary)
            + f" | AED Equivalent: AED {total_aed_equivalent:,.2f}"
        )

    return lines, totals_by_currency
def make_pdf(data):
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    if LOGO_PATH.exists():
        story.append(Image(str(LOGO_PATH), width=55 * mm, height=22 * mm, hAlign="LEFT"))

    story.append(Paragraph(f"<font color='{NAVY}' size='16'><b>QUOTATION</b></font>", styles["Title"]))

    story.append(
        Paragraph(
            f"<b>{COMPANY['name']}</b><br/>"
            f"{COMPANY['address']}<br/>"
            f"Tel: {COMPANY['phone']} | Email: {COMPANY['email']} | Web: {COMPANY['website']}<br/>"
            f"TRN: {COMPANY['trn']}",
            styles["Normal"],
        )
    )

    story.append(Spacer(1, 6 * mm))

    info = [
        ["Quote No", data["quote_no"], "Date", dt.date.today().strftime("%d-%b-%Y")],
        ["Customer", data["customer_name"], "Validity", data.get("validity", "")],
        ["Attention", data.get("attention_to", ""), "Email", data.get("customer_email", "")],
        ["Mode", data["mode"], "Service", data["service"]],
        ["Origin", data["origin"], "Destination", data["destination"]],
    ]

    t = Table(info, colWidths=[25 * mm, 65 * mm, 25 * mm, 65 * mm])
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(NAVY)),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor(NAVY)),
                ("TEXTCOLOR", (2, 0), (2, -1), colors.white),
            ]
        )
    )

    story.append(t)
    story.append(Spacer(1, 5 * mm))

    cargo_rows = data.get("cargo_rows", [])

    if cargo_rows:
        story.append(Paragraph("<b>Cargo Details</b>", styles["Heading3"]))

        if data["mode"] == "Sea":
            if any(r.get("equipment") == "LCL" for r in cargo_rows):
                cargo_table = [["Service", "CBM", "Packages", "Gross Weight KG", "Description"]]
                for r in cargo_rows:
                    if r.get("equipment") == "LCL":
                        cargo_table.append(
                            [
                                "LCL",
                                f"{r.get('cbm', 0):.3f}",
                                r.get("packages", ""),
                                f"{r.get('gross_weight', 0):,.2f}",
                                r.get("description", ""),
                            ]
                        )
                    else:
                        cargo_table.append(
                            [
                                r.get("equipment", ""),
                                "",
                                r.get("qty", ""),
                                f"{r.get('gross_weight', 0):,.2f}",
                                r.get("description", ""),
                            ]
                        )
            else:
                cargo_table = [["Equipment", "Qty", "Gross Weight KG", "Description"]]
                for r in cargo_rows:
                    cargo_table.append(
                        [
                            r.get("equipment", ""),
                            r.get("qty", ""),
                            f"{r.get('gross_weight', 0):,.2f}",
                            r.get("description", ""),
                        ]
                    )

        else:
            cargo_table = [["Pcs", "Dimensions CM", "Gross KG", "CBM", "Chargeable KG"]]
            for r in cargo_rows:
                cargo_table.append(
                    [
                        r.get("pcs", ""),
                        f"{r.get('l', 0)} x {r.get('w', 0)} x {r.get('h', 0)}",
                        f"{r.get('gross_weight', 0):,.2f}",
                        f"{r.get('cbm', 0):.3f}",
                        f"{r.get('chargeable_weight', 0):,.2f}",
                    ]
                )

        ct = Table(cargo_table, repeatRows=1)
        ct.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PINK)),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ]
            )
        )

        story.append(ct)
        story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("<b>Charges</b>", styles["Heading3"]))

    charges = [["Description", "Carrier", "Unit", "Unit Price", "VAT %", "Currency", "Total", "AED Value", "Remarks"]]

    for r in data.get("lines", []):
        charges.append(
    [
        r["description"],
        r["carrier"],
        r["unit"],
        f"{r['unit_price']:,.2f}",
        f"{r['vat']:,.2f}",
        r["currency"],
        f"{r['total']:,.2f}",
        f"{r.get('aed_value', 0):,.2f}",
        r.get("remarks", ""),
    ]
)

    tbl = Table(charges, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ]
        )
    )

    story.append(tbl)
    story.append(Spacer(1, 4 * mm))

    story.append(
        Paragraph(
            "<b>Total Selling Quote:</b> "
            + " | ".join([f"{k} {v:,.2f}" for k, v in data.get("totals_by_currency", {}).items()]),
            styles["Heading3"],
        )
    )

    story.append(Spacer(1, 6 * mm))

    story.append(
        Paragraph(
            "<b>Terms:</b> Subject to space, equipment availability, carrier acceptance and final cargo details. "
            "Duties, taxes, demurrage, detention, storage and inspections are excluded unless specifically mentioned.",
            styles["Normal"],
        )
    )

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Regards,<br/><b>Marvento Shipping LLC</b>", styles["Normal"]))

    doc.build(story)
    return buf.getvalue()


def dashboard():
    st.subheader("Dashboard")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers", len(qdf("SELECT id FROM customers")))
    c2.metric("Enquiries", len(qdf("SELECT id FROM enquiries")))
    c3.metric("Quotes", len(qdf("SELECT id FROM quotes")))
    c4.metric("Won Quotes", len(qdf("SELECT id FROM quotes WHERE status='Won'")))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Open Enquiries", len(qdf("SELECT id FROM enquiries WHERE status='Open'")))
    d2.metric("Quoted Enquiries", len(qdf("SELECT id FROM enquiries WHERE status='Quoted'")))
    d3.metric("Lost Enquiries", len(qdf("SELECT id FROM enquiries WHERE status='Lost'")))
    d4.metric("Draft Quotes", len(qdf("SELECT id FROM quotes WHERE status='Draft'")))

    st.dataframe(
        qdf(
            "SELECT quote_no, customer_name, mode, origin, destination, total, currency, status, created_at "
            "FROM quotes ORDER BY id DESC LIMIT 20"
        ),
        use_container_width=True,
    )


def customers_page():
    st.subheader("Customer Database")

    with st.expander("Add / Update Customer", expanded=True):
        a, b = st.columns(2)
        name = a.text_input("Customer Name", key="customer_name_input")
        contact = b.text_input("Contact Person", key="customer_contact_input")
        email = a.text_input("Email", key="customer_email_input")
        phone = b.text_input("Phone", key="customer_phone_input")

        c1, c2, c3 = st.columns(3)
        country = c1.text_input("Country", key="customer_country_input")
        industry = c2.text_input("Industry", key="customer_industry_input")
        trn = c3.text_input("Customer TRN", key="customer_trn_input")

        address = st.text_area("Address", key="customer_address_input")

        c, d = st.columns(2)
        credit = c.text_input("Credit Terms", key="customer_credit_input")
        sales = d.text_input("Salesperson", value=st.session_state.get("name", ""), key="customer_salesperson_input")

        if st.button("Save Customer", key="save_customer_button") and name:
            save_customer(name, contact, email, phone, address, credit, sales, country, industry, trn)
            st.success("Customer saved")

    st.dataframe(
        qdf(
            "SELECT name, contact_person, email, phone, country, industry, credit_terms, salesperson, created_at "
            "FROM customers ORDER BY name"
        ),
        use_container_width=True,
    )


def enquiry_page():
    st.subheader("Enquiry Database")

    customers = customer_options()

    df_existing = qdf(
        "SELECT * FROM enquiries ORDER BY id DESC"
    )

    edit_existing = False
    selected_enquiry = None

    if not df_existing.empty:
        edit_existing = st.checkbox(
            "Edit existing enquiry",
            key="edit_existing_enquiry_checkbox"
        )

        if edit_existing:
            selected_enquiry_no = st.selectbox(
                "Select enquiry to edit",
                df_existing["enquiry_no"].tolist(),
                key="edit_enquiry_select"
            )

            selected_enquiry = df_existing[
                df_existing["enquiry_no"] == selected_enquiry_no
            ].iloc[0].to_dict()

    with st.expander("Create / Edit Enquiry", expanded=True):

        if customers:
            default_customer_index = 0

            if selected_enquiry and selected_enquiry.get("customer_name") in customers:
                default_customer_index = customers.index(
                    selected_enquiry.get("customer_name")
                )

            customer = st.selectbox(
                "Customer",
                customers,
                index=default_customer_index,
                key="enquiry_customer_select"
            )
        else:
            customer = st.text_input(
                "Customer",
                value=selected_enquiry.get("customer_name", "") if selected_enquiry else "",
                key="enquiry_customer_text"
            )

        mode_options = ["Air", "Sea", "Courier", "Land"]
        service_options = ["EXW", "FCA", "FOB", "CIF", "CPT", "DAP", "DDU", "DDP"]
        source_options = ["Customer", "Agent", "Website", "WhatsApp", "Email", "Phone", "Referral"]
        status_options = ["Open", "Quoted", "Won", "Lost", "Cancelled"]

        mode_default = (
            mode_options.index(selected_enquiry.get("mode"))
            if selected_enquiry and selected_enquiry.get("mode") in mode_options
            else 0
        )

        service_default = (
            service_options.index(selected_enquiry.get("service"))
            if selected_enquiry and selected_enquiry.get("service") in service_options
            else 0
        )

        source_default = (
            source_options.index(selected_enquiry.get("source"))
            if selected_enquiry and selected_enquiry.get("source") in source_options
            else 0
        )

        status_default = (
            status_options.index(selected_enquiry.get("status"))
            if selected_enquiry and selected_enquiry.get("status") in status_options
            else 0
        )

        a, b, c = st.columns(3)

        mode = a.selectbox(
            "Mode",
            mode_options,
            index=mode_default,
            key="enquiry_mode_select"
        )

        service = b.selectbox(
            "Service Required",
            service_options,
            index=service_default,
            key="enquiry_service_select"
        )

        source = c.selectbox(
            "Enquiry Source",
            source_options,
            index=source_default,
            key="enquiry_source_select"
        )

        d, e = st.columns(2)

        origin = d.text_input(
            "AOL / POL / Origin",
            value=selected_enquiry.get("origin", "") if selected_enquiry else "",
            key="enquiry_origin_input"
        )

        dest = e.text_input(
            "AOD / POD / Destination",
            value=selected_enquiry.get("destination", "") if selected_enquiry else "",
            key="enquiry_destination_input"
        )

        def safe_date(value):
            try:
                if value:
                    return dt.datetime.strptime(str(value), "%Y-%m-%d").date()
            except Exception:
                pass
            return dt.date.today()

        f, g, h = st.columns(3)

        cargo_ready = f.date_input(
            "Cargo Ready Date",
            value=safe_date(selected_enquiry.get("cargo_ready_date") if selected_enquiry else None),
            key="enquiry_cargo_ready_date"
        )

        follow_up = g.date_input(
            "Follow Up Date",
            value=safe_date(selected_enquiry.get("follow_up_date") if selected_enquiry else None),
            key="enquiry_follow_up_date"
        )

        win_probability = h.slider(
            "Win Probability %",
            0,
            100,
            int(selected_enquiry.get("win_probability", 50)) if selected_enquiry and selected_enquiry.get("win_probability") is not None else 50,
            key="enquiry_win_probability"
        )

        salesperson = st.text_input(
            "Salesperson",
            value=selected_enquiry.get("salesperson", st.session_state.get("name", "")) if selected_enquiry else st.session_state.get("name", ""),
            key="enquiry_salesperson_input"
        )

        cargo = st.text_area(
            "Cargo Summary",
            value=selected_enquiry.get("cargo_summary", "") if selected_enquiry else "",
            key="enquiry_cargo_summary"
        )

        status = st.selectbox(
            "Status",
            status_options,
            index=status_default,
            key="enquiry_status_select"
        )

        button_label = "Update Enquiry" if selected_enquiry else "Save Enquiry"

        if st.button(button_label, key="save_or_update_enquiry_button") and customer:

            cdb = conn()
            cur = cdb.cursor()

            if selected_enquiry:
                cur.execute(
                    """UPDATE enquiries SET
                        customer_name=?,
                        mode=?,
                        service=?,
                        source=?,
                        origin=?,
                        destination=?,
                        cargo_summary=?,
                        status=?,
                        salesperson=?,
                        cargo_ready_date=?,
                        follow_up_date=?,
                        win_probability=?
                    WHERE enquiry_no=?""",
                    (
                        customer,
                        mode,
                        service,
                        source,
                        origin,
                        dest,
                        cargo,
                        status,
                        salesperson,
                        str(cargo_ready),
                        str(follow_up),
                        win_probability,
                        selected_enquiry["enquiry_no"],
                    ),
                )

                cdb.commit()
                cdb.close()

                st.success(f"Enquiry updated: {selected_enquiry['enquiry_no']}")

            else:
                enq = next_no("ENQ", "enquiries", "enquiry_no")

                cur.execute(
                    """INSERT INTO enquiries(
                        enquiry_no,
                        customer_name,
                        mode,
                        service,
                        source,
                        origin,
                        destination,
                        cargo_summary,
                        status,
                        salesperson,
                        cargo_ready_date,
                        follow_up_date,
                        win_probability,
                        created_at
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        enq,
                        customer,
                        mode,
                        service,
                        source,
                        origin,
                        dest,
                        cargo,
                        status,
                        salesperson,
                        str(cargo_ready),
                        str(follow_up),
                        win_probability,
                        dt.datetime.now().isoformat(timespec="seconds"),
                    ),
                )

                cdb.commit()
                cdb.close()

                st.success(f"Enquiry saved: {enq}")

    st.dataframe(
        qdf(
            "SELECT enquiry_no, customer_name, mode, service, source, origin, destination, status, "
            "salesperson, cargo_ready_date, follow_up_date, win_probability, created_at "
            "FROM enquiries ORDER BY id DESC"
        ),
        use_container_width=True,
    )

def quote_page():
    st.subheader("Quotation Generator")

    customers = customer_options()

    enqs = qdf(
        "SELECT enquiry_no, customer_name, mode, service, origin, destination, cargo_summary "
        "FROM enquiries ORDER BY id DESC"
    )

    use_enq = st.checkbox(
        "Create from existing enquiry",
        key="quote_use_existing_enquiry"
    )

    selected = None

    if use_enq and not enqs.empty:
        enq_no = st.selectbox(
            "Select Enquiry",
            enqs["enquiry_no"].tolist(),
            key="quote_enquiry_select"
        )

        selected = enqs[
            enqs["enquiry_no"] == enq_no
        ].iloc[0].to_dict()

        st.success(f"Loaded enquiry: {selected['enquiry_no']}")

    if selected:
        customer = selected.get("customer_name", "")
        walk_in = False
    else:
        walk_in = st.checkbox(
            "Walk-in Customer",
            key="quote_walk_in_customer"
        )

        if walk_in:
            customer = st.text_input(
                "Walk-in Customer Name",
                key="quote_walk_in_customer_name"
            )
        else:
            if customers:
                customer = st.selectbox(
                    "Customer",
                    customers,
                    key="quote_customer_select"
                )
            else:
                customer = st.text_input(
                    "Customer",
                    key="quote_customer_text"
                )

    cust = get_customer(customer) if not walk_in else {}

    if walk_in:
        w1, w2, w3 = st.columns(3)

        walk_in_contact = w1.text_input(
            "Contact Person",
            key="quote_walk_in_contact"
        )

        walk_in_email = w2.text_input(
            "Customer Email",
            key="quote_walk_in_email"
        )

        walk_in_phone = w3.text_input(
            "Customer Phone",
            key="quote_walk_in_phone"
        )
    else:
        walk_in_contact = ""
        walk_in_email = ""
        walk_in_phone = ""

    mode_options = ["Air", "Sea", "Courier", "Land"]
    service_options = ["EXW", "FCA", "FOB", "CIF", "CPT", "DAP", "DDU", "DDP"]

    mode_default = (
        mode_options.index(selected.get("mode"))
        if selected and selected.get("mode") in mode_options
        else 0
    )

    service_default = (
        service_options.index(selected.get("service"))
        if selected and selected.get("service") in service_options
        else 0
    )

    a, b, c, d = st.columns(4)

    mode = a.selectbox(
        "Mode",
        mode_options,
        index=mode_default,
        key="quote_mode_select"
    )

    service = b.selectbox(
        "Service",
        service_options,
        index=service_default,
        key="quote_service_select"
    )

    origin = c.text_input(
        "AOL/POL/Origin",
        value=selected.get("origin", "") if selected else "",
        key="quote_origin_input"
    )

    dest = d.text_input(
        "AOD/POD/Destination",
        value=selected.get("destination", "") if selected else "",
        key="quote_destination_input"
    )

    e, f, g = st.columns(3)

    attention_to = e.text_input(
        "Attention To",
        value=walk_in_contact if walk_in else (cust.get("contact_person", "") if cust else ""),
        key="quote_attention_input"
    )

    customer_email = f.text_input(
        "Customer Email",
        value=walk_in_email if walk_in else (cust.get("email", "") if cust else ""),
        key="quote_email_input"
    )

    customer_phone = g.text_input(
        "Customer Phone",
        value=walk_in_phone if walk_in else (cust.get("phone", "") if cust else ""),
        key="quote_phone_input"
    )

    validity = st.text_input(
        "Rate Validity",
        value="15 days",
        key="quote_validity_input"
    )

    if selected and selected.get("cargo_summary"):
        st.info(f"Cargo Summary from Enquiry: {selected.get('cargo_summary')}")

    ai_cargo_upload_section()

    cargo_rows = cargo_section(mode)

    exchange_rate = st.number_input(
    "AED Equivalent Exchange Rate",
    min_value=0.0,
    value=3.685,
    step=0.001,
    format="%.3f",    
    key="exchange_rate"
)

    lines, totals = quote_lines_section(exchange_rate)

    quote_no = next_no("MQ", "quotes", "quote_no")

    if lines:
        primary_currency = list(totals.keys())[0]
        primary_total = totals[primary_currency]
    else:
        primary_currency = "AED"
        primary_total = 0.0

    data = {
        "quote_no": quote_no,
        "enquiry_no": selected.get("enquiry_no", "") if selected else "",
        "customer_name": customer,
        "attention_to": attention_to,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "mode": mode,
        "service": service,
        "origin": origin,
        "destination": dest,
        "validity": validity,
        "cargo_rows": cargo_rows,
        "lines": lines,
        "totals_by_currency": totals,
    }

    pdf = make_pdf(data) if customer and lines else None

    col1, col2 = st.columns(2)

    with col1:
        if pdf:
            st.download_button(
                "Download PDF Quotation",
                data=pdf,
                file_name=f"{quote_no}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="download_pdf_quote_button",
            )

    with col2:
        if st.button(
            "Save Quote in Database",
            use_container_width=True,
            disabled=not bool(pdf),
            key="save_quote_button"
        ):
            cdb = conn()
            cur = cdb.cursor()

            cur.execute(
                """INSERT INTO quotes(
                    quote_no,
                    enquiry_no,
                    customer_name,
                    mode,
                    origin,
                    destination,
                    service,
                    validity,
                    currency,
                    total,
                    status,
                    salesperson,
                    quote_json,
                    pdf,
                    created_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    quote_no,
                    selected.get("enquiry_no", "") if selected else "",
                    customer,
                    mode,
                    origin,
                    dest,
                    service,
                    validity,
                    primary_currency,
                    primary_total,
                    "Draft",
                    st.session_state.get("name", ""),
                    json.dumps(data),
                    pdf,
                    dt.datetime.now().isoformat(timespec="seconds"),
                ),
            )

            cdb.commit()
            cdb.close()

            if selected:
                cdb = conn()
                cur = cdb.cursor()
                cur.execute(
                    "UPDATE enquiries SET status='Quoted' WHERE enquiry_no=?",
                    (selected.get("enquiry_no"),)
                )
                cdb.commit()
                cdb.close()

            st.success(f"Quote saved: {quote_no}")

def saved_quotes_page():
    st.subheader("Saved Quotations")

    search = st.text_input("Search customer / quote number", key="saved_quote_search")

    if search:
        df = qdf(
            "SELECT id, quote_no, customer_name, mode, origin, destination, total, currency, status, created_at "
            "FROM quotes WHERE quote_no LIKE ? OR customer_name LIKE ? ORDER BY id DESC",
            (f"%{search}%", f"%{search}%"),
        )
    else:
        df = qdf(
            "SELECT id, quote_no, customer_name, mode, origin, destination, total, currency, status, created_at "
            "FROM quotes ORDER BY id DESC"
        )

    st.dataframe(df.drop(columns=["id"]) if not df.empty else df, use_container_width=True)

    if not df.empty:
        qn = st.selectbox("Select quote to download", df["quote_no"].tolist(), key="saved_quote_select")
        row = df[df["quote_no"] == qn].iloc[0]

        cdb = conn()
        cur = cdb.cursor()
        cur.execute("SELECT pdf FROM quotes WHERE id=?", (int(row["id"]),))
        pdf = cur.fetchone()[0]
        cdb.close()

        st.download_button("Re-download Saved PDF", data=pdf, file_name=f"{qn}.pdf", mime="application/pdf", key="saved_quote_download_button")


def main():
    init_db()

    if not login():
        return

    col1, col2 = st.columns([5, 1])

    with col1:
        add_logo(220)
        st.caption(f"Logged in as {st.session_state.name} | Role: {st.session_state.role}")

    with col2:
        if st.button("Logout", key="logout_button"):
            st.session_state.clear()
            st.rerun()

    tabs = st.tabs(["Dashboard", "Customers", "Enquiries", "Create Quote", "Saved Quotes"])

    with tabs[0]:
        dashboard()

    with tabs[1]:
        customers_page()

    with tabs[2]:
        enquiry_page()

    with tabs[3]:
        quote_page()

    with tabs[4]:
        saved_quotes_page()


if __name__ == "__main__":
    main()
