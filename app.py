import streamlit as st
import pdfplumber
import os
from fuzzywuzzy import fuzz
import io
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# Optional AI
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ─── Page config ────────────────────────────────────────────────
st.set_page_config(page_title="AI Resume Optimizer", layout="wide")

st.title("🚀 AI Resume Optimizer")
st.markdown("Upload resume PDF + paste job description → get ATS insights & suggestions")

# Custom CSS
st.markdown("""
    <style>
    .missing { color: red; font-weight: bold; }
    .match { color: green; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# Sidebar AI choice
st.sidebar.header("AI Settings")
ai_option = st.sidebar.selectbox("AI Provider", ["None", "OpenAI", "Ollama"])
client = None
if ai_option == "OpenAI":
    key = st.sidebar.text_input("OpenAI API Key", type="password")
    if key:
        client = OpenAI(api_key=key)
elif ai_option == "Ollama":
    st.sidebar.info("Run Ollama locally and use model 'mistral' or 'llama3'")

# ─── UI ─────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["Input", "Analysis", "Suggestions", "Export"])

with tab1:
    uploaded = st.file_uploader("Resume (PDF)", type="pdf")
    resume_text = ""
    if uploaded:
        try:
            with pdfplumber.open(uploaded) as pdf:
                resume_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            st.success("Resume parsed!")
        except Exception as e:
            st.error(f"PDF error: {e}")
        resume_text = st.text_area("Resume text", resume_text, height=220)

    jd_text = st.text_area("Job Description(s) – comma separated", height=220)

# ─── Analysis ───────────────────────────────────────────────────
if st.button("Analyze", type="primary") and uploaded and jd_text and resume_text:
    with st.spinner("Working..."):
        try:
            # Fallback keyword extraction (no spaCy needed)
            jd_words = []
            for jd in [j.strip() for j in jd_text.split(',') if j.strip()]:
                jd_words.extend(w for w in jd.lower().split() if len(w) > 2 and w.isalpha())
            jd_keywords = list(set(jd_words))

            resume_words = [w for w in resume_text.lower().split() if len(w) > 2 and w.isalpha()]
            resume_keywords = list(set(resume_words))

            # Missing with fuzzy match
            missing = []
            for kw in jd_keywords:
                if max(fuzz.ratio(kw, r) for r in resume_keywords) <= 80:
                    missing.append(kw)

            total = len(jd_keywords)
            matched = total - len(missing)
            match_pct = (matched / total * 100) if total > 0 else 0
            ats_score = match_pct  # simple version

            # Highlight
            highlighted = resume_text
            for kw in missing:
                highlighted = highlighted.replace(kw, f'<span class="missing">{kw}</span>')
            for kw in set(jd_keywords) - set(missing):
                highlighted = highlighted.replace(kw, f'<span class="match">{kw}</span>')

            with tab2:
                cols = st.columns(4)
                cols[0].metric("JD Keywords", total)
                cols[1].metric("Missing", len(missing))
                cols[2].metric("Match %", f"{match_pct:.1f}%")
                cols[3].metric("ATS Score", f"{ats_score:.1f}%")

                if missing:
                    st.warning("Missing keywords: " + ", ".join(f'<span class="missing">{k}</span>' for k in missing), unsafe_allow_html=True)
                else:
                    st.success("Looks good — most keywords are present!")

                st.markdown("**Highlighted resume:**")
                st.markdown(highlighted, unsafe_allow_html=True)

            with tab3:
                if client and ai_option == "OpenAI":
                    st.info("AI suggestions coming soon... (connect key & enable)")
                else:
                    st.info("Tip: Add missing keywords naturally to Skills or Experience section.")

            with tab4:
                data = {
                    "Category": ["JD Keywords", "Missing", "Match %", "ATS Score"],
                    "Value": [", ".join(jd_keywords), ", ".join(missing), f"{match_pct:.1f}%", f"{ats_score:.1f}%"]
                }
                df = pd.DataFrame(data)

                csv = io.StringIO()
                df.to_csv(csv, index=False)
                st.download_button("CSV Report", csv.getvalue(), "report.csv")

                # Simple PDF
                pdf_buf = io.BytesIO()
                doc = SimpleDocTemplate(pdf_buf, pagesize=letter)
                styles = getSampleStyleSheet()
                elements = [Paragraph("Resume Report", styles['Title'])]
                table_data = [df.columns.tolist()] + df.values.tolist()
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.grey),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('GRID', (0,0), (-1,-1), 1, colors.black)
                ]))
                elements.append(t)
                doc.build(elements)
                pdf_buf.seek(0)
                st.download_button("PDF Report", pdf_buf, "report.pdf", "application/pdf")

        except Exception as e:
            st.error(f"Something went wrong: {str(e)}")

else:
    st.info("Upload resume & paste job description to start.")