---
title: Ireland Visa Checker New Delhi
emoji: 🌍
colorFrom: green
colorTo: blue
sdk: streamlit
sdk_version: 1.44.1
app_file: app.py
pinned: false
---

# 🇮🇪 Ireland Visa Decision Checker — New Delhi

A Streamlit web app that lets applicants instantly look up their Irish visa decision by application number, using live data published by the Irish Embassy in New Delhi.

---

## What it does

- Scrapes the [Ireland Embassy New Delhi](https://www.ireland.ie/en/india/newdelhi/services/visas/processing-times-and-decisions/) page to find the latest visa decisions file
- Downloads and parses the `.ods` file automatically
- Displays total, approved, and refused counts
- Lets users search by application number in any format (`63690452`, `IRL63690452`, `irl63690452`)
- If no result is found, shows the nearest application numbers (before and after) with their decisions and difference
- Provides a full CSV download of all decisions
- Data refreshes every hour via Streamlit cache

---

## Running locally

**Prerequisites:** Python 3.11+

```bash
# 1. Clone / navigate to the project folder
cd "delhi irish visa"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The app will open at `http://localhost:8501`.

---

## Project structure

```
delhi irish visa/
├── app.py            # Main Streamlit application
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `streamlit` | Web app framework |
| `requests` | HTTP requests to embassy website |
| `beautifulsoup4` | Parse HTML to find the ODS file link |
| `pandas` | Data processing |
| `odfpy` | Read `.ods` spreadsheet files |

---

## Deploying

### Hugging Face Spaces
1. Create a new Space with **Streamlit** SDK
2. Upload `app.py` and `requirements.txt`
3. The Space will build and launch automatically

### Render
1. Create a new **Web Service** pointing to your repo
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

---

## Data source

All visa decision data is published by the Department of Justice / Irish Embassy New Delhi at:  
https://www.ireland.ie/en/india/newdelhi/services/visas/processing-times-and-decisions/
