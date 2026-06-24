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
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):
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

    if st.button("+ Add Cargo Row"):
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
                key=f"eq_{i}",
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
                qty = b.number_input("Container Qty", min_value=1, value=1, key=f"eq_qty_{i}")
                gw = c.number_input("Gross Weight KG", min_value=0.0, value=0.0, key=f"sea_gw_{i}")
                desc = e.text_input("Cargo Description", key=f"sea_desc_{i}")

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

            pcs = a.number_input("Pcs", min_value=1, value=1, key=f"pcs_{i}")
            l = b.number_input("L cm", min_value=0.0, value=0.0, key=f"l_{i}")
            w = c.number_input("W cm", min_value=0.0, value=0.0, key=f"w_{i}")
            h = d.number_input("H cm", min_value=0.0, value=0.0, key=f"h_{i}")
            gw = e.number_input("Gross KG", min_value=0.0, value=0.0, key=f"gw_{i}")

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


def quote_lines_section():
    st.markdown("#### Manual Quote Lines")

    if "line_rows" not in st.session_state:
        st.session_state.line_rows = 4

    if st.button("+ Add Quote Line"):
        st.session_state.line_rows += 1
        st.rerun()

    lines = []
    totals_by_currency = {}

    for i in range(st.session_state.line_rows):
        st.markdown(f"Line {i + 1}")
        c1, c2, c3, c4, c5, c6, c7 = st.columns([2.2, 1.4, 0.8, 1.1, 0.8, 0.9, 1.2])

        desc = c1.text_input("Description", key=f"desc_{i}")
        carrier = c2.text_input("Carrier", key=f"carrier_{i}")
        unit = c3.number_input("Unit", min_value=0.0, value=0.0, key=f"unit_{i}")
        price = c4.number_input("Unit Price", min_value=0.0, value=0.0, key=f"price_{i}")
        vat = c5.number_input("VAT %", min_value=0.0, value=0.0, key=f"vat_{i}")
        curr = c6.selectbox("Currency", ["AED", "USD", "EUR", "SAR", "INR", "GBP", "CNY"], key=f"curr_{i}")

        total = unit * price * (1 + vat / 100)
        c7.metric("Total", f"{curr} {total:,.2f}")

        if desc or carrier or total > 0:
            lines.append(
                {
                    "description": desc,
                    "carrier": carrier,
                    "unit": unit,
                    "unit_price": price,
                    "vat": vat,
                    "currency": curr,
                    "total": total,
                }
            )
            totals_by_currency[curr] = totals_by_currency.get(curr, 0) + total

    if totals_by_currency:
        st.success(
            "Total Selling Quote: "
            + " | ".join([f"{k} {v:,.2f}" for k, v in totals_by_currency.items()])
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

    charges = [["Description", "Carrier", "Unit", "Unit Price", "VAT %", "Currency", "Total"]]

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

    customers_count = len(qdf("SELECT id FROM customers"))
    enquiries_count = len(qdf("SELECT id FROM enquiries"))
    quotes_count = len(qdf("SELECT id FROM quotes"))
    won_count = len(qdf("SELECT id FROM quotes WHERE status='Won'"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers", customers_count)
    c2.metric("Enquiries", enquiries_count)
    c3.metric("Quotes", quotes_count)
    c4.metric("Won Quotes", won_count)

    e_open = len(qdf("SELECT id FROM enquiries WHERE status='Open'"))
    e_quoted = len(qdf("SELECT id FROM enquiries WHERE status='Quoted'"))
    e_lost = len(qdf("SELECT id FROM enquiries WHERE status='Lost'"))
    q_draft = len(qdf("SELECT id FROM quotes WHERE status='Draft'"))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Open Enquiries", e_open)
    d2.metric("Quoted Enquiries", e_quoted)
    d3.metric("Lost Enquiries", e_lost)
    d4.metric("Draft Quotes", q_draft)

    qjson = qdf("SELECT quote_json FROM quotes WHERE quote_json IS NOT NULL")
    lcl_quotes = 0
    fcl_quotes = 0
    total_cbm = 0.0
    total_containers = 0

    for _, row in qjson.iterrows():
        try:
            data = json.loads(row["quote_json"])
            if data.get("mode") == "Sea":
                has_lcl = False
                has_fcl = False
                for cr in data.get("cargo_rows", []):
                    if cr.get("equipment") == "LCL":
                        has_lcl = True
                        total_cbm += float(cr.get("cbm", 0) or 0)
                    else:
                        has_fcl = True
                        total_containers += int(cr.get("qty", 0) or 0)
                if has_lcl:
                    lcl_quotes += 1
                if has_fcl:
                    fcl_quotes += 1
        except Exception:
            pass

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Sea LCL Quotes", lcl_quotes)
    s2.metric("Sea FCL Quotes", fcl_quotes)
    s3.metric("Total CBM Quoted", f"{total_cbm:.2f}")
    s4.metric("Total Containers Quoted", total_containers)

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
        name = a.text_input("Customer Name")
        contact = b.text_input("Contact Person")
        email = a.text_input("Email")
        phone = b.text_input("Phone")

        c1, c2, c3 = st.columns(3)
        country = c1.text_input("Country")
        industry = c2.text_input("Industry")
        trn = c3.text_input("Customer TRN")

        address = st.text_area("Address")

        c, d = st.columns(2)
        credit = c.text_input("Credit Terms")
        sales = d.text_input("Salesperson", value=st.session_state.get("name", ""))

        if st.button("Save Customer") and name:
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

    with st.expander("Create Enquiry", expanded=True):
        customer = st.selectbox("Customer", customers) if customers else st.text_input("Customer")

        a, b, c = st.columns(3)
        mode = a.selectbox("Mode", ["Air", "Sea", "Courier", "Land"])
        service = b.selectbox("Service Required", ["EXW", "FCA", "FOB", "CIF", "CPT", "DAP", "DDU", "DDP"])
        source = c.selectbox("Enquiry Source", ["Customer", "Agent", "Website", "WhatsApp", "Email", "Phone", "Referral"])

        d, e = st.columns(2)
        origin = d.text_input("AOL / POL / Origin")
        dest = e.text_input("AOD / POD / Destination")

        f, g, h = st.columns(3)
        cargo_ready = f.date_input("Cargo Ready Date", value=dt.date.today())
        follow_up = g.date_input("Follow Up Date", value=dt.date.today())
        win_probability = h.slider("Win Probability %", 0, 100, 50)

        salesperson = st.text_input("Salesperson", value=st.session_state.get("name", ""))

        cargo = st.text_area("Cargo Summary")
        status = st.selectbox("Status", ["Open", "Quoted", "Won", "Lost", "Cancelled"])

        if st.button("Save Enquiry") and customer:
            enq = next_no("ENQ", "enquiries", "enquiry_no")

            cdb = conn()
            cur = cdb.cursor()

            cur.execute(
                """INSERT INTO enquiries(
                    enquiry_no, customer_name, mode, service, source, origin, destination,
                    cargo_summary, status, salesperson, cargo_ready_date, follow_up_date,
                    win_probability, created_at
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
    enqs = qdf("SELECT enquiry_no, customer_name, mode, service, origin, destination FROM enquiries ORDER BY id DESC")

    use_enq = st.checkbox("Create from existing enquiry")
    selected = None

    if use_enq and not enqs.empty:
        enq_no = st.selectbox("Select Enquiry", enqs["enquiry_no"].tolist())
        selected = enqs[enqs["enquiry_no"] == enq_no].iloc[0].to_dict()

    customer = selected["customer_name"] if selected else (
        st.selectbox("Customer", customers) if customers else st.text_input("Customer")
    )

    cust = get_customer(customer)

    a, b, c, d = st.columns(4)

    mode = a.selectbox(
        "Mode",
        ["Air", "Sea", "Courier", "Land"],
        index=["Air", "Sea", "Courier", "Land"].index(selected["mode"]) if selected else 0,
    )

    service = b.selectbox(
        "Service",
        ["EXW", "FCA", "FOB", "CIF", "CPT", "DAP", "DDU", "DDP"],
        index=["EXW", "FCA", "FOB", "CIF", "CPT", "DAP", "DDU", "DDP"].index(selected["service"])
        if selected and selected["service"] in ["EXW", "FCA", "FOB", "CIF", "CPT", "DAP", "DDU", "DDP"]
        else 0,
    )

    origin = c.text_input("AOL/POL/Origin", value=selected["origin"] if selected else "")
    dest = d.text_input("AOD/POD/Destination", value=selected["destination"] if selected else "")

    e, f, g = st.columns(3)
    attention_to = e.text_input("Attention To", value=cust.get("contact_person", "") if cust else "")
    customer_email = f.text_input("Customer Email", value=cust.get("email", "") if cust else "")
    customer_phone = g.text_input("Customer Phone", value=cust.get("phone", "") if cust else "")

    validity = st.text_input("Rate Validity", value="15 days")

    ai_cargo_upload_section()

    cargo_rows = cargo_section(mode)

    lines, totals = quote_lines_section()

    quote_no = next_no("MQ", "quotes", "quote_no")

    if lines:
        primary_currency = list(totals.keys())[0]
        primary_total = totals[primary_currency]
    else:
        primary_currency = "AED"
        primary_total = 0.0

    data = {
        "quote_no": quote_no,
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
            )

    with col2:
        if st.button("Save Quote in Database", use_container_width=True, disabled=not bool(pdf)):
            cdb = conn()
            cur = cdb.cursor()

            cur.execute(
                """INSERT INTO quotes(
                    quote_no, enquiry_no, customer_name, mode, origin, destination,
                    service, validity, currency, total, status, salesperson,
                    quote_json, pdf, created_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    quote_no,
                    selected["enquiry_no"] if selected else "",
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

            st.success(f"Quote saved: {quote_no}")


def saved_quotes_page():
    st.subheader("Saved Quotations")

    search = st.text_input("Search customer / quote number")

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
        qn = st.selectbox("Select quote to download", df["quote_no"].tolist())
        row = df[df["quote_no"] == qn].iloc[0]

        cdb = conn()
        cur = cdb.cursor()
        cur.execute("SELECT pdf FROM quotes WHERE id=?", (int(row["id"]),))
        pdf = cur.fetchone()[0]
        cdb.close()

        st.download_button("Re-download Saved PDF", data=pdf, file_name=f"{qn}.pdf", mime="application/pdf")


def main():
    init_db()

    if not login():
        return

    col1, col2 = st.columns([5, 1])

    with col1:
        add_logo(220)
        st.caption(f"Logged in as {st.session_state.name} | Role: {st.session_state.role}")

    with col2:
        if st.button("Logout"):
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
