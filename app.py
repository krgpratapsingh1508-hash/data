import streamlit as st
import pandas as pd
import sqlite3
import json

st.set_page_config(layout="wide")

# Database Setup
conn = sqlite3.connect("nep_ug_final_fixed.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS data_store (id INTEGER PRIMARY KEY, js TEXT)")
conn.commit()

# Session States
if "ok" not in st.session_state: st.session_state["ok"] = False
if "hide" not in st.session_state: st.session_state["hide"] = False
if "ug_el" not in st.session_state: st.session_state["ug_el"] = []
if "deleted_cols" not in st.session_state: st.session_state["deleted_cols"] = []

# 1. LOGIN SYSTEM (Admin Password: psv123)
if not st.session_state["ok"]:
    st.title("🔒 Login")
    user = st.selectbox("Username:", ["-- चुनें --", "Admin", "Operator", "Teacher_UG"])
    pas = st.text_input("Password:", type="password")
    if st.button("Login"):
        if (user == "Admin" and pas == "psv123") or (user == "Operator" and pas == "op") or (user == "Teacher_UG" and pas == "ug"):
            st.session_state["ok"] = True
            st.session_state["user"] = user
            st.rerun()
        else: st.error("गलत पासवर्ड!")
    st.stop()

# Role Panels
u = st.session_state["user"]
p_opts = ["📥 Upload"] if u == "Operator" else (["💻 Work"] if "Teacher" in u else ["📥 Upload", "💻 Work", "⚙️ Admin"])
p = st.sidebar.radio("पैनल", p_opts)

def get_db():
    try:
        cursor.execute("SELECT js FROM data_store ORDER BY id DESC LIMIT 1")
        r = cursor.fetchone()
        if r: return pd.read_json(r, orient="split")
    except Exception: return None
    return None

# --- UPLOAD PANEL ---
if p == "📥 Upload":
    st.title("📥 Upload Panel")
    f = st.file_uploader("एक्सेल/CSV फ़ाइल चुनें", type=["csv", "xlsx"])
    if f and st.button("💾 एडमिन डेटाबेस में सेव करें"):
        try:
            df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
            cursor.execute("INSERT INTO data_store (js) VALUES (?)", (df.to_json(orient="split"),))
            conn.commit()
            st.session_state["deleted_cols"] = [] 
            st.success("⚡ डेटा सुरक्षित सेव हो गया!")
        except Exception as e: st.error(f"समस्या: {e}")

# --- WORK PANEL ---
elif p == "💻 Work":
    st.title("💻 Work Panel (UG Data Validation)")
    df = get_db()
    
    if df is None or df.empty:
        st.warning("⚠️ डेटाबेस खाली है। काम शुरू करने के लिए एक्सेल/CSV फ़ाइल सीधे अपलोड करें:")
        direct_file = st.file_uploader("यहाँ फ़ाइल अपलोड करें (Direct Mode):", type=["csv", "xlsx"])
        if direct_file:
            df = pd.read_csv(direct_file) if direct_file.name.endswith('.csv') else pd.read_excel(direct_file)
            st.session_state["deleted_cols"] = []
            st.success("📊 फ़ाइल लोड हो गई!")
            
    if df is not None and not df.empty:
        # आवश्यक कॉलम्स खोजना
        el_col = next((c for c in df.columns if 'elig' in c.lower() or 'qual' in c.lower()), df.columns)
        deg_col = next((c for c in df.columns if 'deg' in c.lower() or 'course' in c.lower()), df.columns)
        br_col = next((c for c in df.columns if 'branch' in c.lower() or 'stream' in c.lower() or 'subject' in c.lower()), df.columns)
        
        minor_col = next((c for c in df.columns if 'minor' in c.lower()), None)
        mdc_col = next((c for c in df.columns if 'mdc' in c.lower()), None)
        voc_col = next((c for c in df.columns if 'voc' in c.lower() or 'skill' in c.lower()), None)
        pw_col = next((c for c in df.columns if 'pw' in c.lower() or 'project' in c.lower() or 'ce' in c.lower()), None)

        u_el = df[el_col].dropna().unique().tolist()
        
        if not st.session_state["hide"]:
            st.subheader("⚙️ स्टेप 1: एलिजिबिलिटी सेट करें")
            st.session_state["ug_el"] = st.multiselect("🎓 UNDERGRADUATE (UG) एलिजिबिलिटी चुनें:", u_el, default=st.session_state["ug_el"])
            if st.button("🔒 लॉक करें और सेटअप छुपाएं") and st.session_state["ug_el"]:
                st.session_state["hide"] = True
                st.rerun()
        else:
            if st.button("🔓 एलिजिबिलिटी नियम दोबारा बदलें"):
                st.session_state["hide"] = False
                st.rerun()

        if st.session_state["hide"]:
            # 1. एलिजिबिलिटी फ़िल्टर
            df_ug = df[df[el_col].isin(st.session_state["ug_el"])].reset_index(drop=True)
            
            # 🎯 2. आपकी बताई हुई 4 डिग्रियों के लिए बिल्कुल सटीक फ़िल्टर (Case Insensitive & Dot-Space Cleaned)
            def filter_strict_ug_exact(val):
                # नाम को साफ करना (स्पेस और डॉट हटाकर स्मॉल लेटर में बदलना)
                v = str(val).lower().replace(".", "").replace(" ", "").strip()
                
                # सटीक मिलान: bcom, ba, bhsc, bsc
                if v in ["bcom", "ba", "bhsc", "bsc"]:
                    return True
                return False
                
            df_ug = df_ug[df_ug[deg_col].apply(filter_strict_ug_exact)].reset_index(drop=True)
            
            if df_ug.empty:
                st.error("⚠️ चुनी गई एलिजिबिलिटी में निर्दिष्ट UG डिग्रियां (B. Com., B. A., B. H. Sc., B. Sc.) नहीं मिलीं।")
            else:
                # 3. परमानेंट कॉलम डिलीट फीचर
                st.subheader("🗑️ बेकार कॉलम हटाएं (Remove Columns)")
                
                remaining_cols = [c for c in df_ug.columns if c not in st.session_state["deleted_cols"]]
                df_ug = df_ug[remaining_cols]
                
                cols_to_delete = st.multiselect("हटाने वाले कॉलम स्क्रॉल लिस्ट से चुनें:", options=remaining_cols)
                
                if cols_to_delete:
                    if st.button("🔴 चुने गए कॉलम हमेशा के लिए डिलीट करें"):
                        st.session_state["deleted_cols"].extend(cols_to_delete)
                        st.success(f"कॉलम डिलीट कर दिए गए!")
                        st.rerun()
                
                # कॉम्बिनेशन बनाना
                df_ug['combo'] = df_ug[deg_col].astype(str) + " - " + df_ug[br_col].astype(str)
                u_combos = df_ug['combo'].unique().tolist()
                
                st.divider()
                st.subheader("📋 2. डिग्री + ब्रांच के अनुसार मान्य (Valid) विषय सेट करें")
                rules = {}
                
                opt_minor = df_ug[minor_col].dropna().unique().tolist() if (minor_col and minor_col in df_ug.columns) else []
                opt_mdc = df_ug[mdc_col].dropna().unique().tolist() if (mdc_col and mdc_col in df_ug.columns) else []
                opt_voc = df_ug[voc_col].dropna().unique().tolist() if (voc_col and voc_col in df_ug.columns) else []
                opt_pw = df_ug[pw_col].dropna().unique().tolist() if (pw_col and pw_col in df_ug.columns) else []
                
                grid = st.columns(2)
                for idx, combo in enumerate(u_combos):
                    with grid[idx % 2]:
                        st.info(f"📍 **{combo}**")
                        r_minor = st.multiselect(f"Minor for {combo}", opt_minor, key=f"mi_{idx}")
                        r_mdc = st.multiselect(f"MDC for {combo}", opt_mdc, key=f"mdc_{idx}")
                        r_voc = st.multiselect(f"Vocational for {combo}", opt_voc, key=f"voc_{idx}")
                        r_pw = st.multiselect(f"PW/Ap/CE for {combo}", opt_pw, key=f"pw_{idx}")
                        
                        rules[combo] = {
                            "minor": {str(x).strip().lower() for x in r_minor},
                            "mdc": {str(x).strip().lower() for x in r_mdc},
                            "voc": {str(x).strip().lower() for x in r_voc},
                            "pw": {str(x).strip().lower() for x in r_pw}
                        }

                def cell_styler(dataframe):
                    s_df = pd.DataFrame('', index=dataframe.index, columns=dataframe.columns)
                    targets = {minor_col: 'minor', mdc_col: 'mdc', voc_col: 'voc', pw_col: 'pw'}
                    
                    for index, row in dataframe.iterrows():
                        c_val = str(row[deg_col]) + " - " + str(row[br_col])
                        c_rule = rules.get(c_val, {"minor":set(), "mdc":set(), "voc":set(), "pw":set()})
                        
                        for col_name, rule_key in targets.items():
                            if col_name and col_name in dataframe.columns:
                                val = row[col_name]
                                if pd.isna(val) or str(val).strip() == "":
                                    s_df.at[index, col_name] = 'background-color: #d1ecf1; color: #0c5460; font-weight: bold;'
                                elif c_rule[rule_key] and str(val).strip().lower() not in c_rule[rule_key]:
                                    s_df.at[index, col_name] = 'background-color: #f8d7da; color: #721c24; font-weight: bold; border: 1px solid red;'
                    return s_df

                st.divider()
                st.subheader("📊 3. लाइव वैरिफाइड UG डेटा टेबल")
                display_df = df_ug.drop(columns=['combo'])
                st.dataframe(display_df.style.apply(cell_styler, axis=None), height=600, use_container_width=True)

# --- ADMIN PANEL ---
elif p == "⚙️ Admin":
    st.title("⚙️ Admin Control")
    df = get_db()
    if df is not None: st.write(f"डेटाबेस में कुल सुरक्षित रिकॉर्ड्स: {len(df)}")
    del_p = st.text_input("डेटा डिलीट करने के लिए पासवर्ड डालें:", type="password")
    if del_p == "psv123" and st.button("🔴 मास्टर डेटाबेस साफ करें"):
        cursor.execute("DELETE FROM data_store")
        conn.commit()
        st.session_state["deleted_cols"] = []
        st.success("डेटाबेस पूरी तरह साफ़ कर दिया गया है!")
        st.rerun()
