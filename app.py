import streamlit as st
import pandas as pd
import sqlite3
import json

st.set_page_config(layout="wide")

# =========================================================================
# डेटाबेस सेटअप - दो टेबल्स (1. अस्थायी रॉ डेटा के लिए, 2. अप्रूव्ड डेटा के लिए)
# =========================================================================
conn = sqlite3.connect("nep_master_perma_db.db", check_same_thread=False)
cursor = conn.cursor()

# 1. अस्थायी स्टोरेज (Panel 1 से Upload होकर यहाँ आएगा)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_store (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_json TEXT
    )
""")

# 2. परमानेंट स्टोरेज (Panel 2 से Approve होकर UG/PG यहाँ आएगा)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS perma_store (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_json TEXT,
        course_type TEXT
    )
""")
conn.commit()

# Session States
if "ok" not in st.session_state: st.session_state["ok"] = False
if "deleted_cols" not in st.session_state: st.session_state["deleted_cols"] = []

# --- LOGIN SYSTEM ---
if not st.session_state["ok"]:
    st.title("🔒 Login System")
    user = st.selectbox("Username:", ["-- चुनें --", "Admin", "Operator", "Teacher_UG", "Teacher_PG"])
    pas = st.text_input("Password:", type="password")
    if st.button("Login"):
        if (user == "Admin" and pas == "psv123") or (user == "Operator" and pas == "op") or (user == "Teacher_UG" and pas == "ug") or (user == "Teacher_PG" and pas == "pg"):
            st.session_state["ok"] = True
            st.session_state["user"] = user
            st.rerun()
        else: 
            st.error("गलत पासवर्ड! कृपया सही पासवर्ड डालें।")
    st.stop()

# =========================================================================
# 5 रोल-बेस्ड पैनल्स का नेविगेशन
# =========================================================================
u = st.session_state["user"]

if u == "Operator":
    p_opts = ["📥 1. Entry / Upload Panel"]
elif u == "Teacher_UG":
    p_opts = ["🎓 3. UG Panel"]
elif u == "Teacher_PG":
    p_opts = ["📜 4. PG Panel"]
else:
    p_opts = [
        "📥 1. Entry / Upload Panel", 
        "💻 2. Work / Approve Panel", 
        "🎓 3. UG Panel", 
        "📜 4. PG Panel", 
        "⚙️ 5. Admin Panel"
    ]

panel = st.sidebar.radio("पैनल चुनें:", p_opts)

# डेटाबेस से डेटा लोड करने के फंक्शंस
def load_raw_data():
    cursor.execute("SELECT data_json FROM raw_store ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        return pd.DataFrame(json.loads(row[0]))
    return None

def load_permanent_data(c_type):
    cursor.execute("SELECT data_json FROM perma_store WHERE course_type = ?", (c_type,))
    rows = cursor.fetchall()
    if rows:
        dfs = []
        for r in rows:
            dfs.append(pd.DataFrame(json.loads(r[0])))
        return pd.concat(dfs, ignore_index=True)
    return None

# लाइव चेकिंग और स्टाइलिंग का कोर लॉजिक फंक्शन
def process_panel_validation(df_panel, prefix, allowed_degrees):
    deg_col = next((c for c in df_panel.columns if any(k in c.lower() for k in ['deg', 'course', 'class'])), df_panel.columns[0])
    br_col = next((c for c in df_panel.columns if any(k in c.lower() for k in ['branch', 'stream', 'subject'])), df_panel.columns[1])
    
    def check_degree(val):
        v = str(val).lower().replace(".", "").replace(" ", "").strip()
        return any(d in v for d in allowed_degrees)
        
    df_filtered = df_panel[df_panel[deg_col].apply(check_degree)].reset_index(drop=True)
    
    if df_filtered.empty:
        st.warning(f"⚠️ {prefix.upper()} पैनल के लिए कोई उपयुक्त डेटा (मैचिंग डिग्री) नहीं मिला।")
        return

    minor_col = next((c for c in df_filtered.columns if 'minor' in c.lower()), None)
    mdc_col = next((c for c in df_filtered.columns if 'mdc' in c.lower()), None)
    voc_col = next((c for c in df_filtered.columns if 'voc' in c.lower() or 'skill' in c.lower()), None)
    pw_col = next((c for c in df_filtered.columns if any(k in c.lower() for k in ['pw', 'project', 'ce'])), None)

    df_filtered['combo'] = df_filtered[deg_col].astype(str) + " - " + df_filtered[br_col].astype(str)
    unique_combos = df_filtered['combo'].unique().tolist()
    
    st.subheader("📋 स्टेप 1: डिग्री + ब्रांच के अनुसार सही विषय सेट करें")
    
    opt_mdc = df_filtered[mdc_col].dropna().unique().tolist() if (mdc_col and mdc_col in df_filtered.columns) else []
    opt_voc = df_filtered[voc_col].dropna().unique().tolist() if (voc_col and voc_col in df_filtered.columns) else []
    opt_pw = df_filtered[pw_col].dropna().unique().tolist() if (pw_col and pw_col in df_filtered.columns) else []
    
    rules = {}
    for idx, combo in enumerate(unique_combos):
        st.markdown(f"#### 📍 `{combo}`")
        c1, c2, c3 = st.columns(3)
        with c1: r_mdc = st.multiselect(f"Valid MDC for {combo}", opt_mdc, key=f"mdc_{prefix}_{idx}")
        with c2: r_voc = st.multiselect(f"Valid Vocational for {combo}", opt_voc, key=f"voc_{prefix}_{idx}")
        with c3: r_pw = st.multiselect(f"Valid PW/Ap/CE for {combo}", opt_pw, key=f"pw_{prefix}_{idx}")
            
        rules[combo] = {
            "mdc": {str(x).strip().lower() for x in r_mdc},
            "voc": {str(x).strip().lower() for x in r_voc},
            "pw": {str(x).strip().lower() for x in r_pw}
        }

    def cell_styler(dataframe):
        s_df = pd.DataFrame('', index=dataframe.index, columns=dataframe.columns)
        targets = {mdc_col: 'mdc', voc_col: 'voc', pw_col: 'pw'}
        
        for index, row in dataframe.iterrows():
            c_val = str(row[deg_col]) + " - " + str(row[br_col])
            c_rule = rules.get(c_val, {"mdc":set(), "voc":set(), "pw":set()})
            
            for b_col in [br_col, minor_col]:
                if b_col and b_col in dataframe.columns:
                    b_val = row[b_col]
                    if pd.isna(b_val) or str(b_val).strip() == "":
                        s_df.at[index, b_col] = 'background-color: #d1ecf1; color: #0c5460; font-weight: bold; border: 1px solid #17a2b8;'
            
            for col_name, rule_key in targets.items():
                if col_name and col_name in dataframe.columns:
                    val = row[col_name]
                    if pd.isna(val) or str(val).strip() == "":
                        s_df.at[index, col_name] = 'background-color: #d1ecf1; color: #0c5460; font-weight: bold; border: 1px solid #17a2b8;'
                    else:
                        val_clean = str(val).strip().lower()
                        valid_set = c_rule[rule_key]
                        if valid_set and val_clean not in valid_set:
                            s_df.at[index, col_name] = 'background-color: #f8d7da; color: #721c24; font-weight: bold; border: 2px solid red;'
        return s_df

    st.divider()
    st.subheader(f"📊 लाइव वैरिफाइड {prefix.upper()} डेटा टेबल")
    st.caption("🔵 नीला सेल = डेटा गायब है | 🔴 लाल cell = गलत विषय (मिसमैच)")
    
    display_df = df_filtered.drop(columns=['combo'])
    st.dataframe(display_df.style.apply(cell_styler, axis=None), height=600, use_container_width=True)

# =========================================================================
# 📥 PANEL 1: ENTRY / UPLOAD PANEL
# =========================================================================
if panel == "📥 1. Entry / Upload Panel":
    st.title("📥 Entry Panel - डेटा सुरक्षित अपलोड")
    st.write("यहाँ अपलोड की गई फ़ाइल सीधे समीक्षा (Review) के लिए **Work / Approve Panel** में भेज दी जाएगी।")
    
    f = st.file_uploader("अपनी फ़ाइल अपलोड करें", type=["csv", "xlsx"])
    if f:
        try:
            df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
            st.success(f"फ़ाइल लोड हो गई ({len(df)} रोज़)!")
            
            if st.button("📤 वर्क/अप्रूवल पैनल में भेजें"):
                # पुरानी रॉ फ़ाइल साफ़ करके नई डालना
                cursor.execute("DELETE FROM raw_store")
                cursor.execute("INSERT INTO raw_store (data_json) VALUES (?)", (json.dumps(df.to_dict(orient='records')),))
                conn.commit()
                st.session_state["deleted_cols"] = [] # कॉलम डिलीट लिस्ट रीसेट
                
                st.success("🎉 फ़ाइल सफलतापूर्वक अपलोड होकर **Work / Approve Panel** में ट्रांसफर हो गई है!")
                st.balloons()
        except Exception as e:
            st.error(f"त्रुटि: {e}")

# =========================================================================
# 💻 PANEL 2: WORK / APPROVE PANEL (कॉलम हटाना + UG/PG विभाजन और अप्रूवल)
# =========================================================================
elif panel == "💻 2. Work / Approve Panel":
    st.title("💻 Work / Approve Panel - डेटा प्रोसेसिंग एवं अप्रूवल")
    
    raw_df = load_raw_data()
    
    if raw_df is None:
        st.info("📥 वर्तमान में कोई नई अपलोड की गई फ़ाइल पेंडिंग नहीं है। कृपया पहले 'Entry / Upload Panel' से फ़ाइल अपलोड करें।")
    else:
        st.subheader("🗑️ बेकार कॉलम हटाएं (Remove Unwanted Columns)")
        active_cols = [c for c in raw_df.columns if c not in st.session_state["deleted_cols"]]
        
        cols_to_delete = st.multiselect("हटाने के लिए अनुपयोगी कॉलम चुनें:", options=active_cols)
        if cols_to_delete:
            if st.button("🔴 चुने गए कॉलम हटाएं"):
                st.session_state["deleted_cols"].extend(cols_to_delete)
                st.success("चयनित कॉलम स्क्रीन से हटा दिए गए!")
                st.rerun()
        
        # फ़िल्टर्ड डेटा दिखाना
        final_raw_df = raw_df[active_cols]
        st.divider()
        st.subheader("📋 अपलोड किए गए रॉ डेटा का लाइव प्रीव्यू")
        st.dataframe(final_raw_df, height=350, use_container_width=True)
        
                # ऑटोमैटिक UG/PG विभाजन के लिए कॉलम खोजना (Eligibility / Qualification / Course)
        el_col = next((c for c in final_raw_df.columns if any(k in c.lower() for k in ['elig', 'qual', 'class', 'course', 'deg'])), final_raw_df.columns[0])
        st.info(f"🔍 सिस्टम ऑटो-वर्गीकरण के लिए **'{el_col}'** कॉलम का उपयोग कर रहा है।")
        
        # --- लाइव प्री-विभाजन व्यू (बटन दबाने से पहले देखें) ---
        st.divider()
        st.subheader("👀 लाइव प्री-विभाजन समीक्षा (Live Split Preview)")
        
        ug_preview_rows = []
        pg_preview_rows = []
        
        for _, row in final_raw_df.iterrows():
            val = str(row[el_col]).lower().replace(".", "").replace(" ", "").strip()
            # योग्यता जाँच लॉजिक
            if any(k in val for k in ["ma", "msc", "mcom", "mba", "mca", "post grad", "pg", "grad"]):
                pg_preview_rows.append(row)
            else:
                ug_preview_rows.append(row)
                
        df_ug_preview = pd.DataFrame(ug_preview_rows)
        df_pg_preview = pd.DataFrame(pg_preview_rows)
        
        # दो छोटे टैब्स में लाइव रिव्यू दिखाना
        prev_tab1, prev_tab2 = st.tabs([f"🎓 UG में जाने वाला डेटा ({len(df_ug_preview)} रोज़)", f"📜 PG में जाने वाला डेटा ({len(df_pg_preview)} रोज़)"])
        
        with prev_tab1:
            if not df_ug_preview.empty:
                st.dataframe(df_ug_preview, height=250, use_container_width=True)
            else:
                st.caption("कोई डेटा UG श्रेणी में नहीं मिला।")
                
        with prev_tab2:
            if not df_pg_preview.empty:
                st.dataframe(df_pg_preview, height=250, use_container_width=True)
            else:
                st.caption("कोई डेटा PG श्रेणी में नहीं मिला।")

        # --- फाइनल अप्रूवल और रूटिंग एक्शन ---
        st.divider()
        st.subheader("🚀 फाइनल एक्शन")
        
        if st.button("✅ डेटा अप्रूव करें और संबंधित पैनल्स में ट्रांसफर करें"):
            # परमानेंट डेटाबेस में रिकॉर्ड्स को सेव करना
            if not df_ug_preview.empty:
                cursor.execute("INSERT INTO perma_store (data_json, course_type) VALUES (?, ?)", 
                               (json.dumps(df_ug_preview.to_dict(orient='records')), "UG"))
            if not df_pg_preview.empty:
                cursor.execute("INSERT INTO perma_store (data_json, course_type) VALUES (?, ?)", 
                               (json.dumps(df_pg_preview.to_dict(orient='records')), "PG"))
            
            # कार्य पूरा होने पर Raw Store से फ़ाइल डिलीट करना ताकि एंट्री पैनल रीसेट हो जाए
            cursor.execute("DELETE FROM raw_store")
            conn.commit()
            
            st.success("🎉 बधाई हो! डेटा सफलता पूर्वक क्लीन, विभाजित (UG/PG) और सुरक्षित लॉक कर दिया गया है।")
            st.balloons()
            st.rerun()

# =========================================================================
# 🎓 PANEL 3: UG PANEL (सिर्फ अप्रूव्ड UG डेटा की लाइव चेकिंग और त्रुटि सुधार)
# =========================================================================
elif panel == "🎓 3. UG Panel":
    st.title("🎓 Undergraduate (UG) चेकिंग एवं त्रुटि सुधार पैनल")
    st.write("यहाँ Panel 2 से अप्रूव होकर आया हुआ शुद्ध UG डेटा प्रदर्शित हो रहा है।")
    
    # परमानेंट डेटाबेस से केवल UG का डेटा लोड करना
    df_ug = load_permanent_data("UG")
    
    if df_ug is None:
        st.info("ℹ️ UG डेटाबेस में अभी कोई डेटा लॉक नहीं है। कृपया पहले **Panel 2 (Work / Approve Panel)** में जाकर डेटा अप्रूव करें।")
    else:
        # आवश्यक कोर्सेस/डिग्री की सूची जिन्हें इस पैनल में प्रोसेस करना है
        allowed_ug_degrees = ["ba", "bsc", "bcom", "bhsc", "12th", "bba", "bca", "btech", "llb"]
        
        # कोर वैलिडेशन और लाइव हाइलाइटिंग टेबल को रन करना
        # (यह ऑटोमैटिकली गायब डेटा को नीले रंग में और गलत विषय को लाल रंग में दिखाएगा)
        process_panel_validation(df_ug, "ug", allowed_ug_degrees)

# =========================================================================
# 📜 PANEL 4: PG PANEL (सिर्फ अप्रूव्ड PG डेटा की लाइव चेकिंग और त्रुटि सुधार)
# =========================================================================
elif panel == "📜 4. PG Panel":
    st.title("📜 Postgraduate (PG) चेकिंग एवं त्रुटि सुधार पैनल")
    st.write("यहाँ Panel 2 से अप्रूव होकर आया हुआ शुद्ध PG डेटा प्रदर्शित हो रहा है।")
    
    # परमानेंट डेटाबेस से केवल PG का डेटा लोड करना
    df_pg = load_permanent_data("PG")
    
    if df_pg is None:
        st.info("ℹ️ PG डेटाबेस में अभी कोई डेटा लॉक नहीं है। कृपया पहले **Panel 2 (Work / Approve Panel)** में जाकर डेटा अप्रूव करें।")
    else:
        # आवश्यक कोर्सेस/डिग्री की सूची जिन्हें इस पैनल में प्रोसेस करना है
        allowed_pg_degrees = ["ma", "msc", "mcom", "mba", "mca", "post grad", "pg", "mtech", "llm"]
        
        # कोर वैलिडेशन और लाइव हाइलाइटिंग टेबल को रन करना
        # (यह ऑटोमैटिकली गायब डेटा को नीले रंग में और गलत विषय को लाल रंग में दिखाएगा)
        process_panel_validation(df_pg, "pg", allowed_pg_degrees)

# =========================================================================
# ⚙️ PANEL 5: ADMIN PANEL (मास्टर कंट्रोल, बैकअप डाउनलोड एवं डेटा रीसेट)
# =========================================================================
elif panel == "⚙️ 5. Admin Panel":
    st.title("⚙️ Admin Panel - मास्टर डेटाबेस कंट्रोल")
    st.write("यह केवल एडमिनिस्ट्रेटर के लिए है। यहाँ से आप पूरे डेटा का बैकअप ले सकते हैं और सिस्टम को रीसेट कर सकते हैं।")
    
    # 📥 सेक्शन 1: बैकअप और डाउनलोड (Backup & Export)
    st.divider()
    st.subheader("📥 डेटाबेस बैकअप डाउनलोड करें")
    st.write("डेटाबेस खाली करने से पहले या काम पूरा होने पर आप यहाँ से फ़ाइल डाउनलोड कर सकते हैं।")
    
    # दोनों प्रकार का डेटा लोड करना
    df_ug_download = load_permanent_data("UG")
    df_pg_download = load_permanent_data("PG")
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("#### 🎓 UG डेटा बैकअप")
        if df_ug_download is not None and not df_ug_download.empty:
            st.success(f"कुल रिकॉर्ड्स उपलब्ध: {len(df_ug_download)}")
            # CSV में कनवर्ट करना
            csv_ug = df_ug_download.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 UG डेटा CSV डाउनलोड करें",
                data=csv_ug,
                file_name="Approved_UG_Data_Backup.csv",
                mime="text/csv",
                key="download_ug_csv"
            )
        else:
            st.info("UG डेटाबेस में डाउनलोड के लिए कोई डेटा नहीं है।")
            
    with c2:
        st.markdown("#### 📜 PG डेटा बैकअप")
        if df_pg_download is not None and not df_pg_download.empty:
            st.success(f"कुल रिकॉर्ड्स उपलब्ध: {len(df_pg_download)}")
            # CSV में कनवर्ट करना
            csv_pg = df_pg_download.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 PG डेटा CSV डाउनलोड करें",
                data=csv_pg,
                file_name="Approved_PG_Data_Backup.csv",
                mime="text/csv",
                key="download_pg_csv"
            )
        else:
            st.info("PG डेटाबेस में डाउनलोड के लिए कोई डेटा नहीं है।")

    # 🚨 सेक्शन 2: डेंजर ज़ोन (Danger Zone - डेटा रीसेट)
    st.divider()
    st.subheader("🚨 डेंजर ज़ोन (Danger Zone)")
    st.warning("सावधान: यहाँ से किया गया बदलाव पूरे सिस्टम के डेटा को हमेशा के लिए मिटा देगा।")
    
    # आकस्मिक डिलीट से बचने के लिए डबल कन्फर्मेशन चेकबॉक्स
    confirm_reset = st.checkbox("हाँ, मैं पुष्टि करता/करती हूँ कि मुझे रॉ (Temporary) और अप्रूव्ड (Permanent) दोनों डेटाबेस पूरी तरह से खाली करने हैं।")
    
    if st.button("💥 ऑल डेटाबेस रीसेट करें (Reset System)"):
        if confirm_reset:
            # दोनों टेबल्स को साफ़ करना
            cursor.execute("DELETE FROM raw_store")
            cursor.execute("DELETE FROM perma_store")
            conn.commit()
            
            # सेशन स्टेट रीसेट करना
            st.session_state["deleted_cols"] = []
            
            st.success("🎉 सिस्टम को सफलतापूर्वक रीसेट कर दिया गया है! सभी टेबल्स खाली हो चुके हैं।")
            st.balloons()
            st.rerun()
        else:
            st.error("त्रुटि: कृपया डेटाबेस खाली करने से पहले ऊपर दिए गए 'पुष्टि चेकबॉक्स' को टिक करें।")



