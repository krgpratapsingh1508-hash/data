import streamlit as st
import pandas as pd
import sqlite3
import json

# Page configuration
st.set_page_config(page_title="NEP Multi-Panel Validator Pro", layout="wide")

# Database initialization
conn = sqlite3.connect("nep_final_secure_db.db", check_same_thread=False)
cursor = conn.cursor()
# सिंगल टेबल जिसमें ऑपरेटर का रॉ डेटा सेव रहेगा
cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_uploaded_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_json TEXT
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
                input_pass = str(password).strip() # नो लोअरकेस ताकि 'psv123' जैसा ही रहे
                
                # आपके स्पेशल पासवर्ड 'psv123' के साथ मैचिंग
                if username == "Admin" and input_pass == "psv123":
                    st.session_state["logged_in"] = True
                    st.session_state["current_user"] = "Admin"
                    st.success("स्वागत है एडमिन!")
                    st.rerun()
                elif username == "Teacher_UG" and input_pass == "ug":
                    st.session_state["logged_in"] = True
                    st.session_state["current_user"] = "Teacher_UG"
                    st.rerun()
                elif username == "Teacher_PG" and input_pass == "pg":
                    st.session_state["logged_in"] = True
                    st.session_state["current_user"] = "Teacher_PG"
                    st.rerun()
                elif username == "Operator" and input_pass == "op":
                    st.session_state["logged_in"] = True
                    st.session_state["current_user"] = "Operator"
                    st.rerun()
                else:
                    st.error("❌ गलत पासवर्ड! कृपया सही पासवर्ड डालें।")
    st.stop()

# --- LOGOUT & USER INFO ---
st.sidebar.markdown(f"👤 **Logged in as:** `{st.session_state['current_user']}`")
if st.sidebar.button("Logout 🏃‍♂️"):
    st.session_state["logged_in"] = False
    st.session_state["current_user"] = ""
    st.rerun()

# --- 2. DYNAMIC PANEL PERMISSIONS BASED ON USER ---
current_user = st.session_state["current_user"]

# यूजर के हिसाब से कौन से पैनल दिखने चाहिए
if current_user == "Admin":
    available_panels = ["📥 Entry Panel (डेटा अपलोड)", "💻 Work Panel (नियम और वैलिडेशन)", "⚙️ Admin Panel (मैनेजमेंट)"]
elif current_user == "Operator":
    available_panels = ["📥 Entry Panel (डेटा अपलोड)"]
else: # Teachers
    available_panels = ["💻 Work Panel (नियम और वैलिडेशन)"]

panel = st.sidebar.radio("पैनल चुनें (Select Panel)", available_panels)

# Helper function to load raw data
def load_raw_db_data():
    cursor.execute("SELECT data_json FROM raw_uploaded_data ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        return pd.DataFrame(json.loads(row[0]))
    return None


# --- PANEL 1: ENTRY PANEL (सिर्फ अपलोड करने के लिए) ---
if panel == "📥 Entry Panel (डेटा अपलोड)":
    st.title("📥 Entry Panel - डेटा अपलोड")
    st.write("यहाँ एक्सेल या सीएसवी फ़ाइल अपलोड करें। यह डेटा सुरक्षित एडमिन डेटाबेस में सेव हो जाएगा।")
    
    uploaded_file = st.file_uploader("अपनी फ़ाइल चुनें", type=["csv", "xlsx"])
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
                
            st.success(f"फ़ाइल सफलतापूर्वक रीड कर ली गई है ({len(df)} रोज़)!")
            
            if st.button("💾 एडमिन डेटाबेस में सेव करें"):
                # JSON फ़ॉर्मेट में कनवर्ट करके SQLite में डालना
                data_json = df.to_json(orient="records")
                cursor.execute("INSERT INTO raw_uploaded_data (data_json) VALUES (?)", (data_json,))
                conn.commit()
                st.success("🎉 डेटा एडमिन के डेटाबेस में सुरक्षित सेव हो गया है!")
                st.balloons()
        except Exception as e:
            st.error(f"त्रुटि: {e}")


# --- PANEL 2: WORK PANEL (स्क्रॉल लिस्ट से एलिजिबिलिटी और यूजी/पीजी फिल्टर) ---
elif panel == "💻 Work Panel (नियम और वैलिडेशन)":
    st.title("💻 Work Panel - एलिजिबिलिटी चेकिंग और वर्गीकरण")
    
    df_raw = load_raw_db_data()
    
    if df_raw is None:
        st.info("ℹ️ अभी डेटाबेस में कोई डेटा उपलब्ध नहीं है। कृपया ऑपरेटर से फ़ाइल अपलोड करवाएं।")
    else:
        # एलिजिबिलिटी कॉलम ढूंढना
        eligibility_col = None
        for col in df_raw.columns:
            if 'eligibility' in col.lower() or 'elig' in col.lower() or 'qualification' in col.lower():
                eligibility_col = col
                break
                
        if not eligibility_col:
            eligibility_col = st.selectbox("एलिजिबिलिटी (Eligibility) वाला कॉलम मैनुअली चुनें:", df_raw.columns)
            
        # एलिजिबिलिटी कॉलम की सभी यूनिक वैल्यूज निकालना स्क्रॉल लिस्ट के लिए
        unique_eligibilities = df_raw[eligibility_col].dropna().unique().tolist()
        
        st.subheader("⚙️ एलिजिबिलिटी रूल्स सेट करें")
        st.write("नीचे दी गई दो स्क्रॉल लिस्ट में से चुनें कि कौन सी एलिजिबिलिटी किस पैनल (UG/PG) में जानी चाहिए:")
        
        col_list1, col_list2 = st.columns(2)
        
        with col_list1:
            ug_selected = st.multiselect(
                "🎓 UNDERGRADUATE (UG) एलिजिबिलिटी चुनें:",
                options=unique_eligibilities,
                placeholder="यहाँ क्लिक करके UG एलिजिबिलिटी चुनें..."
            )
            
        with col_list2:
            pg_selected = st.multiselect(
                "📜 POSTGRADUATE (PG) एलिजिबिलिटी चुनें:",
                options=unique_eligibilities,
                placeholder="यहाँ क्लिक करके PG एलिजिबिलिटी चुनें..."
            )
            
        # डेटा को सिलेक्टेड एलिजिबिलिटी के आधार पर पूरी रो के साथ अलग करना
        df_ug = df_raw[df_raw[eligibility_col].isin(ug_selected)].reset_index(drop=True)
        df_pg = df_raw[df_raw[eligibility_col].isin(pg_selected)].reset_index(drop=True)
        
        # UG और PG के डिस्प्ले के लिए अलग टैब्स
        tab_ug, tab_pg = st.tabs(["🎓 UG वर्गीकृत डेटा ( पूरी रो )", "📜 PG वर्गीकृत डेटा ( पूरी रो )"])
        
        with tab_ug:
            st.subheader(f"UG डेटा लिस्ट (कुल रिकॉर्ड्स: {len(df_ug)})")
            if not df_ug.empty:
                st.dataframe(df_ug, use_container_width=True)
            else:
                st.info("ऊपर स्क्रॉल लिस्ट से एलिजिबिलिटी चुनने पर UG का डेटा यहाँ पूरी रो के साथ आ जाएगा।")
                
        with tab_pg:
            st.subheader(f"PG डेटा लिस्ट (कुल रिकॉर्ड्स: {len(df_pg)})")
            if not df_pg.empty:
                st.dataframe(df_pg, use_container_width=True)
            else:
                st.info("ऊपर स्क्रॉल लिस्ट से एलिजिबिलिटी चुनने पर PG का डेटा यहाँ पूरी रो के साथ आ जाएगा।")


# --- PANEL 3: ADMIN PANEL (सिर्फ एडमिन को दिखेगा, डिलीट सिर्फ पासवर्ड 'psv123' से होगा) ---
elif panel == "⚙️ Admin Panel (मैनेजमेंट)":
    st.title("⚙️ Admin Panel - मास्टर कंट्रोल")
    
    df_raw = load_raw_db_data()
    
    if df_raw is not None:
        st.subheader("📊 डेटाबेस स्टेटिस्टिक्स")
        st.info(f"वर्तमान में मास्टर डेटाबेस के अंदर कुल **{len(df_raw)}** रो (Rows) का डेटा सुरक्षित है।")
        st.dataframe(df_raw.head(10))
        
        st.divider()
        st.subheader("🗑️ डेटाबेस डिलीट डेंजर ज़ोन")
        st.write("डेटाबेस डिलीट करने के लिए अपना एडमिन सीक्रेट कन्फर्मेशन पासवर्ड डालें:")
        
        delete_pass = st.text_input("कन्फर्मेशन पासवर्ड दर्ज करें:", type="password", key="del_pass_input")
        
        if st.button("🔴 डेटाबेस को हमेशा के लिए डिलीट करें"):
            if delete_pass == "psv123":
                cursor.execute("DELETE FROM raw_uploaded_data")
                conn.commit()
                st.success("💥 एडमिन डेटाबेस को सफलतापूर्वक साफ़ (Delete) कर दिया गया है!")
                st.rerun()
            else:
                st.error("❌ गलत कन्फर्मेशन पासवर्ड! डेटा डिलीट नहीं किया गया।")
    else:
        st.info("डेटाबेस वर्तमान में खाली है।")
