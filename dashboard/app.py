import streamlit as st
import pandas as pd
import os
from datetime import datetime
from google import genai
from google.genai import types
from utils import get_available_partitions, load_data, apply_custom_css, parse_dates

# Page Configuration
st.set_page_config(
    page_title="Antigravity - Smart Specials",
    page_icon="🚀",
    layout="wide",
)

def get_global_filters():
    """Renders global filters in the sidebar and returns the selected data."""
    st.sidebar.header("📍 Global Filters")
    province_map, date_map = get_available_partitions()
    
    if not province_map:
        return None, None, pd.DataFrame()

    # Province Selection
    dropdown_options = sorted([k for k in province_map.keys() if k.lower() != 'national'])
    sel_province = st.sidebar.selectbox("Select Province", dropdown_options)
    
    # Date Selection
    today = pd.Timestamp.now().normalize()
    available_dates = sorted(date_map.keys(), reverse=True)
    active_dates = []
    for label in available_dates:
        _, end_dt = parse_dates(label)
        if end_dt and end_dt >= today:
            active_dates.append(label)

    default_selection = active_dates if active_dates else ([available_dates[0]] if available_dates else [])
    sel_dates = st.sidebar.multiselect("Date Ranges", available_dates, default=default_selection)
    
    # Refresh Data Button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Target Folders Logic
    national_key = next((k for k in province_map.keys() if k.lower() == 'national'), None)
    national_folders = province_map[national_key] if national_key else []
    
    target_folders = []
    if sel_province: target_folders.extend(province_map[sel_province])
    target_folders.extend(national_folders)
    
    df = load_data(target_folders, sel_dates, date_map)
    return sel_province, sel_dates, df

def render_deal_grid(df):
    """Common grid renderer for deals."""
    if df.empty:
        st.warning("No deals found for this selection.")
        return

    rows = (len(df) + 2) // 3
    for r in range(rows):
        cols = st.columns(3)
        for c in range(3):
            idx = r * 3 + c
            if idx < len(df):
                item = df.iloc[idx]
                origin = item.get('_origin', 'Province')
                badge_class = "badge-national" if origin == "National" else "badge-province"
                date_range = item.get('_date_range', '')
                
                # Format prices
                current_price = f"R {item.current_price:.2f}"
                was_html = ""
                if not pd.isna(item.get('was_price')) and item.was_price > 0:
                    was_html = f"<span class='was-price'>R {item.was_price:.2f}</span>"
                
                discount_html = ""
                if 'discount_pct' in item and item.discount_pct > 0:
                    discount_html = f"<span class='discount-badge'>({item.discount_pct:.0f}% OFF)</span>"
                
                meta = f"{item.get('weight_volume', '')} {item.get('unit', '')}".strip()
                if not meta or meta == "nan nan": meta = ""

                html = f"""
                <div class="deal-card">
                    <div class="origin-badge {badge_class}">{origin}</div>
                    <div class="date-range-label">{date_range}</div>
                    <span class="brand-tag">{item.get('brand', 'PnP')}</span>
                    <div class="product-name">{item["product_name"]}</div>
                    <div class="price-container">
                        <span class="price-tag">{current_price}</span>
                        {was_html} {discount_html}
                    </div>
                    <div class="meta-info">{meta}</div>
                </div>
                """
                cols[c].html(html)
                
                # Check if we are in AI mode to show pro-tips
                if 'is_ai_mode' in st.session_state and st.session_state.is_ai_mode:
                    try:
                        # We pass the pro-tip back from the AI loop if possible, 
                        # but for simplicity, we'll just handle it here if it exists in the row
                        if '_pro_tip' in item:
                            cols[c].caption(f"💡 {item['_pro_tip']}")
                    except: pass

def deal_finder():
    st.markdown("<h1 style='text-align: center; background: linear-gradient(45deg, #4ade80, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>🔍 Deal Finder</h1>", unsafe_allow_html=True)
    st.session_state.is_ai_mode = False
    
    _, _, df = get_global_filters()
    
    search = st.text_input("🔍 Search deals (e.g. 'Coffee', '2kg')...", "")
    
    if not df.empty:
        if search:
            df = df[df['product_name'].str.contains(search, case=False, na=False) | 
                    df['brand'].str.contains(search, case=False, na=False)]
        
        st.success(f"Showing {len(df)} deals")
        render_deal_grid(df)

def analytics_page():
    st.markdown("<h1 style='text-align: center; background: linear-gradient(45deg, #f59e0b, #ef4444); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>📊 Price Analytics</h1>", unsafe_allow_html=True)
    st.session_state.is_ai_mode = False
    
    # Render global filters but capture only the province
    sel_province, _, _ = get_global_filters()
    
    # Reload data for the selected province using ALL available dates (ignoring date filter)
    province_map, date_map = get_available_partitions()
    if not sel_province or not province_map:
        st.warning("Please select a province in the sidebar.")
        return

    national_key = next((k for k in province_map.keys() if k.lower() == 'national'), None)
    national_folders = province_map[national_key] if national_key else []
    target_folders = province_map[sel_province] + national_folders
    
    # Load data for all dates
    df = load_data(target_folders, list(date_map.keys()), date_map)
    
    if df.empty:
        st.warning(f"No data available for {sel_province}.")
        return

    st.info(f"💡 Showing comprehensive analytics for **{sel_province}** across all captured cycles.")

    # --- Top Row: High Level Metrics ---
    m1, m2, m3, m4 = st.columns(4)
    avg_discount = df[df['discount_pct'] > 0]['discount_pct'].mean()
    m1.metric("Avg. Discount", f"{avg_discount:.1f}%")
    m2.metric("Total Deals", len(df))
    m3.metric("Premium Brands", len(df['brand'].unique()))
    max_save = df['discount_pct'].max()
    m4.metric("Max Savings", f"{max_save:.0f}%")

    st.divider()

    # --- Row 1: Brand Analysis ---
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🏆 Dominant Brands")
        brand_counts = df['brand'].value_counts().head(10)
        st.bar_chart(brand_counts, color="#3b82f6")
        st.caption("Brands with the highest number of active specials.")

    with col2:
        st.subheader("💸 Most Aggressive Discounts")
        brand_savings = df[df['discount_pct'] > 0].groupby('brand').agg({'discount_pct': ['mean', 'count']})
        brand_savings.columns = ['avg_discount', 'deal_count']
        brand_savings = brand_savings[brand_savings['deal_count'] >= 2].sort_values('avg_discount', ascending=False).head(10)
        st.bar_chart(brand_savings['avg_discount'], color="#f59e0b")
        st.caption("Brands offering the highest average percentage off (min 2 deals).")

    st.divider()

    # --- Row 2: Price & Expiry ---
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("💰 Pricing Tiers")
        st.area_chart(df[df['current_price'] < 300]['current_price'].value_counts().sort_index(), color="#4ade80")
        st.caption("Concentration of deals by price point (below R300).")
    
    with c2:
        st.subheader("⌛ Deal Expiry Timeline")
        if '_end_dt' in df.columns:
            today = pd.Timestamp.now().normalize()
            # Prepare data for color-coded bar chart
            df_timeline = df.copy()
            df_timeline['Status'] = df_timeline['_end_dt'].apply(lambda x: '🔴 Expired' if x < today else '🟢 Active')
            
            expiry_summary = df_timeline.groupby(['_end_dt', 'Status']).size().reset_index(name='Deals')
            expiry_summary['Date'] = expiry_summary['_end_dt'].dt.strftime('%d %b')
            
            # Show stacked bar chart
            st.bar_chart(expiry_summary, x='Date', y='Deals', color='Status', height=300)
            
            # Detailed list - Filtered for ACTIVE only
            st.write("🏃 **Last Chance: Expiring Soonest**")
            active_soon = df_timeline[df_timeline['_end_dt'] >= today].sort_values('_end_dt').head(5)
            
            if not active_soon.empty:
                active_soon_display = active_soon[['product_name', 'brand', '_end_dt', 'current_price']].copy()
                active_soon_display['_end_dt'] = active_soon_display['_end_dt'].dt.strftime('%d %b')
                st.dataframe(
                    active_soon_display.rename(columns={
                        'product_name': 'Product', 
                        'brand': 'Brand', 
                        '_end_dt': 'Expires', 
                        'current_price': 'Price'
                    }), 
                    hide_index=True, 
                    use_container_width=True
                )
            else:
                st.info("No active deals found in this cycle.")
            st.caption("Timeline shows past (red) and upcoming (green) expiry dates. Table shows top 5 items ending soonest.")

    st.divider()

    # --- Row 3: Deal Depth & Category ---
    ca, cb = st.columns(2)
    with ca:
        st.subheader("📉 Savings Depth")
        bins = [0, 10, 20, 30, 50, 100]
        labels = ['0-10%', '10-20%', '20-30%', '30-50%', '50%+']
        df['savings_tier'] = pd.cut(df['discount_pct'], bins=bins, labels=labels)
        tier_counts = df['savings_tier'].value_counts().sort_index()
        st.bar_chart(tier_counts, color="#8b5cf6")
        st.caption("Distribution of discount intensity.")

    with cb:
        st.subheader("📋 Promo Types")
        if 'deal_type' in df.columns:
            st.bar_chart(df['deal_type'].value_counts(), color="#ec4899")
            st.caption("Breakdown by PnP deal mechanics.")

def ai_smart_list():
    st.markdown("<h1 style='text-align: center; background: linear-gradient(45deg, #8b5cf6, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>🛒 AI Smart List</h1>", unsafe_allow_html=True)
    st.session_state.is_ai_mode = True
    
    # Securely load API Key from Environment
    api_key = os.getenv("GOOGLE_API_KEY")
    sel_province, _, df = get_global_filters()
    
    if not api_key:
        st.error("🔑 **API Key Missing:** The `GOOGLE_API_KEY` environment variable is not set. Please configure it in your deployment environment.")
        return

    if df.empty:
        st.warning("Please load data using the sidebar filters first.")
        return

    client = genai.Client(api_key=api_key)
    
    user_list = st.text_area("What are you looking for?", placeholder="e.g. 'cheap alcohol, fruit, stationery, meat'", height=120)
    
    if st.button("✨ Match Deals with AI"):
        prompt = f"""
        Act as a retail expert. Analyze this shopping list: "{user_list}"
        Expand ambiguous categories into specific supermarket keywords. 
        Example: "alcohol" -> "wine, beer, gin, vodka"
        Return ONLY a comma-separated list of the 10 most relevant keywords.
        """
        
        try:
            with st.spinner("Gemini is searching..."):
                response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                keywords = [k.strip() for k in response.text.split(',')]
                
                matches = []
                for kw in keywords:
                    res = df[df['product_name'].str.contains(kw, case=False, na=False) | 
                             df['brand'].str.contains(kw, case=False, na=False)].head(4)
                    if not res.empty: matches.append(res)
                
                if matches:
                    final_df = pd.concat(matches).drop_duplicates(subset=['product_name', 'current_price'])
                    st.subheader(f"✅ Best Matches in {sel_province}")
                    
                    # Add pro-tips via AI
                    tips = []
                    for _, item in final_df.iterrows():
                        try:
                            ctx_prompt = f"Product: {item['product_name']} at R{item['current_price']:.2f}. Give a 5-word pro-tip."
                            tip = client.models.generate_content(model="gemini-2.5-flash", contents=ctx_prompt).text
                            tips.append(tip)
                        except: tips.append("")
                    
                    final_df['_pro_tip'] = tips
                    render_deal_grid(final_df)

                    # --- New: Holistic Shopping Plan Advice ---
                    st.divider()
                    st.subheader("💡 Gemini's Shopping Strategy")
                    with st.spinner("Analyzing your shopping plan..."):
                        # Extract product names for the holistic prompt
                        items_found = ", ".join(final_df['product_name'].tolist())
                        strategy_prompt = f"""
                        Based on these deals I found: {items_found}.
                        
                        Give me a 'Smart Shopping Strategy' in 3 short bullet points:
                        1. A meal idea or pairing using these items.
                        2. A 'Don't Forget' suggestion (staples usually needed with these).
                        3. A 'Budget Tip' to maximize these specific savings.
                        
                        Be conversational but very concise.
                        """
                        try:
                            strategy_resp = client.models.generate_content(model="gemini-2.5-flash", contents=strategy_prompt)
                            st.info(strategy_resp.text)
                        except:
                            st.write("Could not generate strategy at this time.")
                else:
                    st.warning("No direct matches found.")
        except Exception as e:
            st.error(f"AI Service Error: {e}")

# Apply logic
apply_custom_css()
pg = st.navigation([
    st.Page(deal_finder, title="Deal Finder", icon="🔍"),
    st.Page(analytics_page, title="Price Analytics", icon="📊"),
    st.Page(ai_smart_list, title="AI Smart List", icon="🛒"),
])
pg.run()
