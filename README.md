# Marvento Rate Desk V6

Updates in V6:

- Air auto quote now displays the carrier/airline clearly.
- Sea auto quote now adds numeric surcharge columns from the same uploaded Excel/CSV row into the total buying cost.
- Surcharge details are shown in the `rate_breakdown` / `surcharge_details` columns.
- Auto quote selection shows carrier, equipment/service and buying total.
- PDF quote and prepared quote text include the selected carrier and final selling amount.

## Important for Sea tariff Excel

For best results, keep one row per lane/equipment with columns like:

- Carrier / Shipping Line
- Mode
- POL
- POD
- Equipment
- Ocean Freight or rate_per_container
- Currency
- BAF
- CAF
- THC
- ISPS
- Seal
- VGM
- Documentation
- Any other surcharge columns

V6 will add the numeric surcharge columns into `other_charges` and include them in buying cost.

## Upload to Streamlit

Upload these files to GitHub:

- app.py
- requirements.txt
- README.md

Then Streamlit will redeploy automatically.
