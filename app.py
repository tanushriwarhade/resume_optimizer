import streamlit as st
import pdfplumber
import spacy
import os
from fuzzywuzzy import fuzz
import io
import csv
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# OpenAI or Ollama import (comment/uncomment based on choice)
# For OpenAI:
from openai import OpenAI
# For Ollama:
# import ollama

# Set up Streamlit page with custom title and wide layout
st.set_page_config(page_title="Advanced AI Resume Optimizer", layout="wide")

st.title("🚀 Advanced AI-Powered Resume Optimizer")
st.markdown("""
    Optimize your resume for ATS systems! Upload PDF, paste job description(s), and get detailed analysis, suggestions, and exports.
""")

# Custom CSS for highlights
st.markdown("""
    <style>
    .missing-keyword { color: red; font-weight: bold; }
    .match-keyword { color: green; font-weight: bold; }
    .stTab { background-color: #f0f2f6; padding: 10px; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

# ─── Load spaCy model with EXPLICIT PATH (your Windows venv path) ───
# nlp = load_nlp()   # comment out

# Inside analysis block:
jd_keywords = list(set(word for word in jd_text.lower().split() if len(word) > 2 and word.isalpha()))
resume_keywords = list(set(word for word in resume_text.lower().split() if len(word) > 2 and word.isalpha()))

# Sidebar for AI configuration
st.sidebar.header("AI Configuration")
ai_option = st.sidebar.selectbox("Choose AI Provider", ["OpenAI", "Ollama", "None (Basic Mode)"])

if ai_option == "OpenAI":
    openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")
    if openai_api_key:
        client = OpenAI(api_key=openai_api_key)
    else:
        client = None
        st.sidebar.warning("Enter OpenAI API key for AI suggestions.")
elif ai_option == "Ollama":
    ollama_model = st.sidebar.text_input("Ollama Model", value="mistral")
    client = "ollama"  # Flag for Ollama
else:
    client = None

# Tabs for better UI organization
tab1, tab2, tab3, tab4 = st.tabs(["📤 Input", "🔍 Analysis", "💡 Suggestions", "📥 Export"])

with tab1:
    st.subheader("Upload Resume & Job Description(s)")
    uploaded_file = st.file_uploader("Upload your resume (PDF)", type="pdf")
    resume_text = ""

    if uploaded_file:
        try:
            with pdfplumber.open(uploaded_file) as pdf:
                resume_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            st.success("Resume uploaded and parsed!")
        except Exception as e:
            st.error(f"Error parsing PDF: {str(e)}. Try a different PDF.")
        resume_text = st.text_area("Extracted resume text (edit if needed)", resume_text, height=200)

    jd_text = st.text_area("Paste Job Description(s) (comma-separated for multiple)", height=250, help="E.g., JD1 text, JD2 text")

# ─── Main analysis button ────────────────────────────────────────────────
if st.button("Analyze & Optimize", type="primary") and uploaded_file and jd_text and resume_text:
    with st.spinner("Analyzing..."):
        try:
            # Load spaCy only when analyzing (and handle failure gracefully)
            nlp = load_nlp()

            # Split multiple JDs
            jds = [jd.strip() for jd in jd_text.split(',') if jd.strip()]

            all_jd_keywords = []
            if nlp:
                for single_jd in jds:
                    jd_doc = nlp(single_jd.lower())
                    jd_keywords = list(set([token.text for token in jd_doc if token.is_alpha and not token.is_stop and len(token.text) > 2]))
                    all_jd_keywords.extend(jd_keywords)
            else:
                # Fallback if spaCy failed
                for single_jd in jds:
                    words = [w for w in single_jd.lower().split() if len(w) > 2 and w.isalpha()]
                    all_jd_keywords.extend(words)

            jd_keywords = list(set(all_jd_keywords))
            total_jd_kw = len(jd_keywords)

            # Resume keywords
            if nlp:
                resume_doc = nlp(resume_text.lower())
                resume_keywords = list(set([token.text for token in resume_doc if token.is_alpha and not token.is_stop]))
            else:
                resume_keywords = list(set([w for w in resume_text.lower().split() if len(w) > 2 and w.isalpha()]))

            # Missing keywords with fuzzy matching
            missing = [kw for kw in jd_keywords if max([fuzz.ratio(kw, rkw) for rkw in resume_keywords], default=0) <= 80]

            # Scores
            keyword_freq = {kw: all_jd_keywords.count(kw) for kw in jd_keywords}
            matched = total_jd_kw - len(missing)
            match_percentage = (matched / total_jd_kw * 100) if total_jd_kw > 0 else 0
            weighted_score = sum(keyword_freq.get(kw, 0) for kw in resume_keywords if kw in jd_keywords) / sum(keyword_freq.values()) * 100 if sum(keyword_freq.values()) > 0 else 0
            ats_score = (match_percentage + weighted_score) / 2

            # Highlighting
            highlighted_resume = resume_text
            for kw in missing:
                highlighted_resume = highlighted_resume.replace(kw, f'<span class="missing-keyword">{kw}</span>')
            for kw in set(jd_keywords) - set(missing):
                highlighted_resume = highlighted_resume.replace(kw, f'<span class="match-keyword">{kw}</span>')

            with tab2:
                st.subheader("Keyword Match Analysis")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total JD Keywords", total_jd_kw)
                col2.metric("Missing in Resume", len(missing))
                col3.metric("Match %", f"{match_percentage:.1f}%")
                col4.metric("Weighted ATS Score", f"{ats_score:.1f}%")

                if missing:
                    st.warning("Missing important keywords:")
                    st.write(", ".join([f'<span class="missing-keyword">{kw}</span>' for kw in missing]), unsafe_allow_html=True)
                else:
                    st.success("Great match! No major keywords missing.")

                st.subheader("Highlighted Resume Text")
                st.markdown(highlighted_resume, unsafe_allow_html=True)

                st.subheader("ATS Score Breakdown")
                st.write(f"- Basic Match: {match_percentage:.1f}% (keywords present)")
                st.write(f"- Weighted Match: {weighted_score:.1f}% (importance by frequency in JD)")
                st.progress(ats_score / 100)

            with tab3:
                st.subheader("Suggested Improvements")
                if client:
                    missing_str = ', '.join(missing)
                    resume_trunc = resume_text[:1500]

                    if ai_option == "OpenAI":
                        prompt = f"""
                        Missing keywords: {missing_str}
                        Resume snippet: {resume_trunc}

                        Generate 5-7 section-specific bullet points (Skills, Experience, etc.) 
                        incorporating these missing keywords naturally.
                        Start each with strong action verbs. Group by section.
                        """
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=500,
                            temperature=0.7
                        )
                        suggestions = response.choices[0].message.content.strip()

                    elif ai_option == "Ollama":
                        # Same prompt
                        response = ollama.generate(model=ollama_model, prompt=prompt)
                        suggestions = response['response'].strip()

                    st.info(suggestions)

                    # Improved resume (optional - can be heavy)
                    # ... (keep or comment out if too slow)

                else:
                    st.info("Basic suggestion: Add missing keywords to your **Skills** or **Experience** section naturally, e.g., 'Experienced in [keyword], [keyword]'.")

                st.subheader("Quick ATS Tips")
                st.markdown("""
                - Use standard section headings: Experience, Skills, Education
                - Avoid images, tables, fancy formatting
                - Include exact phrases from the job description when possible
                - Save as .docx or .pdf (text-based, not scanned)
                """)

            with tab4:
                st.subheader("Export Report")
                report_data = {
                    "Category": ["JD Keywords", "Missing Keywords", "Match %", "ATS Score", "Weighted Score"],
                    "Details": [", ".join(jd_keywords), ", ".join(missing), f"{match_percentage:.1f}%", f"{ats_score:.1f}%", f"{weighted_score:.1f}%"]
                }
                report_df = pd.DataFrame(report_data)

                csv_output = io.StringIO()
                report_df.to_csv(csv_output, index=False)
                st.download_button("Download CSV Report", csv_output.getvalue(), file_name="resume_analysis.csv", mime="text/csv")

                # PDF Export
                pdf_output = io.BytesIO()
                doc = SimpleDocTemplate(pdf_output, pagesize=letter)
                styles = getSampleStyleSheet()
                elements = []

                elements.append(Paragraph("Resume Optimization Report", styles['Title']))
                elements.append(Paragraph(f"ATS Score: {ats_score:.1f}%", styles['Heading2']))

                data = [["Category", "Details"]] + report_df.values.tolist()
                t = Table(data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0,0), (-1,0), 12),
                    ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                    ('GRID', (0,0), (-1,-1), 1, colors.black)
                ]))
                elements.append(t)

                doc.build(elements)
                pdf_output.seek(0)
                st.download_button("Download PDF Report", pdf_output, file_name="resume_analysis.pdf", mime="application/pdf")

        except Exception as e:
            st.error(f"Analysis error: {str(e)}. Please check the terminal for more details.")
else:
    st.info("Upload your resume PDF and paste at least one job description to start analysis.")