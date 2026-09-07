import streamlit as st
import pandas as pd

# Page configuration
st.set_page_config(page_title="Data Validation System", layout="wide")

st.title("📊 Data Validation & Error Detector")
st.write("अपनी फ़ाइल अपलोड करें, स्क्रॉल लिस्ट से गलत (Missing Data) वाले कॉलम चुनें और तुरंत रिपोर्ट देखें।")

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
        st.subheader("📋 आपका अपलोड किया गया डेटा (शुरुआती 20 रो):")
        st.dataframe(df.head(20))
        
        st.divider()
        
        # 2. Scroll List (Multiselect Box) for selecting wrong columns
        st.subheader("🔍 गलत डेटा वाले कॉलम चुनें")
        columns_list = df.columns.tolist()
        
        # यह वो स्क्रॉल लिस्ट है जहाँ आप एक ही बार में कई कॉलम चुन सकते हैं
        wrong_columns = st.multiselect(
            "नीचे दी गई लिस्ट में से उन कॉलम्स को चुनें जिनमें खाली (Missing/Null) डेटा नहीं होना चाहिए:",
            options=columns_list,
            placeholder="यहाँ क्लिक करके कॉलम चुनें..."
        )
        
        st.divider()
        
        # 3. Dynamic Validation Process
        if wrong_columns:
            st.subheader("🔴 मिली हुई गलतियों की रिपोर्ट:")
            
            error_records = []
            
            # सिर्फ चुने हुए कॉलम्स में चेकिंग
            for index, row in df.iterrows():
                for col in wrong_columns:
                    val = row[col]
                    
                    # चेक कर रहा है कि डेटा खाली, NaN या सिर्फ स्पेस तो नहीं है
                    if pd.isna(val) or str(val).strip() == "":
                        error_records.append({
                            "Excel Row Number": index + 2, # Excel format row counting
                            "Column Name": col,
                            "Status": "डेटा गायब (Missing/Null) है"
                        })
            
            # अगर गलतियां मिलती हैं
            if len(error_records) > 0:
                error_df = pd.DataFrame(error_records)
                st.error(f"आपके चुने गए कॉलम्स में कुल {len(error_df)} जगह पर डेटा गलत/खाली मिला!")
                
                # एरर डेटा टेबल दिखाएं
                st.dataframe(error_df, use_container_width=True)
                
                # डाउनलोड बटन
                csv_error = error_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 एरर रिपोर्ट डाउनलोड करें", csv_error, "missing_data_report.csv", "text/csv")
            else:
                st.success("🎉 बहुत बढ़िया! आपके चुने हुए कॉलम्स में कोई भी डेटा खाली या गलत नहीं है।")
        else:
            st.info("💡 ऊपर दी गई स्क्रॉल लिस्ट में से कम से कम एक कॉलम चुनें ताकि हम चेकिंग शुरू कर सकें।")
                
    except Exception as e:
        st.error(f"फ़ाइल पढ़ने में कोई समस्या आई: {e}")
