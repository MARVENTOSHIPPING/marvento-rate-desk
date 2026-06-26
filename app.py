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


APP_TITLE = "Marvento Rate Desk Pro v1.2"
DB_PATH = Path("marvento_pro.db")

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
    "kiran.dxb@marventoshipping.com": {
        "password": "ChangeMe123",
        "role": "Admin",
        "name": "Kiran",
    },
    "sales1@marventoshipping.com": {
        "password": "ChangeMe123",
        "role": "Sales",
        "name": "Sales 1",
    },
    "sales2@marventoshipping.com": {
        "password": "ChangeMe123",
        "role": "Sales",
        "name": "Sales 2",
    },
    "ops@marventoshipping.com": {
        "password": "ChangeMe123",
        "role": "Operations",
        "name": "Operations",
    },
    "management@marventoshipping.com": {
        "password": "ChangeMe123",
        "role": "Management",
        "name": "Management",
    },
}

CSP_OPTIONS = [
    "",
    "Monitha",
    "Nethmi",
    "Abhiram",
    "Kiran",
    "Sales 1",
    "Sales 2",
    "Operations",
]

SALES_OPTIONS = [
    "",
    "Kiran",
    "Sales 1",
    "Sales 2",
    "Monitha",
    "Nethmi",
    "Abhiram",
]

MODE_OPTIONS = [
    "Air",
    "Sea",
    "Courier",
    "Land",
]

SERVICE_OPTIONS = [
    "EXW",
    "FCA",
    "FOB",
    "CIF",
    "CPT",
    "DAP",
    "DDU",
    "DDP",
]


st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
)

st.markdown(
    f"""
<style>
.block-container {{
    padding-top: 1.2rem;
    max-width: 1450px;
}}

.stButton>button {{
    background-color:{NAVY};
    color:white;
    border-radius:8px;
}}

.stDownloadButton>button {{
    background-color:{PINK};
    color:white;
    border-radius:8px;
}}

div[data-testid="stMetricValue"] {{
    color:{NAVY};
}}

.compact-box {{
    background:#eef1f5;
    padding:14px;
    border-radius:8px;
    min-height:46px;
    display:flex;
    align-items:center;
}}
</style>
""",
    unsafe_allow_html=True,
)


def logo_path():
    for p in [
        Path("marvento_logo.png"),
        Path("assets/marvento_logo.png"),
    ]:
        if p.exists():
            return p
    return None


def conn():
    return sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
    )


def ensure_column(cur, table, column, definition):
    cur.execute(
        f"PRAGMA table_info({table})"
    )

    cols = [
        r[1]
        for r in cur.fetchall()
    ]

    if column not in cols:
        cur.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
        )


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
            country TEXT,
            industry TEXT,
            trn TEXT,
            created_at TEXT
        )"""
    )

    cur.execute(
        """CREATE TABLE IF NOT EXISTS enquiries(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enquiry_no TEXT UNIQUE,
            customer_name TEXT,
            mode TEXT,
            service TEXT,
            origin TEXT,
            destination TEXT,
            cargo_summary TEXT,
            status TEXT,
            salesperson TEXT,
            csp_name TEXT,
            source TEXT,
            cargo_ready_date TEXT,
            follow_up_date TEXT,
            win_probability REAL,
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
            csp_name TEXT,
            exchange_rate REAL,
            quote_json TEXT,
            pdf BLOB,
            confirmed_at TEXT,
            created_at TEXT
        )"""
    )

    for table, cols in {
        "customers": [
            ("country", "TEXT"),
            ("industry", "TEXT"),
            ("trn", "TEXT"),
        ],
        "enquiries": [
            ("source", "TEXT"),
            ("cargo_ready_date", "TEXT"),
            ("follow_up_date", "TEXT"),
            ("win_probability", "REAL"),
            ("csp_name", "TEXT"),
        ],
        "quotes": [
            ("csp_name", "TEXT"),
            ("exchange_rate", "REAL"),
            ("confirmed_at", "TEXT"),
        ],
    }.items():
        for col, definition in cols:
            ensure_column(
                cur,
                table,
                col,
                definition,
            )

    c.commit()
    c.close()

def qdf(query, params=()):
    c = conn()
    try:
        return pd.read_sql_query(
            query,
            c,
            params=params,
        )
    finally:
        c.close()


def execute_db(sql, params=()):
    c = conn()
    cur = c.cursor()
    cur.execute(
        sql,
        params,
    )
    c.commit()
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
    p = logo_path()

    if p:
        st.image(
            str(p),
            width=width,
        )
    else:
        st.markdown(
            f"### {COMPANY['name']}"
        )


def option_index(options, value, default=0):
    try:
        return options.index(value)
    except Exception:
        return default


def safe_date(value):
    try:
        if value:
            return dt.datetime.strptime(
                str(value),
                "%Y-%m-%d",
            ).date()
    except Exception:
        pass

    return dt.date.today()


def login():
    if st.session_state.get("logged_in"):
        return True

    col1, col2, col3 = st.columns(
        [1, 1.2, 1]
    )

    with col2:
        add_logo(260)

        st.subheader("Rate Desk Pro Login")

        u = st.text_input(
            "Username",
            key="login_username",
        )

        p = st.text_input(
            "Password",
            type="password",
            key="login_password",
        )

        if st.button(
            "Login",
            use_container_width=True,
            key="login_button",
        ):
            if u in USERS and USERS[u]["password"] == p:
                st.session_state.logged_in = True
                st.session_state.user = u
                st.session_state.role = USERS[u]["role"]
                st.session_state.name = USERS[u]["name"]
                st.rerun()
            else:
                st.error(
                    "Invalid username or password"
                )

    return False


def customer_options():
    df = qdf(
        "SELECT name FROM customers ORDER BY name"
    )

    if df.empty:
        return []

    return df["name"].tolist()


def get_customer(name):
    if not name:
        return {}

    df = qdf(
        "SELECT * FROM customers WHERE name=?",
        (name,),
    )

    if df.empty:
        return {}

    return df.iloc[0].to_dict()


def save_customer(
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
):
    if not name:
        return

    c = conn()
    cur = c.cursor()

    cur.execute(
        """INSERT INTO customers(
            name,
            contact_person,
            email,
            phone,
            address,
            credit_terms,
            salesperson,
            country,
            industry,
            trn,
            created_at
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
            dt.datetime.now().isoformat(
                timespec="seconds"
            ),
        ),
    )

    c.commit()
    c.close()


def ai_cargo_upload_section():
    st.markdown(
        "#### AI Cargo Extraction from Document"
    )

    st.caption(
        "Phase 2 preparation: upload PDF/image now. AI reading engine can be connected later."
    )

    cargo_file = st.file_uploader(
        "Upload packing list / customer PDF / screenshot",
        type=[
            "pdf",
            "png",
            "jpg",
            "jpeg",
        ],
        key="ai_cargo_file_uploader",
    )

    if cargo_file:
        st.success(
            f"Uploaded: {cargo_file.name}"
        )

        st.info(
            "Next Phase 2 engine will extract pieces, dimensions, gross weight, CBM and chargeable weight automatically."
        )

def cargo_section(mode):
    st.markdown("#### Cargo Details")

    if "cargo_rows" not in st.session_state:
        st.session_state.cargo_rows = 3

    if st.session_state.cargo_rows < 3:
        st.session_state.cargo_rows = 3

    rows = []

    if mode == "Sea":
        total_cbm = 0.0
        total_gw = 0.0
        total_containers = 0

        h1, h2, h3, h4, h5 = st.columns([1.2, 1.1, 1.2, 1.2, 2.5])
        h1.markdown("**Equipment**")
        h2.markdown("**CBM / Qty**")
        h3.markdown("**Gross Weight KG**")
        h4.markdown("**Packages**")
        h5.markdown("**Cargo Description**")

        for i in range(st.session_state.cargo_rows):
            c1, c2, c3, c4, c5 = st.columns([1.2, 1.1, 1.2, 1.2, 2.5])

            eq = c1.selectbox(
                "Equipment",
                ["LCL", "20DV", "40STD", "40HC", "40RF", "40FR", "45HC"],
                key=f"sea_equipment_{i}",
                label_visibility="collapsed",
            )

            if eq == "LCL":
                cbm = c2.number_input(
                    "CBM",
                    min_value=0.0,
                    value=0.0,
                    key=f"sea_cbm_{i}",
                    label_visibility="collapsed",
                )

                gw = c3.number_input(
                    "Gross Weight KG",
                    min_value=0.0,
                    value=0.0,
                    key=f"sea_gw_{i}",
                    label_visibility="collapsed",
                )

                packages = c4.number_input(
                    "Packages",
                    min_value=1,
                    value=1,
                    key=f"sea_pkg_{i}",
                    label_visibility="collapsed",
                )

                desc = c5.text_input(
                    "Cargo Description",
                    key=f"sea_desc_{i}",
                    label_visibility="collapsed",
                )

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
                qty = c2.number_input(
                    "Container Qty",
                    min_value=1,
                    value=1,
                    key=f"sea_container_qty_{i}",
                    label_visibility="collapsed",
                )

                gw = c3.number_input(
                    "Gross Weight KG",
                    min_value=0.0,
                    value=0.0,
                    key=f"sea_fcl_gw_{i}",
                    label_visibility="collapsed",
                )

                packages = c4.number_input(
                    "Packages",
                    min_value=0,
                    value=0,
                    key=f"sea_fcl_pkg_{i}",
                    label_visibility="collapsed",
                )

                desc = c5.text_input(
                    "Cargo Description",
                    key=f"sea_fcl_desc_{i}",
                    label_visibility="collapsed",
                )

                total_containers += qty
                total_gw += gw

                rows.append(
                    {
                        "equipment": eq,
                        "qty": qty,
                        "packages": packages,
                        "gross_weight": gw,
                        "description": desc,
                    }
                )

        if st.button("+ Add Cargo Row", key="add_cargo_row_button"):
            st.session_state.cargo_rows += 1
            st.rerun()

        st.info(
            f"Sea Summary: Total CBM {total_cbm:.3f} | "
            f"Total Gross Weight {total_gw:.2f} KG | "
            f"Total Containers {total_containers}"
        )

    else:
        total_cbm = 0.0
        total_gw = 0.0
        total_chw = 0.0

        h1, h2, h3, h4, h5, h6, h7 = st.columns([0.8, 1, 1, 1, 1, 1, 1])
        h1.markdown("**Pcs**")
        h2.markdown("**L cm**")
        h3.markdown("**W cm**")
        h4.markdown("**H cm**")
        h5.markdown("**Gross KG**")
        h6.markdown("**CBM**")
        h7.markdown("**Chg KG**")

        for i in range(st.session_state.cargo_rows):
            c1, c2, c3, c4, c5, c6, c7 = st.columns([0.8, 1, 1, 1, 1, 1, 1])

            pcs = c1.number_input(
                "Pcs",
                min_value=1,
                value=1,
                key=f"air_pcs_{i}",
                label_visibility="collapsed",
            )

            l = c2.number_input(
                "L cm",
                min_value=0.0,
                value=0.0,
                key=f"air_l_{i}",
                label_visibility="collapsed",
            )

            w = c3.number_input(
                "W cm",
                min_value=0.0,
                value=0.0,
                key=f"air_w_{i}",
                label_visibility="collapsed",
            )

            h = c4.number_input(
                "H cm",
                min_value=0.0,
                value=0.0,
                key=f"air_h_{i}",
                label_visibility="collapsed",
            )

            gw = c5.number_input(
                "Gross KG",
                min_value=0.0,
                value=0.0,
                key=f"air_gw_{i}",
                label_visibility="collapsed",
            )

            cbm = (l * w * h * pcs) / 1_000_000 if l and w and h else 0.0
            vol = (l * w * h * pcs) / 6000 if l and w and h else 0.0
            chw = max(gw, vol)

            c6.markdown(
                f"<div class='compact-box'>{cbm:.3f}</div>",
                unsafe_allow_html=True,
            )

            c7.markdown(
                f"<div class='compact-box'>{chw:.2f}</div>",
                unsafe_allow_html=True,
            )

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

        if st.button("+ Add Cargo Row", key="add_cargo_row_button"):
            st.session_state.cargo_rows += 1
            st.rerun()

        st.info(
            f"Total Gross Weight: {total_gw:.2f} KG | "
            f"Total CBM: {total_cbm:.3f} | "
            f"Total Chargeable Weight: {total_chw:.2f} KG"
        )

    return rows


def quote_lines_section(exchange_rate=3.675):
    st.markdown("#### Manual Quote Lines")

    if "line_rows" not in st.session_state:
        st.session_state.line_rows = 4

    lines = []
    totals_by_currency = {}
    total_aed_equivalent = 0.0

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
            label_visibility="collapsed",
        )

        carrier = c2.text_input(
            "Carrier",
            key=f"quote_carrier_{i}",
            label_visibility="collapsed",
        )

        unit = c3.number_input(
            "Unit",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key=f"quote_unit_{i}",
            label_visibility="collapsed",
        )

        price = c4.number_input(
            "Unit Price",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key=f"quote_price_{i}",
            label_visibility="collapsed",
        )

        vat = c5.number_input(
            "VAT %",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key=f"quote_vat_{i}",
            label_visibility="collapsed",
        )

        curr = c6.selectbox(
            "Currency",
            ["AED", "USD", "EUR", "SAR", "INR", "GBP", "CNY"],
            key=f"quote_curr_{i}",
            label_visibility="collapsed",
        )

        total = unit * price
        total = total + (total * vat / 100)

        aed_value = total * exchange_rate

        c7.markdown(
            f"<div class='compact-box'>{total:,.2f}</div>",
            unsafe_allow_html=True,
        )

        remarks = c8.text_input(
            "Remarks",
            key=f"quote_remarks_{i}",
            label_visibility="collapsed",
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

    p = logo_path()

    if p:
        story.append(
            Image(
                str(p),
                width=55 * mm,
                height=22 * mm,
                hAlign="LEFT",
            )
        )

    story.append(
        Paragraph(
            f"<font color='{NAVY}' size='16'><b>QUOTATION</b></font>",
            styles["Title"],
        )
    )

    story.append(
        Paragraph(
            f"<b>{COMPANY['name']}</b><br/>"
            f"{COMPANY['address']}<br/>"
            f"Tel: {COMPANY['phone']} | Email: {COMPANY['email']} | "
            f"Web: {COMPANY['website']}<br/>"
            f"TRN: {COMPANY['trn']}",
            styles["Normal"],
        )
    )

    story.append(
        Spacer(
            1,
            6 * mm,
        )
    )

    info = [
        [
            "Quote No",
            data["quote_no"],
            "Date",
            dt.date.today().strftime("%d-%b-%Y"),
        ],
        [
            "Customer",
            data["customer_name"],
            "Validity",
            data.get("validity", ""),
        ],
        [
            "Attention",
            data.get("attention_to", ""),
            "Email",
            data.get("customer_email", ""),
        ],
        [
            "Mode",
            data["mode"],
            "Service",
            data["service"],
        ],
        [
            "Origin",
            data["origin"],
            "Destination",
            data["destination"],
        ],
        [
            "CSP Name",
            data.get("csp_name", ""),
            "Sales Person",
            data.get("sales_person", ""),
        ],
    ]

    t = Table(
        info,
        colWidths=[
            25 * mm,
            65 * mm,
            25 * mm,
            65 * mm,
        ],
    )

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
    story.append(
        Spacer(
            1,
            5 * mm,
        )
    )

    cargo_rows = data.get("cargo_rows", [])

    if cargo_rows:
        story.append(
            Paragraph(
                "<b>Cargo Details</b>",
                styles["Heading3"],
            )
        )

        if data["mode"] == "Sea":
            cargo_table = [
                [
                    "Equipment/Service",
                    "CBM/Qty",
                    "Packages",
                    "Gross Weight KG",
                    "Description",
                ]
            ]

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
                            r.get("qty", ""),
                            r.get("packages", ""),
                            f"{r.get('gross_weight', 0):,.2f}",
                            r.get("description", ""),
                        ]
                    )

        else:
            cargo_table = [
                [
                    "Pcs",
                    "Dimensions CM",
                    "Gross KG",
                    "CBM",
                    "Chargeable KG",
                ]
            ]

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

        ct = Table(
            cargo_table,
            repeatRows=1,
        )

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

        story.append(
            Spacer(
                1,
                5 * mm,
            )
        )

    story.append(
        Paragraph(
            "<b>Charges</b>",
            styles["Heading3"],
        )
    )

    charges = [
        [
            "Description",
            "Carrier",
            "Unit",
            "Unit Price",
            "VAT %",
            "Currency",
            "Total",
            "AED Value",
            "Remarks",
        ]
    ]

    for r in data.get("lines", []):
        charges.append(
            [
                r.get("description", ""),
                r.get("carrier", ""),
                r.get("unit", ""),
                f"{r.get('unit_price', 0):,.2f}",
                f"{r.get('vat', 0):,.2f}",
                r.get("currency", ""),
                f"{r.get('total', 0):,.2f}",
                f"{r.get('aed_value', 0):,.2f}",
                r.get("remarks", ""),
            ]
        )

    tbl = Table(
        charges,
        repeatRows=1,
    )

    tbl.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (2, 1), (-2, -1), "RIGHT"),
            ]
        )
    )

    story.append(tbl)

    story.append(
        Spacer(
            1,
            4 * mm,
        )
    )

    total_aed_equivalent = sum(
        float(r.get("aed_value", 0) or 0)
        for r in data.get("lines", [])
    )

    story.append(
        Paragraph(
            "<b>Total Selling Quote:</b> "
            + " | ".join(
                [
                    f"{k} {v:,.2f}"
                    for k, v in data.get("totals_by_currency", {}).items()
                ]
            )
            + f" | <b>AED Equivalent:</b> AED {total_aed_equivalent:,.2f}",
            styles["Heading3"],
        )
    )

    story.append(
        Spacer(
            1,
            6 * mm,
        )
    )

    story.append(
        Paragraph(
            "<b>Terms:</b> Subject to space, equipment availability, carrier acceptance and final cargo details. "
            "Duties, taxes, demurrage, detention, storage and inspections are excluded unless specifically mentioned.",
            styles["Normal"],
        )
    )

    story.append(
        Spacer(
            1,
            6 * mm,
        )
    )

    story.append(
        Paragraph(
            "Regards,<br/><b>Marvento Shipping LLC</b>",
            styles["Normal"],
        )
    )

    doc.build(story)

    return buf.getvalue()

def dashboard():
    st.subheader("Dashboard")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Customers", len(qdf("SELECT id FROM customers")))
    c2.metric("Open Enquiries", len(qdf("SELECT id FROM enquiries WHERE status='Open'")))
    c3.metric("Quotes", len(qdf("SELECT id FROM quotes")))
    c4.metric("Won Quotes", len(qdf("SELECT id FROM quotes WHERE status='Won'")))

    st.markdown("### Recent Enquiries")

    enq_df = qdf(
        "SELECT enquiry_no, customer_name, mode, origin, destination, "
        "status, csp_name, salesperson "
        "FROM enquiries ORDER BY id DESC"
    )

    if enq_df.empty:
        st.info("No enquiries yet.")
    else:
        st.dataframe(enq_df, use_container_width=True)

    st.markdown("### Recent Quotes")

    quote_df = qdf(
        "SELECT quote_no, enquiry_no, customer_name, mode, origin, destination, "
        "total, currency, status, salesperson, csp_name "
        "FROM quotes ORDER BY id DESC"
    )

    if quote_df.empty:
        st.info("No quotes yet.")
    else:
        st.dataframe(quote_df, use_container_width=True)

        qn = st.selectbox(
            "Select Quote to Download / Update Status",
            quote_df["quote_no"].tolist(),
            key="dashboard_quote_status_select",
        )

        selected_quote = quote_df[
            quote_df["quote_no"] == qn
        ].iloc[0].to_dict()

        status_options = ["Open", "Lost", "Won"]

        new_status = st.selectbox(
            "Quote Status",
            status_options,
            index=status_options.index(
                selected_quote.get("status")
                if selected_quote.get("status") in status_options
                else "Open"
            ),
            key="dashboard_quote_status_update",
        )

        cdb = conn()
        cur = cdb.cursor()

        cur.execute(
            "SELECT pdf, enquiry_no FROM quotes WHERE quote_no=?",
            (qn,),
        )

        row = cur.fetchone()
        cdb.close()

        col1, col2 = st.columns(2)

        with col1:
            if row and row[0]:
                st.download_button(
                    "Download Quote PDF",
                    data=row[0],
                    file_name=f"{qn}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="dashboard_download_quote_pdf",
                )

        with col2:
            if st.button(
                "Update Status",
                use_container_width=True,
                key="dashboard_update_quote_status_button",
            ):
                cdb = conn()
                cur = cdb.cursor()

                cur.execute(
                    "UPDATE quotes SET status=? WHERE quote_no=?",
                    (new_status, qn),
                )

                if row and row[1]:
                    cur.execute(
                        "UPDATE enquiries SET status=? WHERE enquiry_no=?",
                        (new_status, row[1]),
                    )

                cdb.commit()
                cdb.close()

                st.success(
                    f"Quote {qn} status updated to {new_status}"
                )

                st.rerun()


def customers_page():
    st.subheader("Customer Database")

    with st.expander(
        "Add / Update Customer",
        expanded=True,
    ):
        a, b = st.columns(2)

        name = a.text_input(
            "Customer Name",
            key="customer_name_input",
        )

        contact = b.text_input(
            "Contact Person",
            key="customer_contact_input",
        )

        email = a.text_input(
            "Email",
            key="customer_email_input",
        )

        phone = b.text_input(
            "Phone",
            key="customer_phone_input",
        )

        c1, c2, c3 = st.columns(3)

        country = c1.text_input(
            "Country",
            key="customer_country_input",
        )

        industry = c2.text_input(
            "Industry",
            key="customer_industry_input",
        )

        trn = c3.text_input(
            "Customer TRN",
            key="customer_trn_input",
        )

        address = st.text_area(
            "Address",
            key="customer_address_input",
        )

        c, d = st.columns(2)

        credit = c.text_input(
            "Credit Terms",
            key="customer_credit_input",
        )

        sales = d.selectbox(
            "Sales Person",
            SALES_OPTIONS,
            index=option_index(
                SALES_OPTIONS,
                st.session_state.get("name", ""),
                0,
            ),
            key="customer_salesperson_input",
        )

        if st.button(
            "Save Customer",
            key="save_customer_button",
        ) and name:
            save_customer(
                name,
                contact,
                email,
                phone,
                address,
                credit,
                sales,
                country,
                industry,
                trn,
            )

            st.success("Customer saved")

    st.dataframe(
        qdf(
            "SELECT name, contact_person, email, phone, country, industry, "
            "credit_terms, salesperson, created_at "
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

    selected_enquiry = None

    if not df_existing.empty:
        edit_existing = st.checkbox(
            "Edit existing enquiry",
            key="edit_existing_enquiry_checkbox",
        )

        if edit_existing:
            selected_enquiry_no = st.selectbox(
                "Select enquiry to edit",
                df_existing["enquiry_no"].tolist(),
                key="edit_enquiry_select",
            )

            selected_enquiry = df_existing[
                df_existing["enquiry_no"] == selected_enquiry_no
            ].iloc[0].to_dict()

    with st.expander(
        "Create / Edit Enquiry",
        expanded=True,
    ):
        if customers:
            default_customer_index = 0

            if (
                selected_enquiry
                and selected_enquiry.get("customer_name") in customers
            ):
                default_customer_index = customers.index(
                    selected_enquiry.get("customer_name")
                )

            customer = st.selectbox(
                "Customer",
                customers,
                index=default_customer_index,
                key="enquiry_customer_select",
            )

        else:
            customer = st.text_input(
                "Customer",
                value=selected_enquiry.get("customer_name", "")
                if selected_enquiry
                else "",
                key="enquiry_customer_text",
            )

        mode_options = [
            "Air",
            "Sea",
            "Courier",
            "Land",
        ]

        service_options = [
            "EXW",
            "FCA",
            "FOB",
            "CIF",
            "CPT",
            "DAP",
            "DDU",
            "DDP",
        ]

        source_options = [
            "Customer",
            "Agent",
            "Website",
            "WhatsApp",
            "Email",
            "Phone",
            "Referral",
        ]

        status_options = [
            "Open",
            "Quoted",
            "Won",
            "Lost",
            "Cancelled",
        ]

        a, b, c = st.columns(3)

        mode = a.selectbox(
            "Mode",
            mode_options,
            index=option_index(
                mode_options,
                selected_enquiry.get("mode")
                if selected_enquiry
                else "",
                0,
            ),
            key="enquiry_mode_select",
        )

        service = b.selectbox(
            "Service Required",
            service_options,
            index=option_index(
                service_options,
                selected_enquiry.get("service")
                if selected_enquiry
                else "",
                0,
            ),
            key="enquiry_service_select",
        )

        source = c.selectbox(
            "Enquiry Source",
            source_options,
            index=option_index(
                source_options,
                selected_enquiry.get("source")
                if selected_enquiry
                else "",
                0,
            ),
            key="enquiry_source_select",
        )

        d, e = st.columns(2)

        origin = d.text_input(
            "AOL / POL / Origin",
            value=selected_enquiry.get("origin", "")
            if selected_enquiry
            else "",
            key="enquiry_origin_input",
        )

        dest = e.text_input(
            "AOD / POD / Destination",
            value=selected_enquiry.get("destination", "")
            if selected_enquiry
            else "",
            key="enquiry_destination_input",
        )

        f, g, h = st.columns(3)

        cargo_ready = f.date_input(
            "Cargo Ready Date",
            value=safe_date(
                selected_enquiry.get("cargo_ready_date")
                if selected_enquiry
                else None
            ),
            key="enquiry_cargo_ready_date",
        )

        follow_up = g.date_input(
            "Follow Up Date",
            value=safe_date(
                selected_enquiry.get("follow_up_date")
                if selected_enquiry
                else None
            ),
            key="enquiry_follow_up_date",
        )

        win_probability = h.slider(
            "Win Probability %",
            0,
            100,
            int(selected_enquiry.get("win_probability", 50))
            if selected_enquiry
            and selected_enquiry.get("win_probability") is not None
            else 50,
            key="enquiry_win_probability",
        )

        p1, p2 = st.columns(2)

        csp_name = p1.text_input(
            "CSP Name",
            value=selected_enquiry.get("csp_name", "") if selected_enquiry else "",
            key="enquiry_csp_name_input",
        )

        salesperson = p2.text_input(
            "Sales Person",
            value=selected_enquiry.get("salesperson", st.session_state.get("name", "")) if selected_enquiry else st.session_state.get("name", ""),
            key="enquiry_salesperson_input",
        )
        cargo = st.text_area(
            "Cargo Summary",
            value=selected_enquiry.get("cargo_summary", "")
            if selected_enquiry
            else "",
            key="enquiry_cargo_summary",
        )

        status = st.selectbox(
            "Status",
            status_options,
            index=option_index(
                status_options,
                selected_enquiry.get("status")
                if selected_enquiry
                else "",
                0,
            ),
            key="enquiry_status_select",
        )

        button_label = (
            "Update Enquiry"
            if selected_enquiry
            else "Save Enquiry"
        )

        if st.button(
            button_label,
            key="save_or_update_enquiry_button",
        ) and customer:
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
                        csp_name=?,
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
                        csp_name,
                        str(cargo_ready),
                        str(follow_up),
                        win_probability,
                        selected_enquiry["enquiry_no"],
                    ),
                )

                cdb.commit()
                cdb.close()

                st.success(
                    f"Enquiry updated: {selected_enquiry['enquiry_no']}"
                )

            else:
                enq = next_no(
                    "ENQ",
                    "enquiries",
                    "enquiry_no",
                )

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
                        csp_name,
                        cargo_ready_date,
                        follow_up_date,
                        win_probability,
                        created_at
                    )
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                        csp_name,
                        str(cargo_ready),
                        str(follow_up),
                        win_probability,
                        dt.datetime.now().isoformat(
                            timespec="seconds"
                        ),
                    ),
                )

                cdb.commit()
                cdb.close()

                st.success(
                    f"Enquiry saved: {enq}"
                )

    st.dataframe(
        qdf(
            "SELECT enquiry_no, customer_name, mode, service, source, "
            "origin, destination, status, csp_name, salesperson as sales_person, "
            "cargo_ready_date, follow_up_date, win_probability, created_at "
            "FROM enquiries ORDER BY id DESC"
        ),
        use_container_width=True,
    )

def quote_page():
    st.subheader("Quotation Generator")

    customers = customer_options()

    enqs = qdf(
        "SELECT * FROM enquiries ORDER BY id DESC"
    )

    use_enq = st.checkbox(
        "Create from existing enquiry",
        key="quote_use_existing_enquiry",
    )

    selected = None

    if use_enq and not enqs.empty:
        enq_list = enqs["enquiry_no"].tolist()

        default_index = 0

        dash_enq = st.session_state.get(
            "dashboard_enquiry_no"
        )

        if dash_enq in enq_list:
            default_index = enq_list.index(
                dash_enq
            )

        enq_no = st.selectbox(
            "Select Enquiry",
            enq_list,
            index=default_index,
            key="quote_enquiry_select",
        )

        selected = enqs[
            enqs["enquiry_no"] == enq_no
        ].iloc[0].to_dict()

        st.success(
            f"Loaded enquiry: {selected['enquiry_no']}"
        )

    if selected:
        customer = selected.get(
            "customer_name",
            "",
        )

        walk_in = False

    else:
        walk_in = st.checkbox(
            "Walk-in Customer",
            key="quote_walk_in_customer",
        )

        if walk_in:
            customer = st.text_input(
                "Walk-in Customer Name",
                key="quote_walk_in_customer_name",
            )

        else:
            customer = (
                st.selectbox(
                    "Customer",
                    customers,
                    key="quote_customer_select",
                )
                if customers
                else st.text_input(
                    "Customer",
                    key="quote_customer_text",
                )
            )

    cust = (
        get_customer(customer)
        if not walk_in
        else {}
    )

    if walk_in:
        w1, w2, w3 = st.columns(3)

        walk_in_contact = w1.text_input(
            "Contact Person",
            key="quote_walk_in_contact",
        )

        walk_in_email = w2.text_input(
            "Customer Email",
            key="quote_walk_in_email",
        )

        walk_in_phone = w3.text_input(
            "Customer Phone",
            key="quote_walk_in_phone",
        )

    else:
        walk_in_contact = ""
        walk_in_email = ""
        walk_in_phone = ""

    mode_options = [
        "Air",
        "Sea",
        "Courier",
        "Land",
    ]

    service_options = [
        "EXW",
        "FCA",
        "FOB",
        "CIF",
        "CPT",
        "DAP",
        "DDU",
        "DDP",
    ]

    a, b, c, d = st.columns(4)

    mode = a.selectbox(
        "Mode",
        mode_options,
        index=option_index(
            mode_options,
            selected.get("mode")
            if selected
            else "",
            0,
        ),
        key="quote_mode_select",
    )

    service = b.selectbox(
        "Service",
        service_options,
        index=option_index(
            service_options,
            selected.get("service")
            if selected
            else "",
            0,
        ),
        key="quote_service_select",
    )

    origin = c.text_input(
        "AOL/POL/Origin",
        value=selected.get("origin", "")
        if selected
        else "",
        key="quote_origin_input",
    )

    dest = d.text_input(
        "AOD/POD/Destination",
        value=selected.get("destination", "")
        if selected
        else "",
        key="quote_destination_input",
    )

    e, f, g = st.columns(3)

    attention_to = e.text_input(
        "Attention To",
        value=walk_in_contact
        if walk_in
        else (
            cust.get("contact_person", "")
            if cust
            else ""
        ),
        key="quote_attention_input",
    )

    customer_email = f.text_input(
        "Customer Email",
        value=walk_in_email
        if walk_in
        else (
            cust.get("email", "")
            if cust
            else ""
        ),
        key="quote_email_input",
    )

    customer_phone = g.text_input(
        "Customer Phone",
        value=walk_in_phone
        if walk_in
        else (
            cust.get("phone", "")
            if cust
            else ""
        ),
        key="quote_phone_input",
    )

    p1, p2, p3 = st.columns(3)

    csp_name = p1.selectbox(
        "CSP Name",
        CSP_OPTIONS,
        index=option_index(
            CSP_OPTIONS,
            selected.get("csp_name")
            if selected
            else "",
            0,
        ),
        key="quote_csp_name",
    )

    sales_person = p2.selectbox(
        "Sales Person",
        SALES_OPTIONS,
        index=option_index(
            SALES_OPTIONS,
            selected.get("salesperson")
            if selected
            else st.session_state.get("name", ""),
            0,
        ),
        key="quote_sales_person",
    )

    validity = p3.text_input(
        "Rate Validity",
        value="15 days",
        key="quote_validity_input",
    )

    if selected and selected.get("cargo_summary"):
        st.info(
            f"Cargo Summary from Enquiry: {selected.get('cargo_summary')}"
        )
    if selected:
        st.markdown("#### Enquiry Details Loaded")

        st.table(
            pd.DataFrame(
                [
                    ["Enquiry No", selected.get("enquiry_no", "")],
                    ["Customer", selected.get("customer_name", "")],
                    ["Mode", selected.get("mode", "")],
                    ["Service", selected.get("service", "")],
                    ["Origin", selected.get("origin", "")],
                    ["Destination", selected.get("destination", "")],
                    ["Cargo Ready Date", selected.get("cargo_ready_date", "")],
                    ["Follow Up Date", selected.get("follow_up_date", "")],
                    ["CSP Name", selected.get("csp_name", "")],
                    ["Sales Person", selected.get("salesperson", "")],
                    ["Cargo Summary", selected.get("cargo_summary", "")],
                ],
                columns=["Field", "Value"],
            )
        )
    if selected and selected.get("cargo_summary"):
        st.text_area(
            "Cargo Summary from Enquiry",
            value=selected.get("cargo_summary", ""),
            key="quote_loaded_cargo_summary",
            disabled=True,
        )

    ai_cargo_upload_section()

    cargo_rows = cargo_section(mode)

    exchange_rate = st.number_input(
        "AED Equivalent Exchange Rate",
        min_value=0.0,
        value=3.685,
        step=0.001,
        format="%.3f",
        key="exchange_rate",
    )

    lines, totals = quote_lines_section(
        exchange_rate
    )

    quote_no = next_no(
        "MQ",
        "quotes",
        "quote_no",
    )

    if lines:
        primary_currency = list(
            totals.keys()
        )[0]

        primary_total = totals[
            primary_currency
        ]

    else:
        primary_currency = "AED"
        primary_total = 0.0

    data = {
        "quote_no": quote_no,
        "enquiry_no": selected.get("enquiry_no", "")
        if selected
        else "",
        "customer_name": customer,
        "attention_to": attention_to,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "csp_name": csp_name,
        "sales_person": sales_person,
        "mode": mode,
        "service": service,
        "origin": origin,
        "destination": dest,
        "validity": validity,
        "cargo_rows": cargo_rows,
        "lines": lines,
        "totals_by_currency": totals,
        "exchange_rate": exchange_rate,
    }

    pdf = (
        make_pdf(data)
        if customer and lines
        else None
    )

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
            key="save_quote_button",
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
                    csp_name,
                    exchange_rate,
                    quote_json,
                    pdf,
                    created_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    quote_no,
                    selected.get("enquiry_no", "")
                    if selected
                    else "",
                    customer,
                    mode,
                    origin,
                    dest,
                    service,
                    validity,
                    primary_currency,
                    primary_total,
                    "Draft",
                    sales_person,
                    csp_name,
                    exchange_rate,
                    json.dumps(data),
                    pdf,
                    dt.datetime.now().isoformat(
                        timespec="seconds"
                    ),
                ),
            )

            cdb.commit()
            cdb.close()

            if selected:
                execute_db(
                    "UPDATE enquiries SET status='Quoted' WHERE enquiry_no=?",
                    (
                        selected.get("enquiry_no"),
                    ),
                )

            if walk_in and customer:
                save_customer(
                    customer,
                    attention_to,
                    customer_email,
                    customer_phone,
                    "",
                    "",
                    sales_person,
                    "",
                    "",
                    "",
                )

            st.success(
                f"Quote saved: {quote_no}"
            )

def saved_quotes_page():
    st.subheader("Saved Quotations")

    search = st.text_input(
        "Search customer / quote number",
        key="saved_quote_search",
    )

    if search:
        df = qdf(
            "SELECT id, quote_no, customer_name, mode, origin, destination, "
            "total, currency, status, salesperson, csp_name, created_at "
            "FROM quotes WHERE quote_no LIKE ? OR customer_name LIKE ? "
            "ORDER BY id DESC",
            (
                f"%{search}%",
                f"%{search}%",
            ),
        )

    else:
        df = qdf(
            "SELECT id, quote_no, customer_name, mode, origin, destination, "
            "total, currency, status, salesperson, csp_name, created_at "
            "FROM quotes ORDER BY id DESC"
        )

    if not df.empty:
        st.dataframe(
            df.drop(columns=["id"]),
            use_container_width=True,
        )

    else:
        st.dataframe(
            df,
            use_container_width=True,
        )

    if not df.empty:
        qn = st.selectbox(
            "Select quote to download",
            df["quote_no"].tolist(),
            key="saved_quote_select",
        )

        row = df[
            df["quote_no"] == qn
        ].iloc[0]

        cdb = conn()
        cur = cdb.cursor()

        cur.execute(
            "SELECT pdf FROM quotes WHERE id=?",
            (
                int(row["id"]),
            ),
        )

        result = cur.fetchone()
        cdb.close()

        if result and result[0]:
            st.download_button(
                "Re-download Saved PDF",
                data=result[0],
                file_name=f"{qn}.pdf",
                mime="application/pdf",
                key="saved_quote_download_button",
            )


def main():
    init_db()

    if not login():
        return

    col1, col2 = st.columns(
        [
            5,
            1,
        ]
    )

    with col1:
        add_logo(220)

        st.caption(
            f"Logged in as {st.session_state.name} | Role: {st.session_state.role}"
        )

    with col2:
        if st.button(
            "Logout",
            key="logout_button",
        ):
            st.session_state.clear()
            st.rerun()

    tabs = st.tabs(
        [
            "Dashboard",
            "Customers",
            "Enquiries",
            "Create Quote",
            "Saved Quotes",
        ]
    )

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



