import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from apify_client import ApifyClient

# -------------------------------------------------------------------
# 🛑 PASTE YOUR API KEYS HERE 🛑
# -------------------------------------------------------------------
APIFY_API_TOKEN = st.secrets["APIFY_TOKEN"]
SERPAPI_API_KEY = st.secrets["SERPAPI_KEY"]
# -------------------------------------------------------------------

st.set_page_config(page_title="Competitor Ad Intelligence", layout="wide")

st.title("📊 Competitor Ad Intelligence Dashboard")
st.markdown("Instantly pull, combine, and analyze ad strategies from Meta and Google.")

with st.form("input_form"):
    col1, col2 = st.columns(2)
    with col1:
        meta_url = st.text_input("Meta Ad Library or FB Page URL", placeholder="https://www.facebook.com/competitor")
    with col2:
        google_domain = st.text_input("Google Ads Transparency Domain", placeholder="competitor.com")
        
    submit_button = st.form_submit_button(label="Generate Competitor Report")


def get_meta_ads(url, token):
    if not url or token == "YOUR_APIFY_TOKEN_HERE": 
        return []
        
    client = ApifyClient(token)
    run_input = {
        "startUrls": [{"url": url}],
        "resultsLimit": 15 # Keeping it low so it scrapes fast
    }
    
    # Triggers the Apify scraper
    run = client.actor("apify/facebook-ads-scraper").call(run_input=run_input)
    
    ads = []
    # Formats the data for Pandas
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        ads.append({
            "Platform": "Meta (FB/IG)",
            "Ad Start Date": str(item.get("startDate") or "Unknown")[:10],
            "Format": "Image/Video", 
            "Status": "Active" if item.get("isActive") else "Inactive",
            "Ad Copy Snippet": str(item.get("primaryText", "No text provided"))[:150] + "...",
        })
    return ads


def get_google_ads(domain, api_key):
    if not domain or api_key == "YOUR_SERPAPI_KEY_HERE": 
        return []
        
    # Calls the SerpApi endpoint
    url = f"https://serpapi.com/search.json?engine=google_ads_transparency_center&text={domain}&api_key={api_key}"
    response = requests.get(url).json()
    
    ads = []
    if "ad_creatives" in response:
        for ad in response["ad_creatives"]:
            ads.append({
                "Platform": "Google Ads",
                "Ad Start Date": ad.get("last_shown", "Unknown"),
                "Format": ad.get("format", "Unknown").title(),
                "Status": "Active", 
                "Ad Copy Snippet": "Google format (Check raw data for link)" if ad.get("format") != "text" else "Text Ad",
            })
    return ads


if submit_button:
    if not meta_url and not google_domain:
        st.warning("⚠️ Please enter at least one URL or Domain to begin.")
    elif APIFY_API_TOKEN == "YOUR_APIFY_TOKEN_HERE" or SERPAPI_API_KEY == "YOUR_SERPAPI_KEY_HERE":
        st.error("🛑 You forgot to add your API keys at the top of the code!")
    else:
        with st.spinner("Scraping live data from Meta and Google... (This can take 1-2 minutes)"):
            
            # 1. Pull data from both APIs
            meta_data = get_meta_ads(meta_url, APIFY_API_TOKEN)
            google_data = get_google_ads(google_domain, SERPAPI_API_KEY)
            
            # 2. Combine into one Pandas DataFrame
            combined_data = meta_data + google_data
            df = pd.DataFrame(combined_data)
            
            if df.empty:
                st.warning("No ads found. Check your URLs or ensure the competitor is currently running ads.")
            else:
                st.success("✅ Live Data successfully pulled and cleaned!")
                st.markdown("---")
                
                # --- TOP METRICS ---
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Ads Found", len(df))
                col2.metric("Active Meta Ads", len(df[(df["Platform"] == "Meta (FB/IG)") & (df["Status"] == "Active")]))
                col3.metric("Google Ads Logged", len(df[(df["Platform"] == "Google Ads")]))
                col4.metric("Dominant Format", df["Format"].mode()[0])
                
                st.markdown("---")
                
                # --- CHARTS (Plotly) ---
                st.subheader("📈 Competitor Strategy Visualized")
                chart_col1, chart_col2 = st.columns(2)
                
                with chart_col1:
                    fig_platform = px.pie(df, names="Platform", title="Ad Volume by Platform", hole=0.4)
                    st.plotly_chart(fig_platform, use_container_width=True)
                    
                with chart_col2:
                    fig_format = px.histogram(df, x="Format", color="Platform", title="Creative Format Breakdown", barmode="group")
                    st.plotly_chart(fig_format, use_container_width=True)

                # --- RAW DATA TABLE ---
                st.markdown("---")
                st.subheader("📂 Raw Ad Data")
                st.dataframe(df, use_container_width=True)
