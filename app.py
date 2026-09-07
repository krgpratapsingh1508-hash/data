import streamlit as st
import pandas as pd
import sqlite3
import json

st.set_page_config(layout="wide")

# =========================================================================
# परमानेंट डेटाबेस स्टोरेज (डेटा कभी डिलीट नहीं होगा जब तक आप न चाहें)
# =========================================================================
conn = sqlite3.connect("nep_master_perma_db.db", check_same_thread=False)
cursor = conn.cursor()
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
if "hide_setup" not in st.session_state: st.session_state["hide_setup"] = False
if "deleted_cols" not in st.session_state: st.session_state["deleted_cols"] = []

# --- 1. LOGIN SYSTEM WITH PASSWORD 'psv123' ---
if not st.session_state["ok"]:
    st.title("🔒 Login System")
    user = st.selectbox("Username:", ["-- चुनें --", "Admin", "Operator", "Teacher_UG", "Teacher_PG"])
    pas = st.text_input("Password:", type="password")
    if st.button("Login"):
        if (user == "Admin" and pas == "psv123") or (user == "Operator" and pas == "op") or (user == "Teacher_UG" and pas == "ug") or (user == "Teacher_PG" and pas == "pg"):
            st.session_state["ok"] = True
            st.session_state["user"] = user
            st.rerun()
        else: st.error("गलत पासवर्ड! कृपया सही पासवर्ड डालें।")
    st.stop()

# Role Based Panel Display
u = st.session_state["user"]
if u == "Operator":
    p_opts = ["📥 Entry Panel (डेटा अपलोड)"]
elif "Teacher" in u:
    p_opts = ["💻 Work Panel (वर्गीकरण व चेकिंग)"]
else:
    p_opts = ["📥 Entry Panel (डेटा अपलोड)", "💻 Work Panel (वर्गीकरण व चेकिंग)", "⚙️ Admin Panel (मास्टर कंट्रोल)"]

panel = st.sidebar.radio("पैनल चुनें:", p_opts)

# डेटाबेस से परमानेंट डेटा लोड करने का फंक्शन
def load_permanent_data():
    cursor.execute("SELECT data_json, course_type FROM perma_store")
    rows = cursor.fetchall()
    if rows:
        dfs = []
        for r in rows:
            temp_df = pd.DataFrame(json.loads(r[0]))
            temp_df['Course_Category'] = r[1]
            dfs.append(temp_df)
        return pd.concat(dfs, ignore_index=True)
    return None

# =========================================================================
# 📥 ENTRY PANEL (यहाँ सिर्फ अपलोड होगा, कोई चेकिंग या फालतू काम नहीं)
# =========================================================================
if panel == "📥 Entry Panel (डेटा अपलोड)":
    st.title("📥 Entry Panel - डेटा सुरक्षित अपलोड")
    st.write("यहाँ अपनी मुख्य एक्सेल/CSV फ़ाइल अपलोड करें। यह डेटाबेस में हमेशा के लिए सुरक्षित हो जाएगा।")
    
    f = st.file_uploader("अपनी फ़ाइल अपलोड करें", type=["csv", "xlsx"])
    if f:
        try:
            df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
            st.success(f"फ़ाइल लोड हो गई ({len(df)} रोज़)!")
            
            # ऑटोमैटिक UG/PG विभाजन के लिए कॉलम खोजना
            el_col = next((c for c in df.columns if any(k in c.lower() for k in ['elig', 'qual', 'class', 'course'])), df.columns[0])
            
            if st.button("💾 एडमिन डेटाबेस में सुरक्षित सेव करें"):
                # नियमों के अनुसार UG और PG को ऑटो-विभाजित करके सेव करना
                ug_rows, pg_rows = [], []
                
                for _, row in df.iterrows():
                    val = str(row[el_col]).lower().replace(".", "").replace(" ", "").strip()
                    
                    # BA, BSC, BCOM, BHSC या 12th वाले UG में जाएंगे, MA/MSC वाले PG में
                    if "ma" in val or "msc" in val or "mcom" in val or "grad" in val:
                        pg_rows.append(row.to_dict())
                    else:
                        ug_rows.append(row.to_dict())
                
                # डेटाबेस में राइट करना
                if ug_rows:
                    cursor.execute("INSERT INTO perma_store (data_json, course_type) VALUES (?, ?)", (json.dumps(ug_rows), "UG"))
                if pg_rows:
                    cursor.execute("INSERT INTO perma_store (data_json, course_type) VALUES (?, ?)", (json.dumps(pg_rows), "PG"))
                conn.commit()
                
                st.success("🎉 डेटा एडमिन डेटाबेस में हमेशा के लिए सुरक्षित सेव हो गया है!")
                st.balloons()
        except Exception as e:
            st.error(f"त्रुटि: {e}")

# =========================================================================
# 💻 WORK PANEL (UG और PG अलग-अलग, बेकार कॉलम डिलीट और विषय चेकिंग)
# =========================================================================
elif panel == "💻 Work Panel (वर्गीकरण व चेकिंग)":
    st.title("💻 Work Panel - डेटा वर्गीकरण एवं त्रुटि सुधार")
    
    full_df = load_permanent_data()
    
    if full_df is None:
        st.info("ℹ️ डेटाबेस अभी खाली है। कृपया पहले 'Entry Panel' में जाकर फ़ाइल अपलोड करें।")
    else:
        # दो अलग-अलग टैब: UG का UG में, PG का PG में
        tab_ug, tab_pg = st.tabs(["🎓 UNDERGRADUATE (UG) पैनल", "📜 POSTGRADUATE (PG) PANEL"])
        
        # मास्टर फ़िल्टरिंग
        df_ug_master = full_df[full_df['Course_Category'] == 'UG'].drop(columns=['Course_Category']).reset_index(drop=True)
        df_pg_master = full_df[full_df['Course_Category'] == 'PG'].drop(columns=['Course_Category']).reset_index(drop=True)
        
        # --- कोर प्रोसेसिंग फंक्शन ---
        def process_panel_validation(df_panel, prefix, allowed_degrees):
            # १. डिग्री का नाम बिल्कुल सटीक फ़िल्टर करना
            deg_col = next((c for c in df_panel.columns if any(k in c.lower() for k in ['deg', 'course', 'class'])), df_panel.columns[0])
            br_col = next((c for c in df_panel.columns if any(k in c.lower() for k in ['branch', 'stream', 'subject'])), df_panel.columns[1])
            
            def check_degree(val):
                v = str(val).lower().replace(".", "").replace(" ", "").strip()
                return any(d in v for d in allowed_degrees)
                
            df_filtered = df_panel[df_panel[deg_col].apply(check_degree)].reset_index(drop=True)
            
            if df_filtered.empty:
                st.warning("⚠️ इस पैनल के लिए कोई निर्दिष्ट डिग्री डेटा नहीं मिला।")
                return

            # २. 🗑️ बेकार कॉलम हटाने का फीचर (सबसे पहले काम करेगा)
            st.subheader("🗑️ बेकार कॉलम हटाएं (Remove Unwanted Columns)")
            remaining_cols = [c for c in df_filtered.columns if c not in st.session_state["deleted_cols"]]
            df_filtered = df_filtered[remaining_cols]
            
            cols_to_delete = st.multiselect(f"हटाने वाले कॉलम चुनें ({prefix.upper()}):", options=remaining_cols, key=f"del_sel_{prefix}")
            if cols_to_delete:
                if st.button("🔴 चुने गए कॉलम हमेशा के लिए डिलीट करें", key=f"del_btn_{prefix}"):
                    st.session_state["deleted_cols"].extend(cols_to_delete)
                    st.success("कॉलम डिलीट कर दिए गए!")
                    st.rerun()

            # आवश्यक विषय कॉलम खोजना
            minor_col = next((c for c in df_filtered.columns if 'minor' in c.lower()), None)
            mdc_col = next((c for c in df_filtered.columns if 'mdc' in c.lower()), None)
            voc_col = next((c for c in df_filtered.columns if 'voc' in c.lower() or 'skill' in c.lower()), None)
            pw_col = next((c for c in df_filtered.columns if any(k in c.lower() for k in ['pw', 'project', 'ce'])), None)

            # ३. 📋 डिग्री + ब्रांच का लाइव सेटअप तैयार करना
            df_filtered['combo'] = df_filtered[deg_col].astype(str) + " - " + df_filtered[br_col].astype(str)
            unique_combos = df_filtered['combo'].unique().tolist()
            
            st.divider()
            st.subheader("📋 स्टेप 2: डिग्री + ब्रांच के अनुसार सही विषय सेट करें")
            
            # उपलब्ध विकल्पों की सूची पहले से तैयार करना
            opt_mdc = df_filtered[mdc_col].dropna().unique().tolist() if (mdc_col and mdc_col in df_filtered.columns) else []
            opt_voc = df_filtered[voc_col].dropna().unique().tolist() if (voc_col and voc_col in df_filtered.columns) else []
            opt_pw = df_filtered[pw_col].dropna().unique().tolist() if (pw_col and pw_col in df_filtered.columns) else []
            
            rules = {}
            
            # साइड-बाय-साइड लेआउट में डिग्री + ब्रांच के सामने स्क्रॉल लिस्ट बनाना
            for idx, combo in enumerate(unique_combos):
                st.markdown(f"#### 📍 `{combo}`")
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    r_mdc = st.multiselect(f"Valid MDC for {combo}", opt_mdc, key=f"mdc_{prefix}_{idx}")
                with c2:
                    r_voc = st.multiselect(f"Valid Vocational for {combo}", opt_voc, key=f"voc_{prefix}_{idx}")
                with c3:
                    r_pw = st.multiselect(f"Valid PW/Ap/CE for {combo}", opt_pw, key=f"pw_{prefix}_{idx}")
                    
                rules[combo] = {
                    "mdc": {str(x).strip().lower() for x in r_mdc},
                    "voc": {str(x).strip().lower() for x in r_voc},
                    "pw": {str(x).strip().lower() for x in r_pw}
                }

            # ४. 📊 लाइव हाइलाइटिंग स्टाइलर लॉजिक (खाली = ब्लू, गलत = रेड)
            def cell_styler(dataframe):
                s_df = pd.DataFrame('', index=dataframe.index, columns=dataframe.columns)
                targets = {mdc_col: 'mdc', voc_col: 'voc', pw_col: 'pw'}
                
                for index, row in dataframe.iterrows():
                    c_val = str(row[deg_col]) + " - " + str(row[br_col])
                    c_rule = rules.get(c_val, {"mdc":set(), "voc":set(), "pw":set()})
                    
                    # --- यहाँ से आपका कोड शुरू होता है ---
                    for b_col in [br_col, minor_col]:
                        if b_col and b_col in dataframe.columns:
                            b_val = row[b_col]
                            if pd.isna(b_val) or str(b_val).strip() == "":
                                s_df.at[index, b_col] = 'background-color: #d1ecf1; color: #0c5460; font-weight: bold; border: 1px solid #17a2b8;'
                    
                    # MDC, VOC, PW कॉलम्स की चेकिंग
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
            st.caption("🔵 नीला सेल = डेटा गायब है | 🔴 लाल सेल = गलत विषय (मिसमैच)")
            
            display_df = df_filtered.drop(columns=['combo'])
            st.dataframe(display_df.style.apply(cell_styler, axis=None), height=600, use_container_width=True)

                        
