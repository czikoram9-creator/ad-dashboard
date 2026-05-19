import streamlit as st
import pandas as pd
import requests
import re
from apify_client import ApifyClient
from datetime import datetime
from dateutil.relativedelta import relativedelta

# -------------------------------------------------------------------
APIFY_API_TOKEN = st.secrets["APIFY_TOKEN"]
SERPAPI_API_KEY = st.secrets["SERPAPI_KEY"]
# -------------------------------------------------------------------

st.set_page_config(page_title="Competitor Ad Matrix", layout="wide")
st.title("📊 3-Month Competitor Ad Matrix")
st.markdown("Batch process up to 5 competitors to get their raw ad volume counts over the last 3 months.")

# --- Figure out what the last 3 months are ---
today = datetime.today()
last_3_months = [(today - relativedelta(months=i)).strftime('%Y-%m') for i in range(3)]

# --- UI: Input Fields for 5 Competitors ---
st.markdown("### Enter Competitor Links")
competitor_inputs = []

with st.form("batch_form"):
    for i in range(1, 6):
        with st.expander(f"Competitor {i}", expanded=(i==1)):
            col1, col2, col3 = st.columns([1, 2, 2])
            with col1:
                name = st.text_input(f"Name", key=f"name_{i}", placeholder=f"Brand {i}")
            with col2:
                meta = st.text_input(f"Meta EU Link", key=f"meta_{i}", placeholder="https://www.facebook.com/ads/library/?...")
            with col3:
                google = st.text_input(f"Google EU Link", key=f"google_{i}", placeholder="https://adstransparency.google.com/advertiser/AR...")
            
            competitor_inputs.append({"name": name, "meta": meta, "google": google})
            
    submit_button = st.form_submit_button("Generate Volume Matrix")

# --- Date Helper ---
def parse_eu_date(raw_date):
    if not raw_date: return None
    try:
        if len(str(int(float(raw_date)))) == 10:
            return datetime.fromtimestamp(int(float(raw_date))).strftime('%Y-%m')
        elif len(str(int(float(raw_date)))) == 13:
            return datetime.fromtimestamp(int(float(raw_date)) / 1000).strftime('%Y-%m')
        return str(raw_date)[:7] 
    except:
        return None

# --- Fetchers ---
def get_counts(url, platform):
    if not url: return []
    dates = []
    
    if platform == "Meta":
        client = ApifyClient(APIFY_API_TOKEN)
        run = client.actor("apify/facebook-ads-scraper").call(run_input={"startUrls": [{"url": url}], "resultsLimit": 1000})
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            parsed_date = parse_eu_date(item.get("startDate") or item.get("creationDate"))
            if parsed_date in last_3_months: dates.append(parsed_date)
            
    elif platform == "Google":
        match = re.search(r"advertiser/(AR\d+)", url)
        if not match: return []
        api_url = f"https://serpapi.com/search.json?engine=google_ads_transparency_center&advertiser_id={match.group(1)}&api_key={SERPAPI_API_KEY}"
        
        for _ in range(5): # Up to 5 pages
            response = requests.get(api_url).json()
            if "ad_creatives" in response:
                for ad in response["ad_creatives"]:
                    parsed_date = parse_eu_date(ad.get("last_shown") or ad.get("first_shown"))
                    if parsed_date in last_3_months: dates.append(parsed_date)
            if "serpapi_pagination" in response and "next" in response["serpapi_pagination"]:
                api_url = response["serpapi_pagination"]["next"] + f"&api_key={SERPAPI_API_KEY}"
            else:
                break
                
    return dates

# --- Processing Logic ---
if submit_button:
    # Filter out empty rows
    active_competitors = [c for c in competitor_inputs if c["name"] and (c["meta"] or c["google"])]
    
    if not active_competitors:
        st.error("Please enter at least one competitor name and link.")
    else:
        with st.spinner(f"Scraping background data for {len(active_competitors)} competitors..."):
            
            final_table = []
            
            for comp in active_competitors:
                # 1. Fetch raw date lists
                meta_dates = get_counts(comp["meta"], "Meta")
                google_dates = get_counts(comp["google"], "Google")
                
                # 2. Build the row for this competitor
                row = {"Competitor": comp["name"]}
                
                # 3. Count occurrences for the last 3 months
                for month in last_3_months:
                    row[f"{month} (Meta)"] = meta_dates.count(month)
                    row[f"{month} (Google)"] = google_dates.count(month)
                    
                final_table.append(row)
            
            st.success("✅ Matrix Generated!")
            
            # --- Display Final Matrix ---
            df = pd.DataFrame(final_table)
            
            # Make the table look nice and stretch across the screen
            st.dataframe(df, use_container_width=True, hide_index=True)
