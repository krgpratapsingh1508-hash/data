import streamlit as st
import pandas as pd
import sqlite3
import json

# Page configuration
st.set_page_config(page_title="Data Manager Pro", layout="wide")

# Database initialization
conn = sqlite3.connect("app_database.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS uploaded_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_json TEXT,
        course_type TEXT
    )
""")
conn.commit()

# ==========================================
# पुराने कोड में यहाँ से बदलाव करें
# ==========================================

# --- 1. LOGIN SYSTEM ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["current_user"] = ""

if not st.session_state["logged_in"]:
    st.title("🔒 Login System")
    
    # 📝 यहाँ आप जितने चाहें उतने नाम जोड़ सकते हैं, ये स्क्रॉल लिस्ट में दिखेंगे
    users_list = ["-- यूज़र चुनें --", "Admin", "Teacher_UG", "Teacher_PG", "Operator"]
    
    with st.form("login_form"):
        # 🎯 यूज़रनेम इनपुट को स्क्रॉल लिस्ट (Dropdown) बना दिया गया है
        username = st.selectbox("अपना Username चुनें:", options=users_list)
        
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if username == "-- यूज़र चुनें --":
                st.error("कृपया स्क्रॉल लिस्ट से अपना नाम चुनें!")
            else:
                # 🔑 सुरक्षा नियम: नाम कोई भी हो, पासवर्ड 'admin123' होना चाहिए
                if password == "admin123":
                    st.session_state["logged_in"] = True
                    st.session_state["current_user"] = username
                    st.success(f"स्वागत है, {username}!")
                    st.rerun()
                else:
                    st.error("गलत पासवर्ड! कृपया सही पासवर्ड डालें।")
    st.stop()

# --- LOGOUT & USER INFO (साइडबार में नाम दिखाने के लिए) ---
st.sidebar.markdown(f"👤 **Logged in as:** `{st.session_state['current_user']}`")
if st.sidebar.button("Logout 🏃‍♂️"):
    st.session_state["logged_in"] = False
    st.session_state["current_user"] = ""
    st.rerun()

# ==========================================
# इसके नीचे आपका पुराना PANEL NAVIGATION वाला कोड वैसे ही रहेगा
# ==========================================
# --- 2. PANEL NAVIGATION ---
panel = st.sidebar.radio("पैनल चुनें (Select Panel)", ["📥 Entry Panel (डेटा अपलोड)", "💻 Work Panel (गलती चेकिंग)"])

# Helper function to check if database has data
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
    st.title("📥 Entry Panel - डेटा अपलोड और सेव करें")
    st.write("यहाँ अपनी एक्सेल/CSV फ़ाइल पेस्ट या अपलोड करें। यह डेटाबेस में तब तक सेव रहेगा जब तक आप डिलीट नहीं करेंगे।")
    
    # Check if data already exists
    current_data = load_db_data()
    if current_data is not None:
        st.warning(f"⚠️ डेटाबेस में पहले से {len(current_data)} रोज़ (Rows) का डेटा सुरक्षित है।")
        if st.button("🗑️ पुराना सारा डेटा डिलीट करें"):
            cursor.execute("DELETE FROM uploaded_data")
            conn.commit()
            st.success("डेटाबेस खाली कर दिया गया है!")
            st.rerun()
            
    uploaded_file = st.file_uploader("अपनी फ़ाइल अपलोड करें (इसमें 'Course' या 'Degree' का कॉलम होना चाहिए ताकि UG/PG अलग हो सके)", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                
            st.subheader("📋 अपलोड किया गया डेटा प्रीव्यू:")
            st.dataframe(df.head(10))
            
            # ऑटोमैटिक UG/PG डिटेक्ट करने की कोशिश (अगर कॉलम है तो, नहीं तो यूजर से पूछेंगे)
            course_col = None
            for col in df.columns:
                if 'course' in col.lower() or 'degree' in col.lower() or 'program' in col.lower():
                    course_col = col
                    break
            
            st.divider()
            st.subheader("Categorization Rule")
            
            if course_col:
                st.info(f"सिस्टम ने ऑटोमैटिकली `{course_col}` कॉलम को कोर्स विभाजन के लिए चुना है।")
                selected_col = course_col
            else:
                selected_col = st.selectbox("कोर्स/डिग्री वाले कॉलम को चुनें जिससे UG/PG अलग किया जा सके:", df.columns)
            
            ug_keywords = st.text_input("UG की पहचान के लिए कीवर्ड्स (कमा से अलग करें)", "BA, BSC, BCOM, BTECH, UG")
            pg_keywords = st.text_input("PG की पहचान के लिए कीवर्ड्स (कमा से अलग करें)", "MA, MSC, MCOM, MTECH, PG")
            
            if st.button("💾 डेटाबेस में सेव करें (Save to DB)"):
                ug_list = [x.strip().lower() for x in ug_keywords.split(",")]
                pg_list = [x.strip().lower() for x in pg_keywords.split(",")]
                
                ug_rows = []
                pg_rows = []
                
                for _, row in df.iterrows():
                    val = str(row[selected_col]).lower()
                    is_ug = any(kw in val for kw in ug_list)
                    is_pg = any(kw in val for kw in pg_list)
                    
                    row_dict = row.to_dict()
                    if is_ug:
                        ug_rows.append(row_dict)
                    elif is_pg:
                        pg_rows.append(row_dict)
                    else:
                        ug_rows.append(row_dict) # डिफ़ॉल्ट UG में डाल रहे हैं
                
                # Save to SQLite
                if ug_rows:
                    cursor.execute("INSERT INTO uploaded_data (data_json, course_type) VALUES (?, ?)", (json.dumps(ug_rows), "UG"))
                if pg_rows:
                    cursor.execute("INSERT INTO uploaded_data (data_json, course_type) VALUES (?, ?)", (json.dumps(pg_rows), "PG"))
                conn.commit()
                
                st.success(f"🎉 डेटा सफलतापूर्वक सेव हो गया! (UG: {len(ug_rows)} रोज़, PG: {len(pg_rows)} रोज़)")
                st.balloons()
        except Exception as e:
            st.error(f"त्रुटि: {e}")

# --- PANEL 2: WORK PANEL ---
elif panel == "💻 Work Panel (गलती चेकिंग)":
    st.title("💻 Work Panel - डेटा चेकिंग और वैलिडेशन")
    
    full_df = load_db_data()
    
    if full_df is None:
        st.info("ℹ️ अभी डेटाबेस खाली है। कृपया पहले 'Entry Panel' में जाकर डेटा अपलोड करें।")
    else:
        # UG और PG को दो अलग पैनल/टैब में बांटना
        tab_ug, tab_pg = st.tabs(["🎓 UNDERGRADUATE (UG) PANEL", "📜 POSTGRADUATE (PG) PANEL"])
        
        # Filter Data
        df_ug = full_df[full_df['Course_Category'] == 'UG'].drop(columns=['Course_Category']).reset_index(drop=True)
        df_pg = full_df[full_df['Course_Category'] == 'PG'].drop(columns=['Course_Category']).reset_index(drop=True)
        
        # --- UG TAB WORK ---
        with tab_ug:
            if df_ug.empty:
                st.write("UG का कोई डेटा नहीं है।")
            else:
                st.subheader("UG डेटा चेकिंग स्क्रीन")
                
                columns_ug = df_ug.columns.tolist()
                
                # हर कॉलम के लिए एक स्क्रॉल लिस्ट (सिलेक्ट बॉक्स) ताकि यूजर बता सके कि इस कॉलम में क्या गलत है
                st.markdown("### 🔍 हर कॉलम के लिए गलत (Invalid Values) सब्जेक्ट्स/वैल्यूज चुनें")
                
                # Dictionary to store wrong inputs for each column
                wrong_values_by_col = {}
                
                # Expandable filter block to keep UI clean
                with st.expander("⚙️ यहाँ क्लिक करके हर कॉलम की स्क्रॉल लिस्ट खोलें", expanded=True):
                    # Creating grid layout for columns lists
                    grid_cols = st.columns(3)
                    for idx, col_name in enumerate(columns_ug):
                        with grid_cols[idx % 3]:
                            # Get unique values of this column to show in scroll list
                            unique_vals = df_ug[col_name].dropna().unique().tolist()
                            selected_wrongs = st.multiselect(
                                f"गलत वैल्यू चुनें: `{col_name}`",
                                options=unique_vals,
                                key=f"ug_multiselect_{col_name}"
                            )
                            if selected_wrongs:
                                wrong_values_by_col[col_name] = selected_wrongs
                
                # Function to style cells dynamically (Red Cell logic)
                def highlight_invalid_cells(dataframe):
                    # Style dataframe create empty matching df with format
                    style_df = pd.DataFrame('', index=dataframe.index, columns=dataframe.columns)
                    
                    for col in dataframe.columns:
                        if col in wrong_values_by_col:
                            wrong_list = wrong_values_by_col[col]
                            # If cell value is in wrong list, make it red text and light red background
                            style_df[col] = dataframe[col].apply(
                                lambda x: 'background-color: #ffcccc; color: #cc0000; font-weight: bold;' if x in wrong_list else ''
                            )
                    return style_df
                
                st.divider()
                st.subheader("📊 UG फाइनल लाइव रिजल्ट टेबल (गलत सेल्स लाल रंग में दिखेंगे):")
                
                # Show styled dataframe
                st.dataframe(df_ug.style.apply(highlight_invalid_cells, axis=None), height=500, use_container_width=True)
                
        # --- PG TAB WORK ---
        with tab_pg:
            if df_pg.empty:
                st.write("PG का कोई डेटा नहीं है।")
            else:
                st.subheader("PG डेटा चेकिंग स्क्रीन")
                columns_pg = df_pg.columns.tolist()
                
                # Same logic for PG if you want to implement rules for PG as well
                wrong_values_pg = {}
                with st.expander("⚙️ यहाँ क्लिक करके PG कॉलम की स्क्रॉल लिस्ट खोलें"):
                    grid_cols_pg = st.columns(3)
                    for idx, col_name in enumerate(columns_pg):
                        with grid_cols_pg[idx % 3]:
                            unique_vals_pg = df_pg[col_name].dropna().unique().tolist()
                            # --- यहाँ से आपका कोड शुरू होता है ---
                            selected_wrongs_pg = st.multiselect(
                                f"PG गलत वैल्यू: `{col_name}`",
                                options=unique_vals_pg,
                                key=f"pg_multiselect_{col_name}"
                            )
                            # अगर यूजर लिस्ट से कोई गलत वैल्यू चुनता है, तो उसे सेव करें
                            if selected_wrongs_pg:
                                wrong_values_pg[col_name] = selected_wrongs_pg
                                
                # 1. PG टेबल के सेल्स को लाल (Red) करने का फंक्शन
                def highlight_pg(dataframe):
                    # पहले एक खाली स्टाइल फ्रेम बनाते हैं
                    style_df = pd.DataFrame('', index=dataframe.index, columns=dataframe.columns)
                    for col in dataframe.columns:
                        # अगर इस कॉलम में कोई गलत वैल्यू चुनी गई है
                        if col in wrong_values_pg:
                            wrong_list = wrong_values_pg[col]
                            # मैच होने वाले सेल को लाइट रेड बैकग्राउंड और डार्क रेड टेक्स्ट दें
                            style_df[col] = dataframe[col].apply(
                                lambda x: 'background-color: #ffcccc; color: #cc0000; font-weight: bold; border: 1px solid red;' if x in wrong_list else ''
                            )
                    return style_df
                
                st.divider()
                st.subheader("📊 PG फाइनल लाइव रिजल्ट टेबल (गलत सब्जेक्ट्स लाल रंग में दिखेंगे):")
                
                # 2. लाइव हाइलाइटेड PG डेटा टेबल दिखाना
                st.dataframe(
                    df_pg.style.apply(highlight_pg, axis=None), 
                    height=500, 
                    use_container_width=True
                )

