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

# 3. परमानेंट नियम लॉकिंग स्टोरेज (डेटा डिलीट होने पर भी ड्रॉपडाउन डिब्बे भरे रखने के लिए)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS locked_rules (
        panel_prefix TEXT PRIMARY KEY,
        rules_json TEXT
    )
""")

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

def (df_panel, prefix, allowed_degrees):
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

    df_filtered['combo'] = df_filtered[deg_col].astype(str) + " - " + df_filtered[br_col].astype(str)
    unique_combos = df_filtered['combo'].unique().tolist()
    
    st.subheader("📋 स्टेप 1: डिग्री + ब्रांच के अनुसार सही विषय सेट करें")
    
    opt_minor = df_filtered[minor_col_found].dropna().unique().tolist() if minor_col_found else []
    opt_mdc = df_filtered[mdc_col_found].dropna().unique().tolist() if mdc_col_found else []
    opt_voc = df_filtered[voc_col_found].dropna().unique().tolist() if voc_col_found else []
    opt_pw = df_filtered[pw_col_found].dropna().unique().tolist() if pw_col_found else []
    
    # --- BA और B.Sc. के लिए Minor, MDC और Vocational मास्टर सिंक स्टेट मैनेजमेंट ---
    ba_minor_sync_key = f"ba_minor_sync_{prefix}"
    ba_mdc_sync_key = f"ba_mdc_sync_{prefix}"
    ba_voc_sync_key = f"ba_voc_sync_{prefix}"
    
    bsc_minor_sync_key = f"bsc_minor_sync_{prefix}"
    bsc_mdc_sync_key = f"bsc_mdc_sync_{prefix}"
    bsc_voc_sync_key = f"bsc_voc_sync_{prefix}"
    
    # 🔒 सुरक्षित डेटाबेस कॉल (ताकि एरर आने पर ऐप क्रैश न हो)
    saved_rules = {}
    try:
        cursor.execute("SELECT rules_json FROM locked_rules WHERE panel_prefix = ?", (prefix,))
        locked_row = cursor.fetchone()
        if locked_row and locked_row[0]:
            saved_rules = json.loads(locked_row[0])
    except sqlite3.OperationalError:
        pass # अगर टेबल लॉक या गायब हो तो एरर स्किप करें

    if ba_minor_sync_key not in st.session_state: st.session_state[ba_minor_sync_key] = saved_rules.get("ba_minor", [])
    if ba_mdc_sync_key not in st.session_state: st.session_state[ba_mdc_sync_key] = saved_rules.get("ba_mdc", [])
    if ba_voc_sync_key not in st.session_state: st.session_state[ba_voc_sync_key] = saved_rules.get("ba_voc", [])
    
    if bsc_minor_sync_key not in st.session_state: st.session_state[bsc_minor_sync_key] = saved_rules.get("bsc_minor", [])
    if bsc_mdc_sync_key not in st.session_state: st.session_state[bsc_mdc_sync_key] = saved_rules.get("bsc_mdc", [])
    if bsc_voc_sync_key not in st.session_state: st.session_state[bsc_voc_sync_key] = saved_rules.get("bsc_voc", [])

    rules = {}
    
    has_ba = any("ba-" in combo.lower().replace(".", "").replace(" ", "") or combo.lower().startswith("ba ") for combo in unique_combos)
    has_bsc = any("bsc" in combo.lower().replace(".", "").replace(" ", "") for combo in unique_combos)
    
    if has_ba or has_bsc:
        st.info("💡 **मास्टर सिंक नियम सक्रिय:** आप किसी भी BA या B.Sc. कोर्स का Minor, MDC या Vocational बदलेंगे, वह उस डिग्री के सभी कोर्सेस पर एक साथ स्वचालित रूप से लागू हो जाएगा।")
    
    for idx, combo in enumerate(unique_combos):
        st.markdown(f"#### 📍 `{combo}`")
        
        combo_lower = combo.lower().replace(".", "").replace(" ", "")
        is_ba_course = "ba-" in combo_lower or (combo_lower.startswith("ba") and not combo_lower.startswith("ba(ex") and "bsc" not in combo_lower and "bcom" not in combo_lower)
        is_bsc_course = "bsc" in combo_lower
        
        # --- सख्त डिफ़ॉल्ट नियम (सभी सामान्य कोर्सेस के लिए केवल Project Work) ---
        default_pw_selection = [x for x in opt_pw if str(x).strip().lower() in ["project work", "project", "pw", "project-work (pw)"]]
        if not default_pw_selection:
            default_pw_selection = [x for x in opt_pw if 'project' in str(x).lower() and 'research' not in str(x).lower()]

        # --- विशेष नियम: केवल B.Sc. Biotechnology के लिए इंटर्नशिप छूट ---
        if is_bsc_course and "biotech" in combo_lower:
            internship_opts = [x for x in opt_pw if 'intern' in str(x).lower()]
            default_pw_selection.extend(internship_opts)
            default_pw_selection = list(set(default_pw_selection))
            
        # --- 4 कॉलम्स का सटीक लेआउट (सारे डुप्लीकेट ब्लॉक्स हटा दिए गए हैं) ---
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            if is_ba_course:
                r_minor = st.multiselect(f"Valid Minor for {combo}", opt_minor, default=st.session_state[ba_minor_sync_key], key=f"minor_sync_{prefix}_{idx}")
                if r_minor != st.session_state[ba_minor_sync_key]:
                    st.session_state[ba_minor_sync_key] = r_minor
                    st.rerun()
            elif is_bsc_course:
                r_minor = st.multiselect(f"Valid Minor for {combo}", opt_minor, default=st.session_state[bsc_minor_sync_key], key=f"minor_sync_{prefix}_{idx}")
                if r_minor != st.session_state[bsc_minor_sync_key]:
                    st.session_state[bsc_minor_sync_key] = r_minor
                    st.rerun()
            else:
                r_minor = st.multiselect(f"Valid Minor for {combo}", opt_minor, key=f"minor_sync_{prefix}_{idx}")
                
        with c2:
            if is_ba_course:
                r_mdc = st.multiselect(f"Valid MDC for {combo}", opt_mdc, default=st.session_state[ba_mdc_sync_key], key=f"mdc_sync_{prefix}_{idx}")
                if r_mdc != st.session_state[ba_mdc_sync_key]:
                    st.session_state[ba_mdc_sync_key] = r_mdc
                    st.rerun()
            elif is_bsc_course:
                r_mdc = st.multiselect(f"Valid MDC for {combo}", opt_mdc, default=st.session_state[bsc_mdc_sync_key], key=f"mdc_sync_{prefix}_{idx}")
                if r_mdc != st.session_state[bsc_mdc_sync_key]:
                    st.session_state[bsc_mdc_sync_key] = r_mdc
                    st.rerun()
            else:
                r_mdc = st.multiselect(f"Valid MDC for {combo}", opt_mdc, key=f"mdc_sync_{prefix}_{idx}")
                
        with c3:
            if is_ba_course:
                r_voc = st.multiselect(f"Valid Vocational for {combo}", opt_voc, default=st.session_state[ba_voc_sync_key], key=f"voc_sync_{prefix}_{idx}")
                if r_voc != st.session_state[ba_voc_sync_key]:
                    st.session_state[ba_voc_sync_key] = r_voc
                    st.rerun()
            elif is_bsc_course:
                r_voc = st.multiselect(f"Valid Vocational for {combo}", opt_voc, default=st.session_state[bsc_voc_sync_key], key=f"voc_sync_{prefix}_{idx}")
                if r_voc != st.session_state[bsc_voc_sync_key]:
                    st.session_state[bsc_voc_sync_key] = r_voc
                    st.rerun()
            else:
                r_voc = st.multiselect(f"Valid Vocational for {combo}", opt_voc, key=f"voc_sync_{prefix}_{idx}")
                
        with c4:
            r_pw = st.multiselect(f"Valid PW/Ap/CE for {combo}", opt_pw, default=default_pw_selection, key=f"pw_sync_{prefix}_{idx}")
            
        # नियमों को सुरक्षित रूप से मैप करें
        rules[combo] = {
            "minor": {str(x).strip().lower() for x in r_minor},
            "mdc": {str(x).strip().lower() for x in r_mdc},
            "voc": {str(x).strip().lower() for x in r_voc},
            "pw": {str(x).strip().lower() for x in r_pw}
        }

    # --- 🔒 P3/P4 के लिए नियम लॉक करने का परमानेंट बटन ---
    st.divider()
    st.markdown(f"### 🔒 {prefix.upper()} विषय गाइडलाइन हमेशा के लिए सुरक्षित करें")
    if st.button(f"🔒 {prefix.upper()} पैनल के सभी विषय नियम लॉक करें", key=f"lock_btn_{prefix}"):
        master_rules = {
            "ba_minor": st.session_state.get(ba_minor_sync_key, []),
            "ba_mdc": st.session_state.get(ba_mdc_sync_key, []),
            "ba_voc": st.session_state.get(ba_voc_sync_key, []),
            "bsc_minor": st.session_state.get(bsc_minor_sync_key, []),
            "bsc_mdc": st.session_state.get(bsc_mdc_sync_key, []),
            "bsc_voc": st.session_state.get(bsc_voc_sync_key, [])
        }
        cursor.execute("INSERT OR REPLACE INTO locked_rules (panel_prefix, rules_json) VALUES (?, ?)", (prefix, json.dumps(master_rules)))
        conn.commit()
        st.success(f"🎉 आपके चुने हुए ड्रॉपडाउन विषय डेटाबेस में लॉक हो गए! अब छात्र सूची डिलीट होने पर भी विषय गायब नहीं होंगे।")
        st.balloons()

    # --- डेटाबेस से पुराने लॉक किए गए नियमों को डिफ़ॉल्ट रूप से स्वतः भरने का लॉजिक ---
    cursor.execute("SELECT rules_json FROM locked_rules WHERE panel_prefix = ?", (prefix,))
    locked_row = cursor.fetchone()
    if locked_row and locked_row[0]:
        try:
            saved_rules = json.loads(locked_row[0])
            # अगर सेशन स्टेट अभी खाली है, तो डेटाबेस से लॉक विषय स्वतः भर जाएँगे
            if not st.session_state[ba_minor_sync_key] and saved_rules.get("ba_minor"): st.session_state[ba_minor_sync_key] = saved_rules["ba_minor"]
            if not st.session_state[ba_mdc_sync_key] and saved_rules.get("ba_mdc"): st.session_state[ba_mdc_sync_key] = saved_rules["ba_mdc"]
            if not st.session_state[ba_voc_sync_key] and saved_rules.get("ba_voc"): st.session_state[ba_voc_sync_key] = saved_rules["ba_voc"]
            
            if not st.session_state[bsc_minor_sync_key] and saved_rules.get("bsc_minor"): st.session_state[bsc_minor_sync_key] = saved_rules["bsc_minor"]
            if not st.session_state[bsc_mdc_sync_key] and saved_rules.get("bsc_mdc"): st.session_state[bsc_mdc_sync_key] = saved_rules["bsc_mdc"]
            if not st.session_state[bsc_voc_sync_key] and saved_rules.get("bsc_voc"): st.session_state[bsc_voc_sync_key] = saved_rules["bsc_voc"]
        except:
            pass

    # --- लाइव वैरिफिकेशन स्टाइलर फ़ंक्शन ---
    def cell_styler(dataframe):
        s_df = pd.DataFrame('', index=dataframe.index, columns=dataframe.columns)
        targets = {minor_col_found: 'minor', mdc_col_found: 'mdc', voc_col_found: 'voc', pw_col_found: 'pw'}
        
        for index, row in dataframe.iterrows():
            c_val = str(row[deg_col]) + " - " + str(row[br_col])
            c_rule = rules.get(c_val, {"minor":set(), "mdc":set(), "voc":set(), "pw":set()})
            
            # ब्रांच की खाली चेकिंग
            if br_col and br_col in dataframe.columns:
                b_val = row[br_col]
                if pd.isna(b_val) or str(b_val).strip() == "":
                    s_df.at[index, br_col] = 'background-color: #d1ecf1; color: #0c5460; font-weight: bold; border: 1px solid #17a2b8;'
            
            # Minor, MDC, VOC, PW कॉलम्स की सटीक चेकिंग और लाइव हाइलाइटिंग
            for col_name, rule_key in targets.items():
                if col_name and col_name in dataframe.columns:
                    val = row[col_name]
                    # 🔵 नीला सेल = डेटा गायब है
                    if pd.isna(val) or str(val).strip() == "":
                        s_df.at[index, col_name] = 'background-color: #d1ecf1; color: #0c5460; font-weight: bold; border: 1px solid #17a2b8;'
                    # 🔴 लाल सेल = गलत विषय (वैध सूची में न होने पर तुरंत लाल होगा)
                    else:
                        val_clean = str(val).strip().lower()
                        valid_set = c_rule[rule_key]
                        if val_clean not in valid_set:
                            s_df.at[index, col_name] = 'background-color: #f8d7da; color: #721c24; font-weight: bold; border: 2px solid red;'
        return s_df

    st.divider()
    st.subheader(f"📊 स्टेप 2: लाइव वैरिफाइड {prefix.upper()} डेटा टेबल")
    st.caption("🔵 नीला सेल = डेटा गायब है | 🔴 लाल सेल = गलत विषय (मिसमैच)")
    
    display_df = df_filtered.drop(columns=['combo'])
    st.dataframe(display_df.style.apply(cell_styler, axis=None), height=600, use_container_width=True)

    # --- 🚨 नया रंगीन एक्सेल डाउनलोड फीचर 🚨 ---
    st.caption(f"💡 **टिप:** रंगीन (🔴/🔵) फ़ाइल डाउनलोड करने के लिए नीचे दिए गए बटन से एक्सेल फ़ाइल डाउनलोड करें।")
    
    import io
    from openpyxl.styles import PatternFill, Border, Side
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        display_df.to_excel(writer, index=False, sheet_name='Verified_Data')
        workbook = writer.book
        worksheet = writer.sheets['Verified_Data']
        
        # स्क्रीन वाले सेम रंगों के फिलर (Hex Colors)
        blue_fill = PatternFill(start_color="D1ECF1", end_color="D1ECF1", fill_type="solid") # 🔵 गायब डेटा
        red_fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")   # 🔴 गलत विषय
        thin_border = Border(left=Side(style='thin', color='CCCCCC'), right=Side(style='thin', color='CCCCCC'),
                             top=Side(style='thin', color='CCCCCC'), bottom=Side(style='thin', color='CCCCCC'))
        
        targets_xl = {minor_col_found: 'minor', mdc_col_found: 'mdc', voc_col_found: 'voc', pw_col_found: 'pw'}
        
        for idx, row in display_df.iterrows():
            row_num = idx + 2 # हेडर छोड़ने के लिए +2
            c_val = str(row[deg_col]) + " - " + str(row[br_col])
            c_rule = rules.get(c_val, {"minor":set(), "mdc":set(), "voc":set(), "pw":set()})
            
            for col_idx, col_name in enumerate(display_df.columns, start=1):
                cell = worksheet.cell(row=row_num, column=col_idx)
                
                # ब्रांच और माइनर कॉलम्स की खाली चेकिंग
                if col_name in [br_col, minor_col_found]:
                    val = row[col_name]
                    if pd.isna(val) or str(val).strip() == "":
                        cell.fill = blue_fill
                        cell.border = thin_border
                
                # MDC, VOC, PW कॉलम्स के मिसमैच को लाल/नीला करना
                if col_name in targets_xl:
                    val = row[col_name]
                    rule_key = targets_xl[col_name]
                    
                    if pd.isna(val) or str(val).strip() == "":
                        cell.fill = blue_fill
                        cell.border = thin_border
                    else:
                        val_clean = str(val).strip().lower()
                        valid_set = c_rule[rule_key]
                        if val_clean not in valid_set:
                            cell.fill = red_fill
                            cell.border = thin_border

    processed_data = output.getvalue()

    # रंगीन एक्सेल शीट डाउनलोड करने का फाइनल बटन
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
        
        # ड्रॉपडाउन में दिखाने के लिए यूनीक लिस्ट
        opt_minor = df_ug[minor_col].dropna().unique().tolist() if minor_col else []
        opt_mdc = df_ug[mdc_col].dropna().unique().tolist() if mdc_col else []
        opt_voc = df_ug[voc_col].dropna().unique().tolist() if voc_col else []
        opt_pw = df_ug[pw_col].dropna().unique().tolist() if pw_col else []
        
        st.markdown("### 🛠️ स्टेप 1: डिग्री-वाइज मास्टर गाइडलाइन सेट करें")
        st.caption("नीचे दी गई प्रत्येक डिग्री के बॉक्स को खोलकर उसके मान्य विषय चुनें और फिर 'लॉक करें' बटन दबाएं।")
        
        # डेटाबेस से पहले से सेव नियमों को लोड करना
        ug_master_rules = {}
        try:
            cursor.execute("SELECT rules_json FROM locked_rules WHERE panel_prefix = 'ug_master'")
            locked_row = cursor.fetchone()
            if locked_row and locked_row[0]:
                ug_master_rules = json.loads(locked_row[0])
        except:
            pass

        # आपकी मांगी गई 5 विशिष्ट डिग्रियां
        target_degrees = ["BA", "B.Sc.", "B.H.Sc.", "B.Com.", "B.Com. Computer"]
        current_configured_rules = {}
        
        for deg in target_degrees:
            with st.expander(f"📘 {deg} के लिए वैध विषय नियम (Valid Subjects)"):
                c1, c2, c3, c4 = st.columns(4)
                
                saved_deg_rule = ug_master_rules.get(deg, {})
                
                with c1:
                    r_minor = st.multiselect(f"Valid Minor", opt_minor, default=saved_deg_rule.get("minor", []), key=f"ug_min_{deg}")
                with c2:
                    r_mdc = st.multiselect(f"Valid MDC", opt_mdc, default=saved_deg_rule.get("mdc", []), key=f"ug_mdc_{deg}")
                with c3:
                    r_voc = st.multiselect(f"Valid Vocational", opt_voc, default=saved_deg_rule.get("voc", []), key=f"ug_voc_{deg}")
                with c4:
                    r_pw = st.multiselect(f"Valid PW/Ap/CE", opt_pw, default=saved_deg_rule.get("pw", []), key=f"ug_pw_{deg}")
                    
                current_configured_rules[deg] = {
                    "minor": r_minor,
                    "mdc": r_mdc,
                    "voc": r_voc,
                    "pw": r_pw
                }
        
        # नियमों को डेटाबेस में हमेशा के लिए लॉक करने का बटन
        if st.button("🔒 UG मास्टर विषय नियमावली लॉक करें", key="lock_master_ug_btn"):
            cursor.execute("INSERT OR REPLACE INTO locked_rules (panel_prefix, rules_json) VALUES (?, ?)", 
                           ("ug_master", json.dumps(current_configured_rules)))
            conn.commit()
            st.success("🎉 सभी डिग्रियों (BA, B.Sc, B.Com आदि) के नियम डेटाबेस में सुरक्षित हो गए हैं!")
            st.rerun()
            
        st.divider()
        
        # लाइव वैलिडेशन टेबल रन करना
        allowed_ug = ["ba", "bsc", "bcom", "bhsc", "bba", "bca", "computer"]
        process_panel_validation(df_ug, "ug", allowed_ug, master_rules=current_configured_rules)

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
# 📊 NEW PANEL 5: DASHBOARD / COUNTER PANEL (Minor, MDC, Voc, PW Count Engine)
# =========================================================================
elif panel == "📊 5. Dashboard / Counter Panel":
    st.title("📊 Dashboard - कुल कोर्सेस एवं विषयों की लाइव संख्या")
    st.write("यहाँ आपके डेटाबेस (UG + PG दोनों मिलाकर) में उपयोग हो रहे सभी अनूठे (Unique) विषयों और कोर्सेस की वास्तविक कुल संख्या प्रदर्शित हो रही है:")
    
    # दोनों डेटाबेसों को मिलाकर कंबाइंड मास्टर डेटाफ़्रेम तैयार करना
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
        c_br = next((c for c in master_df.columns if any(k in c.lower() for k in ['branch', 'stream', 'subject'])), None)
        c_minor = next((c for c in master_df.columns if 'minor' in c.lower()), None)
        c_mdc = next((c for c in master_df.columns if 'mdc' in c.lower()), None)
        c_voc = next((c for c in master_df.columns if 'voc' in c.lower() or 'skill' in c.lower()), None)
        c_pw = next((c for c in master_df.columns if any(k in c.lower() for k in ['pw', 'project', 'ce'])), None)
        
        # यूनीक वैल्यूज की गणना करना
        count_br = master_df[c_br].dropna().nunique() if c_br else 0
        count_minor = master_df[c_minor].dropna().nunique() if c_minor else 0
        count_mdc = master_df[c_mdc].dropna().nunique() if c_mdc else 0
        count_voc = master_df[c_voc].dropna().nunique() if c_voc else 0
        count_pw = master_df[c_pw].dropna().nunique() if c_pw else 0
        
        # 📈 विज़ुअल काउंटर मेट्रिक्स रेंडर करना
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1: st.metric(label="🌟 कुल अनूठी ब्रांचेस (Total Unique Branches)", value=f"{count_br}")
        with col2: st.metric(label="📘 कुल अनूठे माइनर विषय (Unique Minor Subjects)", value=f"{count_minor}")
        with col3: st.metric(label="📙 कुल अनूठे एमडीसी विषय (Unique MDC Subjects)", value=f"{count_mdc}")
        
        st.divider()
        col4, col5 = st.columns(2)
        with col4: st.metric(label="🛠️ कुल अनूठे वोकेशनल विषय (Unique Vocational Subjects)", value=f"{count_voc}")
        with col5: st.metric(label="🔬 कुल अनूठे प्रोजेक्ट/CE प्रकार (Unique PW/Ap/CE)", value=f"{count_pw}")
        
        # सूचियों का लाइव विवरण दिखाना (Tabs के अंदर)
        st.divider()
        st.subheader("📋 उपयोग हो रहे सभी विषयों की लाइव मास्टर लिस्ट")
        tab_br, tab_mn, tab_md, tab_vc, tab_p = st.tabs(["Branches", "Minor List", "MDC List", "Vocational List", "Project List"])
        
        with tab_br: 
            if c_br: st.write(master_df[c_br].dropna().unique().tolist())
        with tab_mn: 
            if c_minor: st.write(master_df[c_minor].dropna().unique().tolist())
        with tab_md: 
            if c_mdc: st.write(master_df[c_mdc].dropna().unique().tolist())
        with tab_vc: 
            if c_voc: st.write(master_df[c_voc].dropna().unique().tolist())
        with tab_p: 
            if c_pw: st.write(master_df[c_pw].dropna().unique().tolist())

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
