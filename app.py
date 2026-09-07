import streamlit as st
import pandas as pd
import sqlite3
import json

st.set_page_config(layout="wide")

# Database Setup
conn = sqlite3.connect("nep_secure.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS data_store (id INTEGER PRIMARY KEY, js TEXT)")
conn.commit()

# Session States
if "ok" not in st.session_state: st.session_state["ok"] = False
if "hide" not in st.session_state: st.session_state["hide"] = False
if "ug_el" not in st.session_state: st.session_state["ug_el"], st.session_state["pg_el"] = [], []

# 1. LOGIN SYSTEM
if not st.session_state["ok"]:
    st.title("🔒 Login")
    user = st.selectbox("Username:", ["-- चुनें --", "Admin", "Operator", "Teacher_UG", "Teacher_PG"])
    pas = st.text_input("Password:", type="password")
    if st.button("Login"):
        if (user == "Admin" and pas == "psv123") or (user == "Operator" and pas == "op") or (user == "Teacher_UG" and pas == "ug") or (user == "Teacher_PG" and pas == "pg"):
            st.session_state["ok"] = True
            st.session_state["user"] = user
            st.rerun()
        else: st.error("गलत पासवर्ड!")
    st.stop()

# Role Based Panels
u = st.session_state["user"]
p_opts = ["📥 Upload"] if u == "Operator" else (["💻 Work"] if "Teacher" in u else ["📥 Upload", "💻 Work", "⚙️ Admin"])
p = st.sidebar.radio("पैनल", p_opts)

def get_db():
    cursor.execute("SELECT js FROM data_store ORDER BY id DESC LIMIT 1")
    r = cursor.fetchone()
    return pd.DataFrame(json.loads(r[0])) if r else None

# --- UPLOAD PANEL ---
if p == "📥 Upload":
    st.title("📥 Upload Panel")
    f = st.file_uploader("फ़ाइल चुनें", type=["csv", "xlsx"])
    if f and st.button("💾 डेटाबेस में सेव करें"):
        df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
        cursor.execute("INSERT INTO data_store (js) VALUES (?)", (df.to_json(orient="records"),))
        conn.commit()
        st.success("डेटा सुरक्षित सेव हो गया!")

# --- WORK PANEL ---
elif p == "💻 Work":
    st.title("💻 Work Panel")
    df = get_db()
    if df is None: st.info("डेटाबेस खाली है।")
    else:
        el_col = next((c for c in df.columns if 'elig' in c.lower() or 'qual' in c.lower()), df.columns[0])
        u_el = df[el_col].dropna().unique().tolist()
        
        # Hide/Show Setup Box
        if not st.session_state["hide"]:
            st.subheader("⚙️ एलिजिबिलिटी सेट करें")
            c1, c2 = st.columns(2)
            st.session_state["ug_el"] = c1.multiselect("🎓 UG एलिजिबिलिटी:", u_el, default=st.session_state["ug_el"])
            st.session_state["pg_el"] = c2.multiselect("📜 PG एलिजिबिलिटी:", u_el, default=st.session_state["pg_el"])
            if st.button("🔒 लॉक करें और सेटअप छुपाएं") and (st.session_state["ug_el"] or st.session_state["pg_el"]):
                st.session_state["hide"] = True
                st.rerun()
        else:
            if st.button("🔓 सेटअप दोबारा दिखाएं"):
                st.session_state["hide"] = False
                st.rerun()

        if st.session_state["hide"]:
            df_ug = df[df[el_col].isin(st.session_state["ug_el"])].reset_index(drop=True)
            df_pg = df[df[el_col].isin(st.session_state["pg_el"])].reset_index(drop=True)
            
            t1, t2 = st.tabs(["🎓 UG पैनल", "📜 PG पैनल"])
            
            for tab, current_df, key_prefix in [(t1, df_ug, "ug"), (t2, df_pg, "pg")]:
                with tab:
                    if current_df.empty: st.write("डेटा नहीं है।")
                    else:
                        wrongs = {}
                        with st.expander("🔍 गलत सब्जेक्ट चुनने की स्क्रॉल लिस्ट", expanded=True):
                            grid = st.columns(4)
                            for idx, name in enumerate(current_df.columns):
                                with grid[idx % 4]:
                                    sel = st.multiselect(f"`{name}` में गलत:", current_df[name].dropna().unique().tolist(), key=f"{key_prefix}_{name}")
                                    if sel: wrongs[name] = sel
                        
                        def style_cells(dataframe):
                            s_df = pd.DataFrame('', index=dataframe.index, columns=dataframe.columns)
                            for col in dataframe.columns:
                                if col in wrongs:
                                    s_df[col] = dataframe[col].apply(lambda x: 'background-color: #ffcccc; color: #cc0000; font-weight: bold; border: 2px solid red;' if x in wrongs[col] else '')
                            return s_df
                        st.dataframe(current_df.style.apply(style_cells, axis=None), height=500, use_container_width=True)

# --- ADMIN PANEL ---
elif p == "⚙️ Admin":
    st.title("⚙️ Admin Control")
    df = get_db()
    if df is not None:
        st.write(f"डेटाबेस में कुल रिकॉर्ड्स: {len(df)}")
        if st.text_input("डिलीट करने के लिए पासवर्ड डालें:", type="password") == "psv123" and st.button("🔴 डेटाबेस साफ करें"):
            cursor.execute("DELETE FROM data_store")
            conn.commit()
            st.success("डेटा डिलीट हो गया!")
            st.rerun()
