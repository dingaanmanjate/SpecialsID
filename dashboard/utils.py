import streamlit as st
import awswrangler as wr
import pandas as pd
import boto3
import re

BUCKET_NAME = "special-id-data-0129"
DATA_PREFIX = "data/clean/PnP/"

def normalize_date_label(folder_name):
    """Deep normalization for messy date strings."""
    val = folder_name.split('=')[-1]
    val = re.sub(r'[_\-\s]+', ' ', val)
    val = re.sub(r'(\d+ [A-Za-z]+) (\d+ [A-Za-z]+)', r'\1 - \2', val)
    val = re.sub(r'([a-zA-Z]+)(\d{4})', r'\1 \2', val)
    return val.strip()

def parse_dates(label):
    """Attempts to extract start and end dates from a label."""
    try:
        parts = label.split(' - ')
        if len(parts) != 2: return None, None
        year_match = re.search(r'\d{4}', parts[1])
        year = year_match.group() if year_match else "2026"
        end_str = parts[1] if year_match else f"{parts[1]} {year}"
        start_str = parts[0] if re.search(r'\d{4}', parts[0]) else f"{parts[0]} {year}"
        return pd.to_datetime(start_str), pd.to_datetime(end_str)
    except: return None, None

@st.cache_data(ttl=3600)
def get_available_partitions():
    try:
        s3 = boto3.client("s3")
        paginator = s3.get_paginator("list_objects_v2")
        raw_provinces = []
        for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=DATA_PREFIX, Delimiter='/'):
            if 'CommonPrefixes' in page:
                raw_provinces.extend([p['Prefix'].split('/')[-2] for p in page['CommonPrefixes']])
        
        province_map = {}
        for p in set(raw_provinces):
            label = p.split('=')[-1].replace('_', ' ').strip()
            if label:
                if label not in province_map: province_map[label] = []
                province_map[label].append(p)
        
        all_date_folders = set()
        for p_folder in set(raw_provinces):
            d_paginator = s3.get_paginator("list_objects_v2")
            for page in d_paginator.paginate(Bucket=BUCKET_NAME, Prefix=f"{DATA_PREFIX}{p_folder}/", Delimiter='/'):
                if 'CommonPrefixes' in page:
                    for d in page['CommonPrefixes']:
                        all_date_folders.add(d['Prefix'].split('/')[-2])
        
        date_map = {}
        for d in sorted(all_date_folders):
            label = normalize_date_label(d)
            if label not in date_map: date_map[label] = []
            date_map[label].append(d)
        return province_map, date_map
    except Exception as e:
        st.error(f"S3 Connection Error: {e}")
        return {}, {}

@st.cache_data(ttl=600)
def load_data(province_folders, date_range_labels, date_map):
    all_dfs = []
    session = boto3.Session()
    for p_folder in province_folders:
        is_national = 'national' in p_folder.lower()
        for label in date_range_labels:
            d_folders = date_map.get(label, [])
            for d_folder in d_folders:
                path = f"s3://{BUCKET_NAME}/{DATA_PREFIX}{p_folder}/{d_folder}/"
                try:
                    df = wr.s3.read_parquet(path=path, dataset=True, boto3_session=session)
                    if not df.empty:
                        df['_origin'] = 'National' if is_national else 'Province'
                        df['_date_range'] = label
                        start, end = parse_dates(label)
                        df['_start_dt'] = start
                        df['_end_dt'] = end
                        all_dfs.append(df)
                except: continue
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        # Add a calculated discount field for analytics
        if 'was_price' in combined.columns and 'current_price' in combined.columns:
            combined['discount_pct'] = ((combined['was_price'] - combined['current_price']) / combined['was_price'] * 100).fillna(0)
        return combined.drop_duplicates(subset=['product_name', 'current_price', 'brand', '_date_range'])
    return pd.DataFrame()

def apply_custom_css():
    st.markdown("""
        <style>
        /* Card styling that works in both modes */
        .deal-card {
            padding: 1.5rem;
            border-radius: 16px;
            border: 1px solid rgba(128, 128, 128, 0.2);
            margin-bottom: 1.5rem;
            position: relative;
            min-height: 260px;
            display: flex;
            flex-direction: column;
            background-color: rgba(128, 128, 128, 0.05);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .deal-card:hover { 
            border-color: #4ade80; 
            transform: translateY(-2px);
            background-color: rgba(74, 222, 128, 0.05);
        }
        .origin-badge {
            position: absolute;
            top: 12px;
            right: 12px;
            font-size: 0.65rem;
            padding: 3px 10px;
            border-radius: 20px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .badge-national { background-color: #3b82f6; color: white; }
        .badge-province { background-color: #8b5cf6; color: white; }
        
        .date-range-label {
            font-size: 0.7rem;
            opacity: 0.7;
            margin-bottom: 8px;
        }
        .brand-tag {
            font-size: 0.75rem;
            font-weight: 700;
            color: #4ade80;
            margin-bottom: 8px;
        }
        .product-name {
            font-size: 1.1rem;
            font-weight: 600;
            margin: 10px 0;
            line-height: 1.3;
            flex-grow: 1;
        }
        .price-container { 
            display: flex; 
            align-items: baseline; 
            gap: 10px; 
            margin-top: auto;
        }
        .price-tag { 
            font-size: 1.5rem; 
            font-weight: 800; 
            color: #4ade80; 
        }
        .was-price { 
            font-size: 0.9rem; 
            text-decoration: line-through; 
            opacity: 0.5;
        }
        .discount-badge { 
            color: #f59e0b; 
            font-size: 0.8rem; 
            font-weight: 700; 
        }
        .meta-info { 
            font-size: 0.8rem; 
            opacity: 0.6; 
            border-top: 1px solid rgba(128, 128, 128, 0.1); 
            padding-top: 8px; 
            margin-top: 12px; 
        }
        </style>
    """, unsafe_allow_html=True)
