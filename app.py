import requests
import pandas as pd
import streamlit as st
from io import BytesIO
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="Ireland Visa Decision Checker – New Delhi",
    page_icon="🇮🇪",
    layout="centered",
)

BASE_URL = "https://www.ireland.ie/en/india/newdelhi/services/visas/processing-times-and-decisions/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )
}


def normalize_app_number(value: str) -> str:
    """Strip optional IRL/irl prefix and whitespace so all formats match."""
    return value.strip().upper().removeprefix("IRL")


def validate_input(raw: str) -> tuple[bool, str, str]:
    """
    Validate the user's input.
    Returns (is_valid, error_message, normalized_number).
    Valid formats: 12345678 | IRL12345678 | irl12345678
    """
    raw = raw.strip()
    if not raw:
        return False, "", ""

    upper = raw.upper()

    # Check for special characters (only letters and digits allowed)
    import re
    if not re.match(r'^[A-Za-z0-9]+$', raw):
        return False, "❌ No spaces or special characters allowed. Use format: `IRL12345678` or `12345678`", ""

    # Strip IRL prefix if present
    if upper.startswith("IRL"):
        prefix = raw[:3]
        numeric_part = raw[3:]
        # Anything after IRL must be digits only
        if not numeric_part.isdigit():
            return False, f"❌ After `{prefix}` only digits are allowed. Example: `IRL63690452`", ""
    else:
        # No IRL prefix — check for any letters in the input
        if not raw.isdigit():
            # Find which letters are present
            letters_found = "".join(sorted(set(c for c in raw.upper() if c.isalpha())))
            if upper.endswith(tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")):
                return False, f"❌ Letters must come at the **start** as `IRL` prefix only. Found `{letters_found}` at end.", ""
            return False, f"❌ Only the prefix `IRL` is allowed. Found unexpected letters: `{letters_found}`. Use `IRL12345678` or `12345678`", ""
        numeric_part = raw

    # Check digit length — must be exactly 8
    if len(numeric_part) < 8:
        return False, f"❌ Application number is too short ({len(numeric_part)} digits). Must be exactly **8 digits**. Example: `IRL63690452`", ""
    if len(numeric_part) > 8:
        return False, f"❌ Application number is too long ({len(numeric_part)} digits). Must be exactly **8 digits**. Example: `IRL63690452`", ""

    return True, "", numeric_part


def df_to_html_table_nearest(dataframe):
    """Render nearest-numbers table as plain HTML with coloured decisions."""
    rows = ""
    for _, row in dataframe.iterrows():
        decision_val = str(row["Decision"])
        if "approv" in decision_val.lower():
            badge = f'<span style="color:#1e7e34;font-weight:600">{decision_val}</span>'
        elif "refus" in decision_val.lower():
            badge = f'<span style="color:#c0392b;font-weight:600">{decision_val}</span>'
        else:
            badge = decision_val
        rows += (
            f"<tr>"
            f"<td style='padding:6px'>{row['Nearest Application']}</td>"
            f"<td style='padding:6px;text-align:right'>{row['Application Number']}</td>"
            f"<td style='padding:6px'>{badge}</td>"
            f"<td style='padding:6px;text-align:right'>{row['Difference']}</td>"
            f"</tr>"
        )
    return (
        "<table style='width:100%;border-collapse:collapse;font-size:14px'>"
        "<thead><tr style='border-bottom:2px solid #ddd'>"
        "<th style='text-align:left;padding:6px'>Nearest Application</th>"
        "<th style='text-align:right;padding:6px'>Application Number</th>"
        "<th style='text-align:left;padding:6px'>Decision</th>"
        "<th style='text-align:right;padding:6px'>Difference</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def df_to_html_table(dataframe):
    """Render a DataFrame as a plain HTML table with no pyarrow dependency."""
    rows = ""
    for _, row in dataframe.iterrows():
        decision_val = str(row["Decision"])
        if "approv" in decision_val.lower():
            badge = f'<span style="color:#1e7e34;font-weight:600">{decision_val}</span>'
        elif "refus" in decision_val.lower():
            badge = f'<span style="color:#c0392b;font-weight:600">{decision_val}</span>'
        else:
            badge = decision_val
        rows += f"<tr><td style='padding:6px'>{row['Application Number']}</td><td style='padding:6px'>{badge}</td></tr>"
    return (
        "<table style='width:100%;border-collapse:collapse;font-size:14px'>"
        "<thead><tr style='border-bottom:2px solid #ddd'>"
        "<th style='text-align:left;padding:6px'>Application Number</th>"
        "<th style='text-align:left;padding:6px'>Decision</th>"
        "</tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


@st.cache_data(ttl=3600)
def fetch_data() -> tuple[pd.DataFrame | None, str | None]:
    """Scrape the embassy page, download the ODS file, return (df, period_label)."""
    try:
        response = requests.get(BASE_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        return None, str(e)

    soup = BeautifulSoup(response.content, "html.parser")
    file_url = None
    period_label = None

    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        if "Visa decisions made from" in text and "January" in text:
            file_url = link.get("href", "")
            period_label = text
            if not file_url.startswith("http"):
                file_url = requests.compat.urljoin(BASE_URL, file_url)
            break

    if not file_url:
        return None, "Could not find the visa decisions file link on the website."

    try:
        ods_response = requests.get(file_url, headers=HEADERS, timeout=30)
        ods_response.raise_for_status()
    except requests.RequestException as e:
        return None, str(e)

    try:
        raw = pd.read_excel(BytesIO(ods_response.content), engine="odf", header=None)
    except Exception as e:
        return None, f"Failed to parse ODS file: {e}"

    # The file has 4 columns; real data lives in columns 2 & 3.
    # Row layout: metadata rows, then a header row containing "Application Number",
    # then data rows. Find the header row index dynamically.
    header_row = None
    for i, row in raw.iterrows():
        vals = [str(v).lower() for v in row.values]
        if any("application number" in v for v in vals):
            header_row = i
            break

    if header_row is None:
        return None, "Could not locate the 'Application Number' header in the file."

    # Extract period label from the file itself as a fallback
    if period_label is None:
        for i, row in raw.iterrows():
            for val in row.values:
                if isinstance(val, str) and "decisions for period" in val.lower():
                    period_label = val.strip()
                    break

    df = raw.iloc[header_row + 1:].copy()
    df = df.iloc[:, 2:4].copy()  # columns 2 & 3 contain the real data
    df.columns = ["Application Number", "Decision"]
    df.dropna(how="all", inplace=True)
    df = df[df["Application Number"].astype(str).str.strip().str.lower() != "application number"]
    df.reset_index(drop=True, inplace=True)
    df["Application Number"] = df["Application Number"].astype(str).str.strip()
    df["Decision"] = df["Decision"].astype(str).str.strip()

    return df, period_label


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("🇮🇪 Ireland Visa Decision Checker")
st.caption("New Delhi Embassy · Data sourced from ireland.ie")

with st.spinner("Loading latest visa decisions…"):
    df, meta = fetch_data()

if df is None:
    st.error(f"Could not load data: {meta}")
    st.stop()

st.success(f"**{meta}**" if meta else "Data loaded.")

# ── Stats row ─────────────────────────────────────────────────────────────────
total = len(df)
decisions = df["Decision"].value_counts()

col1, col2, col3 = st.columns(3)
col1.metric("Total Decisions", total)
col2.metric("Approved", int(decisions.get("Approved", decisions.get("Granted", 0))))
col3.metric("Refused", int(decisions.get("Refused", decisions.get("Rejected", 0))))

st.divider()

# ── Search ────────────────────────────────────────────────────────────────────
st.subheader("Check your application")
st.caption("Valid formats: `63690452` · `IRL63690452` · `irl63690452` — exactly 8 digits, optional IRL prefix")
query = st.text_input(
    "Enter your Application Number",
    placeholder="e.g. IRL63690452 or 63690452",
    max_chars=11,  # IRL (3) + 8 digits = 11 max
).strip()

if query:
    is_valid, error_msg, normalized_query = validate_input(query)

    if not is_valid:
        st.error(error_msg)
    else:
        df_normalized = df["Application Number"].apply(normalize_app_number)
        result = df[df_normalized == normalized_query]

        if result.empty:
            st.warning(f"No record found for Application Number: {normalized_query}.")

            # Find nearest application numbers
            try:
                query_int = int(normalized_query)
                nums = df["Application Number"].apply(
                    lambda x: int(normalize_app_number(x)) if normalize_app_number(x).isdigit() else None
                ).dropna().astype(int)

                below = nums[nums < query_int]
                above = nums[nums > query_int]

                nearest_rows = []
                if not below.empty:
                    closest_below_num = below.max()
                    closest_below = df[nums == closest_below_num].iloc[0]
                    nearest_rows.append({
                        "Nearest Application": "Before",
                        "Application Number": str(closest_below["Application Number"]),
                        "Decision": closest_below["Decision"],
                        "Difference": query_int - closest_below_num,
                    })
                if not above.empty:
                    closest_above_num = above.min()
                    closest_above = df[nums == closest_above_num].iloc[0]
                    nearest_rows.append({
                        "Nearest Application": "After",
                        "Application Number": str(closest_above["Application Number"]),
                        "Decision": closest_above["Decision"],
                        "Difference": closest_above_num - query_int,
                    })

                if nearest_rows:
                    st.subheader("Nearest Application Numbers")
                    nearest_df = pd.DataFrame(nearest_rows)
                    st.markdown(df_to_html_table_nearest(nearest_df), unsafe_allow_html=True)
            except ValueError:
                pass
        else:
            decision = result.iloc[0]["Decision"]
            app_num = result.iloc[0]["Application Number"]
            if "approv" in decision.lower() or "grant" in decision.lower():
                st.success(f"**Application {app_num} — Decision: {decision}** ✅")
            elif "refus" in decision.lower() or "reject" in decision.lower():
                st.error(f"**Application {app_num} — Decision: {decision}** ❌")
            else:
                st.info(f"**Application {app_num} — Decision: {decision}**")

st.divider()

# ── Download + Browse ─────────────────────────────────────────────────────────
csv = df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Download full dataset (CSV)",
    data=csv,
    file_name="ireland_visa_decisions.csv",
    mime="text/csv",
)

# with st.expander("Browse first 100 decisions"):
#     st.markdown(df_to_html_table(df.head(100)), unsafe_allow_html=True)

st.caption(
    "Data refreshes every hour. "
    f"[Source]({BASE_URL})"
)
