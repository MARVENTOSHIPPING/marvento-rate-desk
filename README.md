# Marvento Rate Desk V7 - Manual Quote Only

This version removes tariff upload and auto-rate matching. The app is focused on manual quotation creation.

## Login
Default username: `kiran.dxb@marventoshipping.com`  
Default password: `ChangeMe123`

Change these in `app.py` before production use.

## Main changes
- Tariff and Auto Quote removed
- Manual quote table only
- Total selling quote calculation fixed
- Sea mode shows POL/POD, Gross Weight and Equipment only
- Sea equipment dropdown: 20DV, 40STD, 40HC, 40RF, 40 FR
- Add cargo lines using the manual quote table plus dynamic rows
- Tab key works inside the editable table field-by-field and continues to the next row
- PDF quote generation with Marvento branding placeholder on top left

## Deploy
Upload these files to GitHub:
- app.py
- requirements.txt
- README.md

Streamlit will redeploy automatically.
