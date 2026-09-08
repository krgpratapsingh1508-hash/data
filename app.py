import streamlit as st
import pandas as pd
import sqlite3
import json

st.set_page_config(layout="wide")

# =========================================================================
# डेटाबेस सेटअप - टेबल्स संरचना (Raw, Permanent और Rules Lock)
# =========================================================================
conn = sqlite3.connect("nep_master_perma_db.db", check_same_thread=False)
cursor = conn.cursor()

# 1. अस्थायी स्टेजिंग स्टोरेज (Panel 1 से Upload होकर यहाँ आएगा)
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

# 3. परमानेंट नियम लॉकिंग स्टोरेज (पुरानी खराब टेबल को डिलीट करके नया बनाने का ऑटो-सिस्टम)
try:
    # चेक करना कि क्या टेबल सही है
    cursor.execute("SELECT panel_prefix FROM locked_rules LIMIT 1")
except sqlite3.OperationalError:
    # अगर कोई भी गड़बड़ (जैसे कॉलम गायब होना) मिले, तो पुरानी टेबल हटा दें
    cursor.execute("DROP TABLE IF EXISTS locked_rules")
    conn.commit()

# अब बिल्कुल सही और नए स्ट्रक्चर के साथ टेबल बनाएं
cursor.execute("""
    CREATE TABLE IF NOT EXISTS locked_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        panel_prefix TEXT UNIQUE,
        rules_json TEXT
    )
""")
conn.commit()

# सुनिश्चित करें कि टेबल बनने के बाद डेटाबेस में बदलाव सुरक्षित (Commit) हो जाएं
conn.commit()

# =========================================================================
# परमानेंट डेटा लोड करने का फंक्शन (perma_store से UG/PG डेटा पढ़ने के लिए)
# =========================================================================
def load_permanent_data(course_type):
    cursor.execute("SELECT data_json FROM perma_store WHERE course_type = ?", (course_type,))
    rows = cursor.fetchall()
    if not rows:
        return pd.DataFrame()
    all_records = []
    for (data_json,) in rows:
        try:
            records = json.loads(data_json)
            if isinstance(records, list):
                all_records.extend(records)
            else:
                all_records.append(records)
        except (json.JSONDecodeError, TypeError):
            continue
    if not all_records:
        return pd.DataFrame()
    return pd.DataFrame(all_records)

def load_raw_data():
    cursor.execute("SELECT data_json FROM raw_store ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    if not row or not row[0]:
        return pd.DataFrame()
    try:
        records = json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return pd.DataFrame()
    if isinstance(records, dict):
        records = [records]
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)

# Session States Management
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
# 🔄 6 रोल-बेस्ड पैनल्स का नेविगेशन (Updated to 6 Panels Structure)
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
        "📊 5. Dashboard / Counter Panel", # नया काउंटर पैनल
        "⚙️ 6. Admin Panel"                 # एडमिन अब पैनल 6 बन गया है
    ]

panel = st.sidebar.radio("पैनल चुनें:", p_opts)

def process_panel_validation(df_panel, prefix, allowed_degrees, master_rules=None):
    deg_col = next((c for c in df_panel.columns if any(k in c.lower() for k in ['deg', 'course', 'class'])), df_panel.columns[0])
    br_col = next((c for c in df_panel.columns if any(k in c.lower() for k in ['branch', 'stream', 'subject'])), df_panel.columns[0])
    
    def check_degree(val):
        v = str(val).lower().replace(".", "").replace(" ", "").strip()
        return any(d in v for d in allowed_degrees)
        
    df_filtered = df_panel[df_panel[deg_col].apply(check_degree)].reset_index(drop=True)
    
    if df_filtered.empty:
        st.warning(f"⚠️ {prefix.upper()} पैनल के लिए कोई उपयुक्त डेटा (मैचिंग डिग्री) नहीं मिला।")
        return

    minor_col_found = next((c for c in df_filtered.columns if 'minor' in c.lower()), None)
    mdc_col_found = next((c for c in df_filtered.columns if 'mdc' in c.lower()), None)
    voc_col_found = next((c for c in df_filtered.columns if 'voc' in c.lower() or 'skill' in c.lower()), None)
    pw_col_found = next((c for c in df_filtered.columns if any(k in c.lower() for k in ['pw', 'project', 'ce'])), None)

    # --- लाइव वैरिफिकेशन स्टाइलर फ़ंक्शन ---
    def cell_styler(dataframe):
        s_df = pd.DataFrame('', index=dataframe.index, columns=dataframe.columns)
        targets = {minor_col_found: 'minor', mdc_col_found: 'mdc', voc_col_found: 'voc', pw_col_found: 'pw'}
        
        for index, row in dataframe.iterrows():
            student_deg = str(row[deg_col]).lower().replace(".", "").replace(" ", "").strip()
            
            # सही मास्टर रूल की पहचान करना (जैसे bcom computer या bcom)
            matched_key = "Default"
            if master_rules:
                # सबसे पहले बड़े नाम (जैसे bcom computer) को चेक करें ताकि सटीक मैच हो
                sorted_keys = sorted(master_rules.keys(), key=len, reverse=True)
                for rule_key in sorted_keys:
                    rk_clean = rule_key.lower().replace(".", "").replace(" ", "").strip()
                    if rk_clean in student_deg:
                        matched_key = rule_key
                        break
            
            c_rule = master_rules.get(matched_key, {"minor": [], "mdc": [], "voc": [], "pw": []}) if master_rules else {"minor": [], "mdc": [], "voc": [], "pw": []}
            
            # ब्रांच की खाली चेकिंग
            if br_col and br_col in dataframe.columns:
                b_val = row[br_col]
                if pd.isna(b_val) or str(b_val).strip() == "":
                    s_df.at[index, br_col] = 'background-color: #d1ecf1; color: #0c5460; font-weight: bold; border: 1px solid #17a2b8;'
            
            # Minor, MDC, VOC, PW कॉलम्स की लाइव चेकिंग और रेड हाइलाइटिंग
            for col_name, rule_key in targets.items():
                if col_name and col_name in dataframe.columns:
                    val = row[col_name]
                    if pd.isna(val) or str(val).strip() == "":
                        s_df.at[index, col_name] = 'background-color: #d1ecf1; color: #0c5460; font-weight: bold; border: 1px solid #17a2b8;'
                    else:
                        val_clean = str(val).strip().lower()
                        valid_list = c_rule.get(rule_key, [])
                        valid_set = {str(x).strip().lower() for x in valid_list}
                        # अगर मास्टर रूल में विषय सेट हैं और छात्र का विषय उसमें नहीं है, तो लाल करें
                        if valid_set and (val_clean not in valid_set):
                            s_df.at[index, col_name] = 'background-color: #f8d7da; color: #721c24; font-weight: bold; border: 2px solid red;'
        return s_df

    st.subheader(f"📊 लाइव वैरिफाइड {prefix.upper()} डेटा टेबल")
    st.caption("🔵 नीला सेल = डेटा गायब है | 🔴 लाल सेल = गलत विषय (मास्टर गाइडलाइन से मिसमैच)")
    
    st.dataframe(df_filtered.style.apply(cell_styler, axis=None), height=500, use_container_width=True)

    # --- 🚨 नया रंगीन एक्सेल डाउनलोड फीचर 🚨 ---
    import io
    from openpyxl.styles import PatternFill, Border, Side
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_filtered.to_excel(writer, index=False, sheet_name='Verified_Data')
        workbook = writer.book
        worksheet = writer.sheets['Verified_Data']
        
        blue_fill = PatternFill(start_color="D1ECF1", end_color="D1ECF1", fill_type="solid") 
        red_fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")   
        thin_border = Border(left=Side(style='thin', color='CCCCCC'), right=Side(style='thin', color='CCCCCC'),
                             top=Side(style='thin', color='CCCCCC'), bottom=Side(style='thin', color='CCCCCC'))
        
        targets_xl = {minor_col_found: 'minor', mdc_col_found: 'mdc', voc_col_found: 'voc', pw_col_found: 'pw'}
        
        for idx, row in df_filtered.iterrows():
            row_num = idx + 2 
            student_deg = str(row[deg_col]).lower().replace(".", "").replace(" ", "").strip()
            
            matched_key = "Default"
            if master_rules:
                sorted_keys = sorted(master_rules.keys(), key=len, reverse=True)
                for rule_key in sorted_keys:
                    rk_clean = rule_key.lower().replace(".", "").replace(" ", "").strip()
                    if rk_clean in student_deg:
                        matched_key = rule_key
                        break
            c_rule = master_rules.get(matched_key, {"minor": [], "mdc": [], "voc": [], "pw": []}) if master_rules else {"minor": [], "mdc": [], "voc": [], "pw": []}
            
            for col_idx, col_name in enumerate(df_filtered.columns, start=1):
                cell = worksheet.cell(row=row_num, column=col_idx)
                
                if col_name in [br_col, minor_col_found]:
                    val = row[col_name]
                    if pd.isna(val) or str(val).strip() == "":
                        cell.fill = blue_fill
                        cell.border = thin_border
                
                if col_name in targets_xl:
                    val = row[col_name]
                    rule_key = targets_xl[col_name]
                    
                    if pd.isna(val) or str(val).strip() == "":
                        cell.fill = blue_fill
                        cell.border = thin_border
                    else:
                        val_clean = str(val).strip().lower()
                        valid_list = c_rule.get(rule_key, [])
                        valid_set = {str(x).strip().lower() for x in valid_list}
                        if valid_set and (val_clean not in valid_set):
                            cell.fill = red_fill
                            cell.border = thin_border

    processed_data = output.getvalue()
    st.download_button(
        label=f"📥 रंगीन (🔴/🔵) {prefix.upper()} डेटा एक्सेल डाउनलोड करें",
        data=processed_data,
        file_name=f"Verified_{prefix.upper()}_Colored_Data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"download_validated_excel_{prefix}"
    )

# =========================================================================
# 📥 PANEL 1: ENTRY / UPLOAD PANEL (डेटा सुरक्षित अपलोड)
# =========================================================================
if panel == "📥 1. Entry / Upload Panel":
    st.title("📥 Entry Panel - डेटा सुरक्षित अपलोड")
    st.write("यहाँ अपनी मुख्य एक्सेल/CSV फ़ाइल अपलोड करें। यह डेटा सीधे समीक्षा और क्लीनिंग के लिए **Work / Approve Panel (P2)** में ट्रांसफर हो जाएगा।")
    
    # एक्सेल या सीएसवी फ़ाइल अपलोड करने का विकल्प
    f = st.file_uploader("अपनी फ़ाइल अपलोड करें", type=["csv", "xlsx"])
    if f:
        try:
            # फ़ाइल टाइप के अनुसार डेटाबेस में रीड करना (Pandas Dataframe)
            df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
            st.success(f"🎉 फ़ाइल सफलतापूर्वक लोड हो गई ({len(df)} रोज़)!")
            
            # डेटा को P2 में ट्रांसफर करने का बटन
            if st.button("📤 वर्क/अप्रूवल पैनल (P2) में ट्रांसफर करें"):
                # पुराने किसी भी रॉ (Temporary) डेटा को साफ़ करना
                cursor.execute("DELETE FROM raw_store")
                
                # डेटाफ़्रेम को JSON में बदलकर सुरक्षित रूप से अस्थायी डेटाबेस में स्टोर करना
                cursor.execute("INSERT INTO raw_store (data_json) VALUES (?)", (json.dumps(df.to_dict(orient='records')),))
                conn.commit()
                
                # पुराने फ़ाइल के डिलीट किए गए कॉलम्स की सेटिंग्स को रीसेट करना
                st.session_state["deleted_cols"] = [] 
                
                st.success("🎉 डेटा सफलतापूर्वक अपलोड होकर **Work / Approve Panel** में प्रोसेस होने के लिए ट्रांसफर हो गया है!")
                st.balloons()
                st.rerun()
        except Exception as e:
            st.error(f"त्रुटि: {e}")

# =========================================================================
# 💻 PANEL 2: WORK / APPROVE PANEL (कॉलम मूव + लाइव स्प्लिट + डेटाबेस रूटिंग)
# =========================================================================
elif panel == "💻 2. Work / Approve Panel":
    st.title("💻 Work / Approve Panel - डेटा प्रोसेसिंग एवं अप्रूवल")
    
    # Panel 1 से ट्रांसफर होकर आया हुआ Staging (Raw) डेटा लोड करना
    raw_df = load_raw_data()
    
    if raw_df is None or raw_df.empty:
        st.info("📥 वर्तमान में कोई नई अपलोड की गई फ़ाइल पेंडिंग नहीं है। कृपया पहले 'Entry / Upload Panel (P1)' से फ़ाइल अपलोड करें।")
    else:
        # --- कार्य 1: बेकार कॉलम हटाना ---
        st.subheader("🗑️ बेकार कॉलम हटाएं (Remove Unwanted Columns)")
        active_cols = [c for c in raw_df.columns if c not in st.session_state["deleted_cols"]]
        
        cols_to_delete = st.multiselect("हटाने के लिए अनुपयोगी कॉलम चुनें:", options=active_cols)
        if cols_to_delete:
            if st.button("🔴 चुने गए कॉलम हटाएं"):
                st.session_state["deleted_cols"].extend(cols_to_delete)
                st.success("चयनित कॉलम स्क्रीन से हटा दिए गए!")
                st.rerun()
        
        final_raw_df = raw_df[active_cols]

        # --- कार्य 2: 🔄 कॉलमों का क्रम बदलना (Left/Right Move Feature) ---
        st.divider()
        st.subheader("🔄 कॉलमों का क्रम बदलें (Move Columns Left/Right)")
        st.write("नीचे दिए गए बॉक्स में क्रम बदलकर कॉलम को आगे-पीछे सेट करें। अप्रूवल के बाद इसी क्रम में लिस्ट लॉक होगी:")
        
        reordered_cols = st.multiselect(
            "कॉलमों का नया क्रम तय करें (सभी आवश्यक कॉलम इसी क्रम में चुनें):",
            options=active_cols,
            default=active_cols,
            key="col_reorder_select"
        )
        
        missing_cols = [c for c in active_cols if c not in reordered_cols]
        if missing_cols:
            reordered_cols.extend(missing_cols)
            
        final_raw_df = final_raw_df[reordered_cols]
        
        deg_col = next((c for c in final_raw_df.columns if any(k in c.lower() for k in ['deg', 'course', 'class'])), final_raw_df.columns)
        br_col = next((c for c in final_raw_df.columns if any(k in c.lower() for k in ['branch', 'stream', 'subject'])), final_raw_df.columns if len(final_raw_df.columns) > 1 else final_raw_df.columns)
        
        # --- कार्य 3: विशिष्ट डिग्री / ब्रांच की पूरी रो डिलीट करना ---
        st.divider()
        st.subheader("❌ विशिष्ट डिग्री / ब्रांच की पूरी रो डिलीट करें")
        st.write("यदि आप किसी खास कोर्स या स्ट्रीम का पूरा डेटा हटाना चाहते हैं, तो यहाँ से चुनें:")
        
        c_row1, c_row2 = st.columns(2)
        with c_row1:
            unique_degrees = final_raw_df[deg_col].dropna().unique().tolist()
            selected_degs = st.multiselect("डिलीट करने के लिए डिग्री (Course) चुनें:", options=unique_degrees)
        with c_row2:
            unique_branches = final_raw_df[br_col].dropna().unique().tolist()
            selected_branches = st.multiselect("डिलीट करने के लिए ब्रांच (Stream) चुनें:", options=unique_branches)
            
        if selected_degs or selected_branches:
            if st.button("🗑️ चुनी हुई रोज़ हमेशा के लिए डिलीट करें"):
                filtered_rows = []
                for _, row in raw_df.iterrows():
                    match_deg = str(row[deg_col]) in selected_degs if selected_degs else False
                    match_br = str(row[br_col]) in selected_branches if selected_branches else False
                    if not (match_deg or match_br):
                        filtered_rows.append(row.to_dict())
                
                cursor.execute("DELETE FROM raw_store")
                if filtered_rows:
                    cursor.execute("INSERT INTO raw_store (data_json) VALUES (?)", (json.dumps(filtered_rows),))
                conn.commit()
                st.success("🎉  चयनित डिग्री/ब्रांच की सभी रोज़ को सफलतापूर्वक डिलीट कर दिया गया है!")
                st.rerun()

        # फ़िल्टर्ड और रीऑर्डर किए गए डेटा का लाइव प्रीव्यू दिखाना
        st.divider()
        st.subheader("📋 अपलोड किए गए रॉ डेटा का लाइव प्रीव्यू (संशोधित क्रम)")
        st.dataframe(final_raw_df, height=350, use_container_width=True)
        
        el_col = next((c for c in final_raw_df.columns if any(k in c.lower() for k in ['elig', 'qual', 'class', 'course', 'deg'])), final_raw_df.columns)
        st.info(f"🔍 सिस्टम ऑटो-वर्गीकरण के लिए **'{el_col}'** कॉलम का उपयोग कर रहा है।")
        
        st.subheader("👀 लाइव प्री-विभाजन समीक्षा (Live Split Preview)")
        ug_preview_rows = []
        pg_preview_rows = []
        
        for _, row in final_raw_df.iterrows():
            val = str(row[el_col]).lower().replace(".", "").replace(" ", "").strip()
            if any(k in val for k in ["ma", "msc", "mcom", "mba", "mca", "post grad", "pg", "grad"]):
                pg_preview_rows.append(row.to_dict())
            else:
                ug_preview_rows.append(row.to_dict())
                
        df_ug_preview = pd.DataFrame(ug_preview_rows)
        df_pg_preview = pd.DataFrame(pg_preview_rows)
        
        prev_tab1, prev_tab2 = st.tabs([f"🎓 UG में जाने वाला डेटा ({len(df_ug_preview)} रोज़)", f"📜 PG में जाने वाला डेटा ({len(df_pg_preview)} रोज़)"])
        
        with prev_tab1:
            if not df_ug_preview.empty: st.dataframe(df_ug_preview, height=250, use_container_width=True)
            else: st.caption("कोई डेटा UG श्रेणी में नहीं मिला।")
        with prev_tab2:
            if not df_pg_preview.empty: st.dataframe(df_pg_preview, height=250, use_container_width=True)
            else: st.caption("कोई डेटा PG श्रेणी में नहीं मिला।")

        # --- कार्य 4: फाइनल अप्रूवल और रूटिंग एक्शन (नया क्रम डेटाबेस में लॉक होगा) ---
        st.divider()
        st.subheader("🚀 FINAL ACTION")
        st.write("📈 **डेटा ट्रांसफर:** क्लीन और रीऑर्डर किए गए छात्रों के डेटा को आगे UG (P3) और PG (P4) पैनल में भेजने के लिए यह बटन दबाएँ।")
        
        if st.button("✅ डेटा अप्रूव करें और पैनल्स में ट्रांसफर करें"):
            if not df_ug_preview.empty:
                ug_json_str = json.dumps(df_ug_preview[reordered_cols].to_dict(orient='records'))
                cursor.execute("INSERT INTO perma_store (data_json, course_type) VALUES (?, ?)", (ug_json_str, "UG"))
            if not df_pg_preview.empty:
                pg_json_str = json.dumps(df_pg_preview[reordered_cols].to_dict(orient='records'))
                cursor.execute("INSERT INTO perma_store (data_json, course_type) VALUES (?, ?)", (pg_json_str, "PG"))
            
            cursor.execute("DELETE FROM raw_store")
            conn.commit()
            st.success("🎉 बधाई हो! डेटा सफलतापूर्वक कस्टमाइज्ड क्रम में ट्रांसफर और लॉक कर दिया गया है।")
            st.balloons()
            st.rerun()

elif panel == "🎓 3. UG Panel":
    st.title("🎓 Undergraduate (UG) चेकिंग एवं त्रुटि सुधार पैनल")
    df_ug = load_permanent_data("UG")
    
    if df_ug is None or df_ug.empty: 
        st.info("ℹ️ UG डेटाबेस खाली है। कृपया पहले Panel 2 से डेटा अप्रूव करें।")
    else:
        # ऑटो-कॉलम डिटेक्शन
        minor_col = next((c for c in df_ug.columns if 'minor' in c.lower()), None)
        mdc_col = next((c for c in df_ug.columns if 'mdc' in c.lower()), None)
        voc_col = next((c for c in df_ug.columns if 'voc' in c.lower() or 'skill' in c.lower()), None)
        pw_col = next((c for c in df_ug.columns if any(k in c.lower() for k in ['pw', 'project', 'ce'])), None)
        
        # ड्रॉपडाउन में दिखाने के लिए यूनिक लिस्ट
        opt_minor = df_ug[minor_col].dropna().unique().tolist() if minor_col else []
        opt_mdc = df_ug[mdc_col].dropna().unique().tolist() if mdc_col else []
        opt_voc = df_ug[voc_col].dropna().unique().tolist() if voc_col else []
        opt_pw = df_ug[pw_col].dropna().unique().tolist() if pw_col else []
        
        st.markdown("### 🛠️ स्टेप 1: डिग्री-वाइज मास्टर गाइडलाइन सेट करें")
        st.caption("नीचे दी गई प्रत्येक डिग्री के बॉक्स को खोलकर उसके मान्य विषय चुनें और फिर 'लॉक करें' बटन दबाएं।")
        
        # --- डेटाबेस से पहले से सेव नियमों को सुरक्षित लोड करना ---
        ug_master_rules = {}
        try:
            cursor.execute("SELECT rules_json FROM locked_rules WHERE panel_prefix = 'ug_master'")
            locked_row = cursor.fetchone()
            if locked_row and locked_row[0]:
                ug_master_rules = json.loads(locked_row[0])
        except Exception as e:
            pass

        # आपकी मांगी गई 6 विशिष्ट डिग्रियां
        target_degrees = ["BA", "B.Sc.", "B.Sc. Biotechnology", "B.H.Sc.", "B.Com.", "B.Com. Computer"]
        current_configured_rules = {}
        
        for deg in target_degrees:
            with st.expander(f"📘 {deg} के लिए वैध विषय नियम (Valid Subjects)"):
                c1, c2, c3, c4 = st.columns(4)
                
                # पहले से सेव नियमों को ड्रॉपडाउन में डिफ़ॉल्ट दिखाना
                saved_deg_rule = ug_master_rules.get(deg, {})
                default_min = [x for x in saved_deg_rule.get("minor", []) if x in opt_minor]
                default_mdc = [x for x in saved_deg_rule.get("mdc", []) if x in opt_mdc]
                default_voc = [x for x in saved_deg_rule.get("voc", []) if x in opt_voc]
                default_pw = [x for x in saved_deg_rule.get("pw", []) if x in opt_pw]
                
                with c1:
                    r_minor = st.multiselect(f"Valid Minor", opt_minor, default=default_min, key=f"ug_min_{deg}")
                with c2:
                    r_mdc = st.multiselect(f"Valid MDC", opt_mdc, default=default_mdc, key=f"ug_mdc_{deg}")
                with c3:
                    r_voc = st.multiselect(f"Valid Vocational", opt_voc, default=default_voc, key=f"ug_voc_{deg}")
                with c4:
                    r_pw = st.multiselect(f"Valid PW/Ap/CE", opt_pw, default=default_pw, key=f"ug_pw_{deg}")
                    
                current_configured_rules[deg] = {
                    "minor": r_minor,
                    "mdc": r_mdc,
                    "voc": r_voc,
                    "pw": r_pw
                }
        
        # नियमों को डेटाबेस में लॉक करने का बटन
        if st.button("🔒 UG मास्टर विषय नियमावली लॉक करें", key="lock_master_ug_btn"):
            try:
                cursor.execute("""
                    INSERT INTO locked_rules (panel_prefix, rules_json) 
                    VALUES (?, ?)
                    ON CONFLICT(panel_prefix) DO UPDATE SET rules_json = excluded.rules_json
                """, ("ug_master", json.dumps(current_configured_rules)))
                conn.commit()
                st.success("🎉 सभी डिग्रियों के नियम डेटाबेस में सुरक्षित हो गए हैं और नीचे की लिस्ट रंगीन हो गई है!")
                st.rerun()
            except Exception as e:
                st.error(f"त्रुटि: {e}")
            
        st.divider()
        
        # लाइव वैलिडेशन टेबल रन करना (डेटाबेस से लोड किए गए नियमों को प्राथमिकता दें)
        rules_to_apply = ug_master_rules if ug_master_rules else current_configured_rules
        allowed_ug = ["ba", "bsc", "bcom", "bhsc", "bba", "bca", "computer"]
        
        process_panel_validation(df_ug, "ug", allowed_ug, master_rules=rules_to_apply)

# =========================================================================
# 📜 PANEL 4: PG PANEL
# =========================================================================
elif panel == "📜 4. PG Panel":
    st.title("📜 Postgraduate (PG) चेकिंग एवं त्रुटि सुधार पैनल")
    df_pg = load_permanent_data("PG")
    if df_pg is None or df_pg.empty: 
        st.info("ℹ️ PG डेटाबेस खाली है।")
    else: 
        process_panel_validation(df_pg, "pg", ["ma", "msc", "mcom", "mba", "mca", "post grad", "pg", "mtech", "llm"])

# =========================================================================
# 📊 PANEL 5: DASHBOARD / COUNTER PANEL (एडवांस शो-हाइड एवं टॉगल काउंटर लिस्ट)
# =========================================================================
elif panel == "📊 5. Dashboard / Counter Panel":
    st.title("📊 Dashboard - डिग्री-वाइज लाइव काउंटर एवं विस्तृत डेटा समीक्षा")
    st.write("नीचे दिए गए टैब पर क्लिक करके संबंधित डिग्री का लाइव काउंट देखें और उसके ठीक नीचे पूरे छात्र डेटाबेस की समीक्षा करें।")
    
    # UG और PG दोनों का डेटा लोड करना
    df_ug_all = load_permanent_data("UG")
    df_pg_all = load_permanent_data("PG")
    
    all_dfs = []
    if df_ug_all is not None and not df_ug_all.empty: all_dfs.append(df_ug_all)
    if df_pg_all is not None and not df_pg_all.empty: all_dfs.append(df_pg_all)
    
    if not all_dfs:
        st.info("ℹ️ काउंट प्रदर्शित करने के लिए डेटाबेस में कोई डेटा उपलब्ध नहीं है। कृपया पहले Panel 2 से डेटा अप्रूव करें।")
    else:
        master_df = pd.concat(all_dfs, ignore_index=True)
        
        # ऑटो-कॉलम डिटेक्शन इंजन
        deg_col = next((c for c in master_df.columns if any(k in c.lower() for k in ['deg', 'course', 'class'])), None)
        minor_col = next((c for c in master_df.columns if 'minor' in c.lower()), None)
        mdc_col = next((c for c in master_df.columns if 'mdc' in c.lower()), None)
        voc_col = next((c for c in master_df.columns if 'voc' in c.lower() or 'skill' in c.lower()), None)
        pw_col = next((c for c in master_df.columns if any(k in c.lower() for k in ['pw', 'project', 'ce'])), None)
        
        # 🔒 डेटाबेस से UG मास्टर नियमों को सुरक्षित लोड करना
        ug_master_rules = {}
        try:
            cursor.execute("SELECT rules_json FROM locked_rules WHERE panel_prefix = 'ug_master'")
            locked_row = cursor.fetchone()
            if locked_row and locked_row[0]:
                ug_master_rules = json.loads(locked_row[0])
        except:
            pass

        # डिग्रियों की सूची की सटीक मैपिंग
        target_degrees = [
            {"display": "BA", "keywords": ["ba"]},
            {"display": "B.Com.", "keywords": ["bcom"], "exclude": ["computer"]},
            {"display": "B.Sc.", "keywords": ["bsc"], "exclude": ["biotech"]},
            {"display": "B.H.Sc.", "keywords": ["bhsc"]}
        ]

        # सभी डिग्रियों के लिए इंटरएक्टिव टैब्स
        tab_titles = [deg["display"] for deg in target_degrees]
        tabs = st.tabs(tab_titles)

        for index, deg_info in enumerate(target_degrees):
            with tabs[index]:
                st.markdown(f"## 🎓 {deg_info['display']} डैशबोर्ड")
                
                # छात्र सूची में से इस विशिष्ट डिग्री के छात्रों को फ़िल्टर करना
                if deg_col and deg_col in master_df.columns:
                    def match_degree(val):
                        v = str(val).lower().replace(".", "").replace(" ", "").strip()
                        match = all(k in v for k in deg_info["keywords"])
                        if "exclude" in deg_info:
                            if any(ex in v for ex in deg_info["exclude"]):
                                match = False
                        return match
                    
                    df_deg_filtered = master_df[master_df[deg_col].apply(match_degree)].reset_index(drop=True)
                else:
                    df_deg_filtered = pd.DataFrame()

                if df_deg_filtered.empty:
                    st.warning(f"⚠️ डेटाबेस में `{deg_info['display']}` का कोई छात्र रिकॉर्ड नहीं मिला।")
                    continue
                    
                # ---------------------------------------------------------
                # भाग 1: लाइव विषय काउंटर ग्रिड (Show/Hide & Toggle Enabled)
                # ---------------------------------------------------------
                st.markdown("### 📈 विषयों की लाइव स्थिति (Summary Counters)")
                deg_rule = ug_master_rules.get(deg_info['display'], {"minor":[], "mdc":[], "voc":[], "pw":[]})
                
                # 🔒 जादुई बटन: डिफ़ॉल्ट रूप से False (समरी को हमेशा छिपा कर रखेगा)
                show_summary = st.checkbox(
                    "👀 विषय काउंटर समरी दिखाएँ (Show Subject Summary)", 
                    value=False, 
                    key=f"toggle_sum_{deg_info['display']}"
                )
                
                # अगर शो बटन ऑन है, तभी विषय की अलग-अलग लिस्ट और टेबल्स खुलेंगी
                if show_summary:
                    selected_category = st.radio(
                        "समीक्षा के लिए विषय प्रकार चुनें:",
                        options=["Minor (माइनर)", "MDC (एम.डी.सी.)", "Vocational (व्यवसायिक)", "Project/PW (परियोजना)"],
                        horizontal=True,
                        key=f"cat_selector_{deg_info['display']}"
                    )

                    # सिलेक्टेड कैटेगरी के अनुसार कॉलम मैपिंग
                    cat_mapping = {
                        "Minor (माइनर)": {"col_name": minor_col, "rule_key": "minor", "label": "विषय का नाम (Minor Subject)"},
                        "MDC (एम.डी.सी.)": {"col_name": mdc_col, "rule_key": "mdc", "label": "विषय का नाम (MDC Subject)"},
                        "Vocational (व्यवसायिक)": {"col_name": voc_col, "rule_key": "voc", "label": "विषय का नाम (Vocational Subject)"},
                        "Project/PW (परियोजना)": {"col_name": pw_col, "rule_key": "pw", "label": "प्रोजेक्ट प्रकार (Project Type)"}
                    }

                    current_cat = cat_mapping[selected_category]

                    if current_cat["col_name"] and current_cat["col_name"] in df_deg_filtered.columns:
                        counts = df_deg_filtered[current_cat["col_name"]].dropna().value_counts().reset_index()
                        counts.columns = ["Subject", "Count"]
                        
                        if not counts.empty:
                            valid_subjects_set = {str(x).strip().lower() for x in deg_rule.get(current_cat["rule_key"], [])}
                            
                            def row_styler(row):
                                sub_val = str(row["Subject"]).strip().lower()
                                if valid_subjects_set and (sub_val not in valid_subjects_set):
                                    return ['background-color: #f8d7da; color: #721c24; font-weight: bold; border: 1px solid red;'] * len(row)
                                return [''] * len(row)
                            
                            # विस्तृत चौड़ाई वाली साफ़ सिंगल-हेडर टेबल
                            st.dataframe(
                                counts.style.apply(row_styler, axis=1), 
                                hide_index=True, 
                                use_container_width=True,
                                height=220,
                                column_config={
                                    "Subject": st.column_config.TextColumn(label=current_cat["label"], width=500), 
                                    "Count": st.column_config.NumberColumn(label="छात्रों की संख्या (Count)", width=150)
                                }
                            )
                        else:
                            st.caption("इस श्रेणी में कोई डेटा उपलब्ध नहीं है।")
                    else:
                        st.caption("डेटाबेस में संबंधित कॉलम नहीं मिला।")
                else:
                    st.info("ℹ️ काउंटर समरी वर्तमान में छिपी (Hidden) है। देखने के लिए ऊपर दिए गए चेकबॉक्स पर टिक करें।")
                
                st.divider()
                
                # ---------------------------------------------------------
                # भाग 2: विस्तृत छात्र डेटा तालिका (Show/Hide Button Control Enabled)
                # ---------------------------------------------------------
                st.markdown(f"### 📋 {deg_info['display']} के छात्रों का विस्तृत डेटा")
                
                # 🔒 जादुई बटन: डिफ़ॉल्ट रूप से False (यानी छात्रों की लिस्ट हमेशा छिपी रहेगी)
                show_full_list = st.checkbox(
                    f"👀 {deg_info['display']} की पूरी छात्र सूची देखें (Show Student List)", 
                    value=False, 
                    key=f"toggle_list_{deg_info['display']}"
                )
                
                # अगर बटन पर टिक किया गया है (True है), तभी अंदर का सर्च बार और टेबल दिखाई देगी
                if show_full_list:
                    st.write(f"वर्तमान में इस डिग्री में कुल **{len(df_deg_filtered)}** छात्र रिकॉर्ड उपलब्ध हैं।")
                    
                    # लाइव सर्च बार फीचर
                    search_query = st.text_input(
                        f"🔍 {deg_info['display']} डेटा में सर्च करें (नाम, रोल नंबर या विषय डालें):", 
                        key=f"search_{deg_info['display']}"
                    )
                    
                    df_to_show = df_deg_filtered.copy()
                    if search_query:
                        mask = df_to_show.astype(str).apply(lambda row: row.str.contains(search_query, case=False).any(), axis=1)
                        df_to_show = df_to_show[mask]
                    
                    # पूरी टेबल का लाइव मिसमैच स्टाइलर (गलत विषय लाल रंग में चमकेंगे)
                    def full_table_styler(dataframe):
                        s_df = pd.DataFrame('', index=dataframe.index, columns=dataframe.columns)
                        targets = {minor_col: 'minor', mdc_col: 'mdc', voc_col: 'voc', pw_col: 'pw'}
                        
                        for index, row in dataframe.iterrows():
                            for col_name, rule_key in targets.items():
                                if col_name and col_name in dataframe.columns:
                                    val = row[col_name]
                                    if pd.isna(val) or str(val).strip() == "":
                                        s_df.at[index, col_name] = 'background-color: #d1ecf1; color: #0c5460; font-weight: bold;'
                                    else:
                                        val_clean = str(val).strip().lower()
                                        valid_list = deg_rule.get(rule_key, [])
                                        valid_set = {str(x).strip().lower() for x in valid_list}
                                        if valid_set and (val_clean not in valid_set):
                                            s_df.at[index, col_name] = 'background-color: #f8d7da; color: #721c24; font-weight: bold; border: 1px solid red;'
                        return s_df

                    # मुख्य डेटाबेस ग्रिड व्यूअर
                    st.dataframe(
                        df_to_show.style.apply(full_table_styler, axis=None),
                        height=400,
                        use_container_width=True
                    )
                else:
                    # जब बटन बंद होगा, तो यह छोटा सा संदेश दिखेगा और बड़ी लिस्ट छिपी रहेगी
                    st.info(f"ℹ️ {deg_info['display']} छात्र सूची वर्तमान में छिपी (Hidden) है। देखने के लिए ऊपर दिए गए चेकबॉक्स पर टिक करें।")
                                    
# =========================================================================
# ⚙️ PANEL 6: ADMIN PANEL
# =========================================================================
elif panel == "⚙️ 6. Admin Panel":
    st.title("⚙️ Admin Panel - मास्टर डेटाबेस कंट्रोल")
    
    df_ug_download = load_permanent_data("UG")
    df_pg_download = load_permanent_data("PG")
    
    st.subheader("📥 डेटाबेस बैकअप डाउनलोड करें")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🎓 UG डेटा बैकअप")
        if df_ug_download is not None and not df_ug_download.empty:
            st.download_button(
                label="📥 UG डेटा CSV डाउनलोड करें", 
                data=df_ug_download.to_csv(index=False).encode('utf-8'), 
                file_name="Approved_UG_Data_Backup.csv", 
                mime="text/csv"
            )
        else: 
            st.info("UG डेटाबेस खाली है।")
            
    with c2:
        st.markdown("#### 📜 PG डेटा बैकअप")
        if df_pg_download is not None and not df_pg_download.empty:
            st.download_button(
                label="📥 PG डेटा CSV डाउनलोड करें", 
                data=df_pg_download.to_csv(index=False).encode('utf-8'), 
                file_name="Approved_PG_Data_Backup.csv", 
                mime="text/csv"
            )
        else: 
            st.info("PG डेटाबेस खाली है।")

    st.divider()
    st.subheader("🚨 डेंजर ज़ोन")
    confirm_reset = st.checkbox("मैं पूरे सिस्टम (रॉ + अप्रूव्ड दोनों डेटाबेस) को रीसेट करने की पुष्टि करता हूँ।")
    if st.button("💥 ऑल डेटाबेस रीसेट करें"):
        if confirm_reset:
            cursor.execute("DELETE FROM raw_store")
            cursor.execute("DELETE FROM perma_store")
            cursor.execute("DELETE FROM locked_rules") # रीसेट करने पर नियमों की लॉक टेबल भी साफ़ होगी
            conn.commit()
            st.session_state["deleted_cols"] = []
            st.success("सिस्टम पूरी तरह से रीसेट हो गया है!")
            st.rerun()
        else: 
            st.error("कृपया पहले पुष्टि चेकबॉक्स पर टिक करें।")
