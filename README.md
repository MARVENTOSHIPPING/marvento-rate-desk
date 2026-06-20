# Marvento Rate Desk App V3

New in V3:
- Saves uploaded tariff files into an app tariff database.
- Supports multiple CSV, Excel and PDF tariff uploads.
- Air mode shows AOL/AOD. Sea mode shows POL/POD.
- Service terms: EXW, FCA, FOB, CIF, CPT, DAP, DDU, DDP.
- Rate validity field.
- Auto quote option with rate selection.
- Manual quote table with Description, Carrier, Unit, Unit Price, VAT/Tax, Currency, Total.
- Prepared quote text reflects selected/entered values.
- PDF quote download with Marvento branding.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Login

Default username: `kiran.dxb@marventoshipping.com`
Default password: `ChangeMe123`

Change these in Streamlit secrets before sharing.

## Tariff upload

Click **Save uploaded tariff files** after choosing one or many tariff files.

Recommended tariff columns:

vendor, mode, origin, destination, service, currency, min_charge, rate_per_kg, rate_per_cbm, rate_per_container, doc_fee, fuel_pct, other_charges, transit_days, valid_from, valid_to, remarks

PDF support is best-effort and works best when the PDF has actual tables, not scanned images.
