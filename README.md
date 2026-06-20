# Marvento Rate Desk V5

This version improves tariff fetching and makes matching transparent.

## Added / Fixed
- Stronger AI-style tariff extraction from CSV, all Excel sheets, PDF tables, and PDF text.
- Supports sea equipment columns like `20DV`, `20DC`, `20GP`, `40STD`, `40GP`, `40HC`, `40HQ`, `40RF`, `40FR`.
- Auto Quote now ranks by mode, lane, equipment, source text, and rate presence.
- If no exact lane match is found, it shows fallback rate options instead of silently showing zero.
- Diagnostic table shows match score, match reason, and calculated buying amount.
- Manual quote totals and PDF quote totals are retained.
- PDF quote keeps Marvento logo top-left if logo is uploaded.

## Important tariff columns
For best results, use these columns in CSV/Excel:

`vendor, mode, origin, destination, equipment, service, currency, min_charge, rate_per_kg, rate_per_cbm, rate_per_container, doc_fee, fuel_pct, other_charges, transit_days, valid_from, valid_to, remarks`

For Sea FCL:
- `mode` = Sea
- `origin` = POL
- `destination` = POD
- `equipment` = 20DV / 40STD / 40HC / 40RF / 40 FR
- `rate_per_container` = buying ocean freight per container

For Air/Courier:
- `mode` = Air or Courier
- `origin` = AOL
- `destination` = AOD
- `rate_per_kg` = buying rate per chargeable kg
- `min_charge` optional

## Deploy
Upload `app.py`, `requirements.txt`, and `README.md` to GitHub. Streamlit will redeploy automatically.
