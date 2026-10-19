import streamlit as st

def apply():
    st.markdown('''<style>
    
    :root{--ink:#172c2a;--muted:#768580;--green:#246b50}
    .stApp{background:#f6f7f3;color:var(--ink);font-family:'Segoe UI',sans-serif}
    h1,h2,h3{font-family:Segoe UI,sans-serif!important;letter-spacing:-.045em!important;color:var(--ink)}
    .block-container{padding-top:2.6rem;max-width:1500px;padding-bottom:4rem}
    [data-testid="stSidebar"]{color:#172c2a;background:#eaf0e8;border-right:1px solid #dbe2d8}
    [data-testid="stSidebar"] .block-container{padding-top:2rem}
    .stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"]{background:#246b50;border-color:#246b50;border-radius:9px}
    .stButton>button,.stDownloadButton>button{border-radius:9px;font-weight:600}
    [data-testid="stMetric"]{background:white;border:1px solid #e0e6dd;border-radius:14px;padding:18px 22px}
    [data-testid="stMetricLabel"]{color:#768580;font-size:12px;text-transform:uppercase;letter-spacing:.07em}
    [data-testid="stMetricValue"]{color:#172c2a;font-family:Segoe UI,sans-serif;font-weight:700;font-size:30px}
    .stTabs [data-baseweb="tab-list"]{gap:24px;border-bottom:1px solid #dce3d9}
    .stTabs [aria-selected="true"]{color:#246b50!important}
    .stTabs [data-baseweb="tab-highlight"]{background:#246b50}
    .brand{font-family:Segoe UI;font-size:25px;font-weight:800;letter-spacing:-1px;margin-bottom:5px}
    .eyebrow{font-size:11px;color:#6c8475;text-transform:uppercase;letter-spacing:2px;font-weight:700}
    .hero{background:#e6edde;border:1px solid #d6e1cd;border-radius:18px;padding:30px 34px;margin:20px 0 26px;position:relative}
    .hero h2{font-size:32px;margin:8px 0 10px;padding:0;max-width:640px}
    .hero p{color:#5a7062;max-width:630px;line-height:1.6;margin:0}
    .tag{display:inline-block;background:#f8fbf4;border:1px solid #d6e1cd;border-radius:20px;padding:5px 12px;font-size:11px;color:#43664a;margin-bottom:7px}
    .preview{background:#142e2a;border-radius:16px;min-height:285px;padding:32px;color:white;margin-bottom:18px;box-shadow:0 12px 30px #19382b12}
    .preview h3{color:#edf5dc!important;font-size:28px;margin:26px 0 18px}
    .preview p{color:#c5d4c9;font-size:16px;line-height:1.7}
    .preview small{color:#a5c591;letter-spacing:2px;text-transform:uppercase}
    .note{color:#7a867c;font-size:12px;line-height:1.6}
    [data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] .brand{color:#172c2a!important} header[data-testid="stHeader"]{background:#f6f7f3!important} </style>''', unsafe_allow_html=True)
    
