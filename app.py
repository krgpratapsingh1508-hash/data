import streamlit as st
import pandas as pd

# Page configuration - पूरे स्क्रीन का इस्तेमाल करने के लिए
st.set_page_config(page_title="Data Validation System", layout="wide")

st.title("📊 Columns Manager & Data Validation System")
st.write("फ़ाइल अपलोड करें, लिस्ट से कॉलम चुनें और अपनी पूरी डेटा टेबल के साथ मैच करें।")

# 1. File Upload
uploaded_file = st.file_uploader("CSV या Excel फ़ाइल अपलोड करें", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        # File type loading
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.success("फ़ाइल लोड हो गई है!")
        
        # 2. Side-by-Side Layout (बाएं तरफ लिस्ट, दाएं तरफ पूरा डेटा)
        layout_col1, layout_col2 = st.columns([1, 2]) # 1:2 का रेशियो
        
        columns_list = df.columns.tolist()
        
        with layout_col1:
            st.subheader("⚙️ गलत कॉलम चुनें")
            # स्क्रॉल लिस्ट जिससे आप सीधे कॉलम सिलेक्ट करेंगे
            wrong_columns = st.multiselect(
                "डेटा देखकर बताएं कौन से कॉलम गलत हैं:",
                options=columns_list,
                placeholder="यहाँ से कॉलम चुनें..."
            )
            
            # शॉर्टकट बटन: सब सिलेक्ट करने या क्लियर करने के लिए
            if st.button("❌ सारे सिलेक्शन हटाएं"):
                st.rerun()

        with layout_col2:
            st.subheader("📋 आपकी पूरी डेटा टेबल")
            
            # अगर आपने कोई कॉलम चुना है, तो टेबल में उस कॉलम को हाईलाइट (Highlight) करने का फीचर
            if wrong_columns:
                def highlight_cols(s):
                    if s.name in wrong_columns:
                        return ['background-color: #ffcccc; color: black'] * len(s) # गलत कॉलम लाल दिखेगा
                    return [''] * len(s)
                
                # हाईलाइटेड टेबल दिखाना
                st.dataframe(df.style.apply(highlight_cols, axis=0), height=400, use_container_width=True)
            else:
                # नॉर्मल टेबल दिखाना
                st.dataframe(df, height=400, use_container_width=True)

        st.divider()
        
        # 3. एरर डिटेक्शन और रिपोर्ट जनरेशन (नीचे दिखेगा)
        if wrong_columns:
            st.subheader("🚨 चुने गए गलत कॉलम्स की एरर रिपोर्ट")
            
            error_records = []
            
            # सिर्फ सिलेक्टेड कॉलम्स में चेकिंग (खाली या गलत डेटा के लिए)
            for index, row in df.iterrows():
                for col in wrong_columns:
                    val = row[col]
                    
                    # कंडीशन: अगर डेटा खाली (NaN) है या कोई स्पेसिफिक गलत एंट्री है
                    if pd.isna(val) or str(val).strip() == "":
                        error_records.append({
                            "Excel Row Number": index + 2, # एक्सेल शीट के हिसाब से रो नंबर
                            "Column Name": col,
                            "Current Value": "❌ खाली (Missing Data)",
                            "Issue": "इस कॉलम को आपने गलत मार्क किया है और इसमें डेटा गायब है।"
                        })
                    else:
                        # अगर डेटा मौजूद है पर आपने कॉलम को गलत बोला है
                        error_records.append({
                            "Excel Row Number": index + 2,
                            "Column Name": col,
                            "Current Value": val,
                            "Issue": "इस कॉलम में डेटा है, पर आपने इसे 'गलत कॉलम' लिस्ट में चुना है।"
                        })
            
            # रिपोर्ट को टेबल फॉर्मेट में दिखाना
            if error_records:
                error_df = pd.DataFrame(error_records)
                st.error(f"चुने गए कॉलम्स में कुल {len(error_df)} संदिग्ध एंट्रीज (Entries) मिलीं!")
                st.dataframe(error_df, use_container_width=True)
                
                # डाउनलोड बटन
                csv_error = error_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 यह एरर रिपोर्ट डाउनलोड करें", csv_error, "column_error_report.csv", "text/csv")
        else:
            st.info("💡 बाईं तरफ (Left Side) की लिस्ट से कॉलम चुनें। चुनते ही दाईं तरफ की टेबल में वो कॉलम हाईलाइट हो जाएगा।")
                
    except Exception as e:
        st.error(f"फ़ाइल प्रोसेस करने में एरर: {e}")
