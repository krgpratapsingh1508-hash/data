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
            
            # 🎯 2. केवल 4 मुख्य डिग्रियों (BA, BCOM, BHSC, BSC) को रखने का सटीक फ़िल्टर
            def filter_strict_ug_exact(val):
                v = str(val).lower().replace(".", "").replace(" ", "").strip()
                if v in ["bcom", "ba", "bhsc", "bsc"]:
                    return True
                return False
                
            df_ug = df_ug[df_ug[deg_col].apply(filter_strict_ug_exact)].reset_index(drop=True)
            
            if df_ug.empty:
                st.error("⚠️ चुनी गई एलिजिबिलिटी में निर्दिष्ट 4 UG डिग्रियां (B. A., B. Com., B. H. Sc., B. Sc.) नहीं मिलीं।")
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
                
                # 🎯 4. स्मार्ट तरीके से हाइफन (-) के बाद से ऑटोमैटिक माइनर सब्जेक्ट निकालना
                def extract_auto_minor(row):
                    branch_val = str(row[br_col])
                    if "-" in branch_val:
                        # हाइफन के बाद वाले हिस्से को निकालकर साफ करना
                        return branch_val.split("-")[1].strip()
                    return ""
                
                # केवल दिखाने के लिए डिग्रियों के यूनिक नाम (BA, B.Sc. आदि)
                unique_degrees_present = df_ug[deg_col].dropna().unique().tolist()
                
                st.divider()
                st.subheader("📋 2. डिग्री के अनुसार मान्य (Valid) विषय सेट करें")
                st.caption("💡 नोट: सिस्टम ऑटोमैटिकली आपके 'Branch' कॉलम में हाइफन (-) के बाद लिखे विषय को सही माइनर मान रहा है।")
                
                rules = {}
                # सभी संभावित माइनर सब्जेक्ट्स की लिस्ट (जो हाइफन के बाद मौजूद हैं)
                auto_minor_options = df_ug.apply(extract_auto_minor, axis=1).unique().tolist()
                auto_minor_options = [x for x in auto_minor_options if x != ""]
                
                # अन्य कॉलम के लिए उपलब्ध विकल्प
                opt_mdc = df_ug[mdc_col].dropna().unique().tolist() if (mdc_col and mdc_col in df_ug.columns) else []
                opt_voc = df_ug[voc_col].dropna().unique().tolist() if (voc_col and voc_col in df_ug.columns) else []
                opt_pw = df_ug[pw_col].dropna().unique().tolist() if (pw_col and pw_col in df_ug.columns) else []
                
                # 🎯 केवल इन 4 डिग्रियों के लिए ही डिब्बे (Boxes) स्क्रीन पर बनेंगे
                grid = st.columns(2)
                for idx, deg_name in enumerate(unique_degrees_present):
                    with grid[idx % 2]:
                        st.info(f"🎓 **{deg_name}** के लिए मान्य विषय नियम:")
                        
                        # माइनर सब्जेक्ट के लिए हाइफन से निकली लिस्ट का स्क्रॉल
                        r_minor = st.multiselect(f"Valid Minors for {deg_name}", auto_minor_options, key=f"mi_{idx}")
                        r_mdc = st.multiselect(f"Valid MDCs for {deg_name}", opt_mdc, key=f"mdc_{idx}")
                        r_voc = st.multiselect(f"Valid Vocational for {deg_name}", opt_voc, key=f"voc_{idx}")
                        r_pw = st.multiselect(f"Valid PW/Ap/CE for {deg_name}", opt_pw, key=f"pw_{idx}")
                        
                        rules[str(deg_name).strip().lower()] = {
                            "minor": {str(x).strip().lower() for x in r_minor},
                            "mdc": {str(x).strip().lower() for x in r_mdc},
                            "voc": {str(x).strip().lower() for x in r_voc},
                            "pw": {str(x).strip().lower() for x in r_pw}
                        }

                # 5. लाइव हाइलाइटेड डेटा टेबल लॉजिक (स्मार्ट हाइफन मैचिंग के साथ)
                def cell_styler(dataframe):
                    s_df = pd.DataFrame('', index=dataframe.index, columns=dataframe.columns)
                    targets = {minor_col: 'minor', mdc_col: 'mdc', voc_col: 'voc', pw_col: 'pw'}
                    
                    for index, row in dataframe.iterrows():
                        d_val = str(row[deg_col]).strip().lower()
                        c_rule = rules.get(d_val, {"minor":set(), "mdc":set(), "voc":set(), "pw":set()})
                        
                        for col_name, rule_key in targets.items():
                            if col_name and col_name in dataframe.columns:
                                val = row[col_name]
                                
                                # खाली सेल = नीला (Blue)
                                if pd.isna(val) or str(val).strip() == "":
                                    s_df.at[index, col_name] = 'background-color: #d1ecf1; color: #0c5460; font-weight: bold; border: 1px solid #17a2b8;'
                                else:
                                    val_clean = str(val).strip().lower()
                                                                        # --- यहाँ से आपका कोड शुरू होता है ---
                                    valid_set = c_rule[rule_key]
                                    
                                    # अगर नियम सेट किए गए हैं और वैल्यू मैच नहीं करती तो लाल (Red)
                                    if valid_set and val_clean not in valid_set:
                                        s_df.at[index, col_name] = 'background-color: #f8d7da; color: #721c24; font-weight: bold; border: 2px solid red;'
                    return s_df

                st.divider()
                st.subheader("📊 3. लाइव वैरिफाइड UG डेटा टेबल")
                st.caption("🔵 नीला सेल = डेटा गायब है | 🔴 लाल सेल = विषय नियमों से मैच नहीं है")
                
                # टेम्परेरी कॉम्बिनेशन वाले कॉलम (अगर बना हो) को हटाकर साफ टेबल दिखाना
                if 'combo' in df_ug.columns:
                    display_df = df_ug.drop(columns=['combo'])
                else:
                    display_df = df_ug.copy()
                    
                # लाइव हाइलाइटेड डेटा टेबल को स्क्रीन पर लोड करना
                st.dataframe(
                    display_df.style.apply(cell_styler, axis=None), 
                    height=600, 
                    use_container_width=True
                )
                
                # --- गलतियों का लाइव समरी काउंटर ---
                total_errors = 0
                for index, row in df_ug.iterrows():
                    d_val = str(row[deg_col]).strip().lower()
                    c_rule = rules.get(d_val, {"minor":set(), "mdc":set(), "voc":set(), "pw":set()})
                    for col_name, rule_key in targets.items():
                        if col_name and col_name in df_ug.columns:
                            val = row[col_name]
                            if pd.isna(val) or str(val).strip() == "":
                                total_errors += 1
                            elif c_rule[rule_key] and str(val).strip().lower() not in c_rule[rule_key]:
                                total_errors += 1
                                
                if total_errors > 0:
                    st.error(f"🚨 ध्यान दें: इस शीट में कुल {total_errors} सेल्स नियमों के खिलाफ (या खाली) मिले हैं!")
                else:
                    st.success("🎉 बहुत बढ़िया! आपके सेट किए गए नियमों के अनुसार सारा डेटा बिल्कुल सही है।")

                                    
