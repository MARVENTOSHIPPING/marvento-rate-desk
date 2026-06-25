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

