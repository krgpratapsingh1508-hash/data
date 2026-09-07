import streamlit as st
import pandas as pd
import sqlite3
import json

# Page configuration
st.set_page_config(page_title="NEP Data Validator Pro", layout="wide")

# Database initialization
conn = sqlite3.connect("nep_app_database.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS uploaded_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_json TEXT,
        course_type TEXT
    )
""")
conn.commit()

# --- 1. LOGIN SYSTEM WITH EASY PASSWORDS ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["current_user"] = ""

if not st.session_state["logged_in"]:
    st.title("🔒 Login System")
    users_list = ["-- यूज़र चुनें --", "Admin", "Teacher_UG", "Teacher_PG", "Operator"]
    
    with st.form("login_form"):
        username = st.selectbox("अपना Username चुनें:", options=users_list)
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if username == "-- यूज़र चुनें --":
                st.error("कृपया स्क्रॉल लिस्ट से अपना नाम चुनें!")
            else:
                is_valid = False
                input_pass = str(password).strip().lower()
                
                if username == "Admin" and input_pass == "admin":
                    is_valid = True
                elif username == "Teacher_UG" and input_pass == "ug":
                    is_valid = True
                elif username == "Teacher_PG" and input_pass == "pg":
                    is_valid = True
                elif username == "Operator" and input_pass == "op":
                    is_valid = True
                
                if is_valid:
                    st.session_state["logged_in"] = True
                    st.session_state["current_user"] = username
                    st.success(f"स्वागत है, {username}!")
                    st.rerun()
                else:
                    st.error(f"❌ '{username}' के लिए गलत पासवर्ड डाला है!")
    st.stop()

# --- LOGOUT & USER INFO ---
st.sidebar.markdown(f"👤 **Logged in as:** `{st.session_state['current_user']}`")
if st.sidebar.button("Logout 🏃‍♂️"):
    st.session_state["logged_in"] = False
    st.session_state["current_user"] = ""
    st.rerun()

# --- 2. PANEL NAVIGATION ---
panel = st.sidebar.radio("पैनल चुनें (Select Panel)", ["📥 Entry Panel (डेटा अपलोड)", "💻 Work Panel (नियम और वैलिडेशन)"])

def load_db_data():
    cursor.execute("SELECT data_json, course_type FROM uploaded_data")
    rows = cursor.fetchall()
    if rows:
        dfs = []
        for r in rows:
            temp_df = pd.DataFrame(json.loads(r[0]))
            temp_df['Course_Category'] = r[1]
            dfs.append(temp_df)
        return pd.concat(dfs, ignore_index=True)
    return None

# --- PANEL 1: ENTRY PANEL ---
if panel == "📥 Entry Panel (डेटा अपलोड)":
    st.title("📥 Entry Panel - एक्सेल/CSV डेटाबेस")
    
    current_data = load_db_data()
    if current_data is not None:
        st.warning(f"⚠️ डेटाबेस में पहले से {len(current_data)} रोज़ का डेटा मौजूद है।")
        if st.button("🗑️ पुराना सारा डेटा डिलीट करें"):
            cursor.execute("DELETE FROM uploaded_data")
            conn.commit()
            st.success("डेटाबेस खाली कर दिया गया है!")
            st.rerun()
            
    uploaded_file = st.file_uploader("अपनी मुख्य डेटा लिस्ट अपलोड करें", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                
            st.subheader("📋 अपलोडेड डेटा प्रीव्यू:")
            st.dataframe(df.head(10))
            
            st.divider()
            st.subheader("UG / PG विभाजन सेटिंग्स")
            selected_col = st.selectbox("कोर्स/डिग्री वाला कॉलम चुनें (जैसे Degree या Course):", df.columns)
            
            ug_keywords = st.text_input("UG के कीवर्ड्स (कमा से अलग करें)", "BA, BSC, BCOM, BTECH, UG")
            pg_keywords = st.text_input("PG के कीवर्ड्स (कमा से अलग करें)", "MA, MSC, MCOM, MTECH, PG")
            
            if st.button("💾 डेटाबेस में सुरक्षित करें"):
                ug_list = [x.strip().lower() for x in ug_keywords.split(",")]
                pg_list = [x.strip().lower() for x in pg_keywords.split(",")]
                
                ug_rows, pg_rows = [], []
                
                for _, row in df.iterrows():
                    val = str(row[selected_col]).lower()
                    is_pg = any(kw in val for kw in pg_list)
                    is_ug = any(kw in val for kw in ug_list)
                    
                    row_dict = row.to_dict()
                    if is_pg:
                        pg_rows.append(row_dict)
                    else:
                        ug_rows.append(row_dict)
                
                if ug_rows:
                    cursor.execute("INSERT INTO uploaded_data (data_json, course_type) VALUES (?, ?)", (json.dumps(ug_rows), "UG"))
                if pg_rows:
                    cursor.execute("INSERT INTO uploaded_data (data_json, course_type) VALUES (?, ?)", (json.dumps(pg_rows), "PG"))
                conn.commit()
                
                st.success(f"🎉 डेटा सेव हो गया! (UG: {len(ug_rows)} रोज़, PG: {len(pg_rows)} रोज़)")
                st.balloons()
        except Exception as e:
            st.error(f"त्रुटि: {e}")

# --- PANEL 2: WORK PANEL ---
elif panel == "💻 Work Panel (नियम और वैलिडेशन)":
    st.title("💻 Work Panel - विषय मिलान और वैलिडेशन")
    
    full_df = load_db_data()
    
    if full_df is None:
        st.info("ℹ️ डेटाबेस खाली है। कृपया पहले 'Entry Panel' में जाकर फ़ाइल अपलोड करें।")
    else:
        tab_ug, tab_pg = st.tabs(["🎓 UNDERGRADUATE (UG) PANEL", "📜 POSTGRADUATE (PG) PANEL"])
        
        df_ug = full_df[full_df['Course_Category'] == 'UG'].drop(columns=['Course_Category']).reset_index(drop=True)
        df_pg = full_df[full_df['Course_Category'] == 'PG'].drop(columns=['Course_Category']).reset_index(drop=True)
        
        # --- फंक्शन: डेटा वैलिडेशन और कलर कोडिंग ---
        def process_validation(df_panel, prefix):
            st.subheader("⚙️ नियम सेट करें (Define Rules)")
            st.write("चुनें कि किस Degree + Branch के लिए कौन-से सब्जेक्ट्स वैध (Valid) हैं:")
            
            col_deg = st.selectbox("Degree कॉलम चुनें:", df_panel.columns, key=f"{prefix}_c1")
            col_br = st.selectbox("Branch/Subject कॉलम चुनें:", df_panel.columns, key=f"{prefix}_c2")
            
            col_minor = st.selectbox("Minor Subject कॉलम चुनें:", df_panel.columns, key=f"{prefix}_m")
            col_mdc = st.selectbox("MDC Subject कॉलम चुनें:", df_panel.columns, key=f"{prefix}_md")
            col_voc = st.selectbox("Vocational Subject कॉलम चुनें:", df_panel.columns, key=f"{prefix}_v")
            col_pw = st.selectbox("PW/Ap/CE Subject कॉलम चुनें:", df_panel.columns, key=f"{prefix}_p")
            
            # यूनिक कॉम्बिनेशन ढूंढना (जैसे B.Sc + Mathematics)
            df_panel['combo'] = df_panel[col_deg].astype(str) + " - " + df_panel[col_br].astype(str)
            unique_combos = df_panel['combo'].unique().tolist()
            
            rules = {}
            st.markdown("#### हर डिग्रियों के लिए मान्य सब्जेक्ट्स की स्क्रॉल लिस्ट:")
            
            with st.expander("👉 यहाँ क्लिक करके डिग्रियों के नियम सेट करें", expanded=True):
                grid = st.columns(2)
                for i, combo in enumerate(unique_combos):
                    with grid[i % 2]:
                        st.info(f"📍 **{combo}** के लिए नियम:")
                        
                        # हर कैटेगरी के लिए उपलब्ध यूनिक सब्जेक्ट्स की लिस्ट स्क्रॉल के लिए
                        all_minors = df_panel[col_minor].dropna().unique().tolist()
                        all_mdcs = df_panel[col_mdc].dropna().unique().tolist()
                        all_vocs = df_panel[col_voc].dropna().unique().tolist()
                        all_pws = df_panel[col_pw].dropna().unique().tolist()
                        
                        r_minor = st.multiselect(f"Valid Minor Subjects", options=all_minors, key=f"{prefix}_rm_{i}")
                        r_mdc = st.multiselect(f"Valid MDC Subjects", options=all_mdcs, key=f"{prefix}_rmdc_{i}")
                        r_voc = st.multiselect(f"Valid Vocational", options=all_vocs, key=f"{prefix}_rvoc_{i}")
                        r_pw = st.multiselect(f"Valid PW/Ap/CE", options=all_pws, key=f"{prefix}_rpw_{i}")
                        
                        rules[combo] = {
                            "minor": [str(x).strip().lower() for x in r_minor],
                            "mdc": [str(x).strip().lower() for x in r_mdc],
                            "voc": [str(x).strip().lower() for x in r_voc],
                            "pw": [str(x).strip().lower() for x in r_pw]
                        }
            
            # सेल हाइलाइटिंग लॉजिक (Red for Wrong, Blue for Blank)
            def cell_styler(dataframe):
                style_df = pd.DataFrame('', index=dataframe.index, columns=dataframe.columns)
                target_cols = {col_minor: 'minor', col_mdc: 'mdc', col_voc: 'voc', col_pw: 'pw'}
                
                for index, row in dataframe.iterrows():
                    combo_val = str(row[col_deg]) + " - " + str(row[col_br])
                    current_rule = rules.get(combo_val, {"minor":[], "mdc":[], "voc":[], "pw":[]})
                    
                    for col_name, rule_key in target_cols.items():
                        cell_val = row[col_name]
                        
                        # --- यहाँ से आपका कोड शुरू होता है ---
                        # 1. अगर सेल खाली (Blank) है तो ब्लू कलर दें
                        if pd.isna(cell_val) or str(cell_val).strip() == "":
                            style_df.at[index, col_name] = 'background-color: #d1ecf1; color: #0c5460; font-weight: bold; border: 1px solid #17a2b8;'
                        else:
                            # 2. अगर भरा हुआ है लेकिन नियमों से मैच नहीं करता तो रेड कलर दें
                            valid_list = current_rule[rule_key]
                            if valid_list and str(cell_val).strip().lower() not in valid_list:
                                style_df.at[index, col_name] = 'background-color: #f8d7da; color: #721c24; font-weight: bold; border: 2px solid red;'
                return style_df
            
            st.divider()
            st.subheader("📊 लाइव वैरिफाइड डेटा टेबल:")
            st.caption("🔵 नीला सेल = डेटा गायब (Blank) | 🔴 लाल सेल = गलत विषय (Mismatch Subject)")
            
            # टेम्परेरी कॉम्बिनेशन कॉलम को हटाकर टेबल दिखाना
            display_df = df_panel.drop(columns=['combo'])
            
            # लाइव हाइलाइटेड डेटा टेबल स्क्रीन पर लोड करना
            st.dataframe(
                display_df.style.apply(cell_styler, axis=None), 
                height=600, 
                use_container_width=True
            )
            
            # --- बोनस: गलत डेटा की समरी रिपोर्ट ---
            error_count = 0
            for index, row in df_panel.iterrows():
                combo_val = str(row[col_deg]) + " - " + str(row[col_br])
                current_rule = rules.get(combo_val, {"minor":[], "mdc":[], "voc":[], "pw":[]})
                for col_name, rule_key in {col_minor: 'minor', col_mdc: 'mdc', col_voc: 'voc', col_pw: 'pw'}.items():
                    cell_val = row[col_name]
                    if pd.isna(cell_val) or str(cell_val).strip() == "":
                        error_count += 1
                    elif current_rule[rule_key] and str(cell_val).strip().lower() not in current_rule[rule_key]:
                        error_count += 1
            
            if error_count > 0:
                st.warning(f"⚠️ इस शीट में कुल {error_count} जगह पर गलतियाँ (लाल/नीले सेल्स) मिली हैं।")
            else:
                st.success("🎉 बहुत बढ़िया! चुने गए नियमों के अनुसार सारा डेटा बिल्कुल सही है।")
