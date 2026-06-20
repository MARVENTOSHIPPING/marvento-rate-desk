# Marvento Rate Desk App

First working web app for Marvento rate desk quoting.

## Login

Default login for first test:

- Username: `kiran.dxb@marventoshipping.com`
- Password: `ChangeMe123`

Important: I cannot access your ChatGPT password. To use the same username/password you personally use, change the app secrets in Streamlit Cloud:

```toml
APP_USERNAME = "your username"
APP_PASSWORD = "your password"
```

## Easiest deployment: Streamlit Cloud

1. Unzip this folder.
2. Upload all files to a GitHub repository.
3. Go to Streamlit Cloud.
4. Create a new app.
5. Select the repository.
6. Main file path: `app.py`.
7. Add secrets:

```toml
APP_USERNAME = "kiran.dxb@marventoshipping.com"
APP_PASSWORD = "your chosen password"
```

8. Deploy.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Features

- Login screen
- Enter enquiry details
- Extract dimensions/weight from pasted email text, PDF, CSV, Excel, TXT, EML and image files where OCR is available
- Manual dimension and CBM entry
- Chargeable weight for Air, Courier, Land and Sea
- Import real tariff rates by CSV/Excel
- Download tariff CSV template inside the app
- Match tariffs by mode, origin and destination
- Rank rates by lowest total AED cost
- Calculate margin and selling quote
- Prepare quote text and download as TXT

## Tariff columns

Use the in-app template. Columns:

vendor, mode, origin, destination, service, currency, min_charge, rate_per_kg, rate_per_cbm, rate_per_container, doc_fee, fuel_pct, other_charges, transit_days, valid_from, valid_to, remarks
