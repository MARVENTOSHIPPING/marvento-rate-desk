# Marvento Rate Desk V4

Changes included:
- AI-assisted PDF/text tariff extraction and better auto quote matching.
- Sea mode shows POL/POD, equipment dropdown: 20DV, 40STD, 40HC, 40RF, 40 FR.
- Sea mode shows gross weight and equipment cargo details only, with a plus button for extra cargo lines.
- Manual quote total is calculated and reflected in quote text/PDF.
- Auto quote lets you select matched tariff options.
- PDF quote supports Marvento logo upload on left top and Marvento-style blue/orange colours.

Run:
```bash
pip install -r requirements.txt
streamlit run app.py
```

Default login:
- Username: kiran.dxb@marventoshipping.com
- Password: ChangeMe123

For Streamlit Cloud, change credentials in Secrets:
```
APP_USERNAME="your_username"
APP_PASSWORD="your_password"
```
