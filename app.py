import streamlit as st
import pandas as pd
import numpy as np

# Page configuration
st.set_page_config(page_title="Data Validation System", layout="wide")

st.title("📊 Data Validation & Error Detector System")
st.write("अपनी फ़ाइल अपलोड करें, हर कॉलम के नियम एक बार में सेट करें और गलत डेटा तुरंत देखें।")

# 1. File Upload Component
uploaded_file = st.file_uploader("CSV या Excel फ़ाइल अपलोड करें", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        # File type checking
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.success("फ़ाइल सफलतापूर्वक अपलोड हो गई है!")
        
        # Display Original Data
        st.subheader("📋 आपका अपलोड किया गया डेटा:")
        st.dataframe(df.head(20)) # Shows first 20 rows
        
        st.divider()
        
        # 2. Rule Settings Section (एक ही बार में सब कॉलम सेट करने के लिए)
        st.subheader("⚙️ कॉलम के नियम सेट करें (Validation Rules)")
        st.write("बताएं कि किस कॉलम में क्या डेटा नहीं होना चाहिए या क्या होना चाहिए:")
        
        rules = {}
        columns = df.columns.tolist()
        
        # Create columns layout for rules input
        cols = st.columns(3) # 3 columns grid for configuration
        
        for i, col in enumerate(columns):
            with cols[i % 3]:
                st.markdown(f"**ק कॉलम: `{col}`**")
                rule_type = st.selectbox(
                    f"नियम चुनें ({col})",
                    ["कोई नियम नहीं", "खाली (Missing/Null) नहीं होना चाहिए", "सिर्फ नंबर (Numeric) होना चाहिए", "Text होना चाहिए", "कस्टम वैल्यू नहीं होनी चाहिए"],
                    key=f"rule_{col}"
                )
                
                custom_val = None
                if rule_type == "कस्टम वैल्यू नहीं होनी चाहिए":
                    custom_val = st.text_input(f"कौन सी वैल्यू नहीं होनी चाहिए? (उदा: Invalid, 0)", key=f"val_{col}")
                
                rules[col] = {"type": rule_type, "custom_val": custom_val}
        
        st.divider()
        
        # 3. Check Validation Button
        if st.button("🔴 गलत डेटा चेक करें (Run Validation)"):
            st.subheader("🔍 वैलिडेशन रिपोर्ट (Validation Report)")
            
            error_records = []
            
            # Row-by-row and Column-by-column check
            for index, row in df.iterrows():
                for col in columns:
                    val = row[col]
                    rule = rules[col]["type"]
                    c_val = rules[col]["custom_val"]
                    
                    is_error = False
                    reason = ""
                    
                    # Rule 1: Missing values
                    if rule == "खाली (Missing/Null) नहीं होना चाहिए":
                        if pd.isna(val) or str(val).strip() == "":
                            is_error = True
                            reason = "यह वैल्यू खाली है।"
                            
                    # Rule 2: Must be numeric
                    elif rule == "सिर्फ नंबर (Numeric) होना चाहिए":
                        if pd.isna(val):
                            is_error = True
                            reason = "नंबर होना चाहिए था पर खाली है।"
                        else:
                            try:
                                float(val)
                            except ValueError:
                                is_error = True
                                reason = f"यह Text है (`{val}`), जबकि नंबर होना चाहिए था।"
                                
                    # Rule 3: Must be Text (Not pure number)
                    elif rule == "Text होना चाहिए":
                        if not pd.isna(val) and str(val).strip() != "":
                            # If it's fully numeric, it's an error
                            if str(val).replace('.', '', 1).isdigit():
                                is_error = True
                                reason = f"यह नंबर है (`{val}`), जबकि Text होना चाहिए था।"
                                
                    # Rule 4: Custom incorrect values
                    elif rule == "कस्टम वैल्यू नहीं होनी चाहिए" and c_val:
                        if str(val).strip().lower() == str(c_val).strip().lower():
                            is_error = True
                            reason = f"आपने इस वैल्यू (`{c_val}`) को गलत बताया था।"
                    
                    # Append error if found
                    if is_error:
                        error_records.append({
                            "Row Number": index + 2, # +2 matches Excel/CSV row format
                            "Column Name": col,
                            "Wrong Value": val,
                            "Reason/Error": reason
                        })
            
            # Show Results
            if len(error_records) > 0:
                error_df = pd.DataFrame(error_records)
                st.error(f"कुल {len(error_df)} गलतियाँ (Errors) मिलीं!")
                st.dataframe(error_df)
                
                # Option to download error report
                csv_error = error_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 एरर रिपोर्ट डाउनलोड करें", csv_error, "error_report.csv", "text/csv")
            else:
                st.success("🎉 बधाई हो! आपके नियमों के हिसाब से डेटा में कोई गलती नहीं मिली।")
                
    except Exception as e:
        st.error(f"फ़ाइल पढ़ने में कोई समस्या आई: {e}")
