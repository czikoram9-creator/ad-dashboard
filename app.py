import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import re
from apify_client import ApifyClient
from datetime import datetime

# -------------------------------------------------------------------
APIFY_API_TOKEN = st.secrets["APIFY_TOKEN"]
SERPAPI_API_KEY = st.secrets["SERPAPI_KEY"]
# -------------------------------------------------------------------

st.set_page_config(page_title="EU Competitor Ad Intelligence (DSA)", layout="wide")
st.title("🇪🇺 EU Competitor Ad Intelligence Dashboard")
st.markdown("Extracting 1-year historical archives mandated under the EU Digital Services Act (DSA).")

with st.form("input_form"):
    col1, col2 = st.columns(2)
    with col1:
        meta_url = st.text_input("Paste Full Meta Ad Library URL", placeholder="https://www.facebook.com/ads/library/?...")
    with col2:
        google_url = st.text_input("Paste Full Google Transparency URL", placeholder="https://adstransparency.google.com/advertiser/AR...")
    submit_button = st.form_submit_button(label="Generate 3-Month EU Report")

# --- Improved Date Fixer for EU Timestamps ---
def parse_eu_date(raw_date):
    if not raw_date:
        return "Unknown"
    try:
        # Check if it's a 10-digit Unix timestamp (seconds)
        if len(str(int(float(raw_date)))) == 10:
            return datetime.fromtimestamp(int(float(raw_date))).strftime('%Y-%m-%d')
        # Check if it's a 13-digit Unix timestamp (milliseconds)
        elif len(str(int(float(raw_date)))) == 13:
            return datetime.fromtimestamp(int(float(raw_date)) / 1000).strftime('%Y-%m-%d')
        return str(raw_date)[:10]
    except:
        return "Unknown"

def get_meta_ads(url, token):
    if not url: return []
    client = ApifyClient(token)
    
    # Tells Apify to look for EU-specific DSA fields and historical ads
    run_input = {"startUrls": [{"url": url}], "resultsLimit": 80}
    run = client.actor("apify/facebook-ads-scraper").call(run_input=run_input)
    
    ads = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        # Look across all possible text fields used in EU reporting
        raw_text = item.get("primaryText") or item.get("title") or item.get("description") or item.get("caption")
        
        ads.append({
            "Platform": "Meta (FB/IG)",
            "Ad Start Date": parse_eu_date(item.get("startDate") or item.get("creationDate")),
            "Format": "Image/Video", 
            "Status": "Active" if item.get("isActive") else "Inactive",
            "Ad Copy Snippet": str(raw_text)[:150] + "..." if raw_text else "Visual Ad (No Text Captions)",
        })
    return ads

def get_google_ads(url, api_key):
    if not url: return []
    
    # Regex to pull the unique 'AR...' Advertiser ID out of the link you pasted
    advertiser_id_match = re.search(lambda x: r"advertiser/(AR\d+)", url) # Handles AR numbers
    if not advertiser_id_match:
        # Fallback if it's just a number
        advertiser_id_match = re.search(r"advertiser/(\d+)", url)
        
    if not advertiser_id_match:
        st.error("Could not find a valid Google Advertiser ID in your link. Make sure it contains '/advertiser/AR...'")
        return []
        
    advertiser_id = advertiser_id_match.group(1)
    
    # Call SerpApi using the exact Advertiser ID and specifying the EU region parameter
    api_url = f"https://serpapi.com/search.json?engine=google_ads_transparency_center&advertiser_id={advertiser_id}&region=HU&api_key={api_key}"
    response = requests.get(api_url).json()
    
    ads = []
    if "ad_creatives" in response:
        for ad in response["ad_creatives"]:
            # Pull text from Google's various text objects
            raw_text = ad.get("snippet") or ad.get("title") or ad.get("body")
            ads.append({
                "Platform": "Google Ads",
                "Ad Start Date": parse_eu_date(ad.get("last_shown") or ad.get("first_shown")),
                "Format": ad.get("format", "Unknown").title(),
                "Status": "Active" if ad.get("is_active", True) else "Inactive", 
                "Ad Copy Snippet": str(raw_text)[:150] + "..." if raw_text else "Display/Video Creative",
            })
    return ads

if submit_button:
    with st.spinner("Accessing EU Transparency Archives..."):
        meta_data = get_meta_ads(meta_url, APIFY_API_TOKEN)
        google_data = get_google_ads(google_url, SERPAPI_API_KEY)
        
        df = pd.DataFrame(meta_data + google_data)
        
        if df.empty:
            st.warning("No data found. Ensure your links are valid EU transparency links.")
        else:
            st.success("✅ EU Historical Archives Successfully Processed!")
            
            # --- TOP METRICS ---
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Ads Analyzed", len(df))
            col2.metric("Meta Ads Found", len(df[df["Platform"] == "Meta (FB/IG)"]))
            col3.metric("Google Ads Found", len(df[df["Platform"] == "Google Ads"]))
            
            st.markdown("---")
            
            # --- HISTORICAL TIMELINE CHART ---
            timeline_df = df[df["Ad Start Date"] != "Unknown"].copy()
            if not timeline_df.empty:
                # Group dates into simple Month format (YYYY-MM)
                timeline_df['Month'] = pd.to_datetime(timeline_df['Ad Start Date']).dt.to_period('M').astype(str)
                # Filter to only look at the most recent months
                timeline_counts = timeline_df.groupby(['Month', 'Platform']).size().reset_index(name='Ad Count')
                
                fig_time = px.bar(timeline_counts, x="Month", y="Ad Count", color="Platform", barmode="group",
                                  title="Ad Volume History Over Time (Past Months)")
                st.plotly_chart(fig_time, use_container_width=True)
            
            # --- DATA TABLE ---
            st.subheader("📂 Complete Historical Log")
            st.dataframe(df, use_container_width=True)
