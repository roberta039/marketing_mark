import streamlit as st
import google.generativeai as genai
from tavily import TavilyClient
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
import tempfile
import os
import json
import re

# --- 1. Configurare Pagină ---
st.set_page_config(
    page_title="Marketing Portfolio & Slides AI",
    page_icon="🚀",
    layout="wide"
)

# --- 2. Gestionare Secrete (API Keys) ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
except FileNotFoundError:
    st.error("⚠️ Lipsesc cheile API! Configurează .streamlit/secrets.toml sau Streamlit Cloud Secrets.")
    st.stop()

# Configurare Clienți
genai.configure(api_key=GOOGLE_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# --- 3. Funcții Utilitare (Backend) ---

@st.cache_data(ttl=3600)
def get_available_models():
    """Returnează lista modelelor Gemini care suportă generare de conținut."""
    try:
        models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
                models.append(m.name)
        return sorted(models, reverse=True)
    except:
        return ["models/gemini-1.5-flash"]

def upload_to_gemini(uploaded_file):
    """Încarcă PDF-ul la Google pentru analiză vizuală (Vision)."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
        
        # Upload la Google File API
        file_ref = genai.upload_file(tmp_path, mime_type="application/pdf")
        
        # Curățenie locală
        os.remove(tmp_path)
        return file_ref
    except Exception as e:
        st.error(f"Eroare upload: {e}")
        return None

def search_internet(query):
    """Caută trenduri live pe internet."""
    try:
        res = tavily_client.search(query=query, search_depth="advanced", max_results=4)
        context = "\n".join([f"- {r['content']} ({r['url']})" for r in res.get('results', [])])
        return context if context else "Nu s-au găsit date relevante."
    except Exception as e:
        return f"Eroare căutare: {e}"

def create_presentation_file(slides_json):
    """Generează PPTX cu layout: Text Stânga + Placeholder Poză Dreapta."""
    prs = Presentation()
    
    try:
        data = json.loads(slides_json)
    except:
        return None

    # A. Slide de Titlu
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = data.get("presentation_title", "Analiză Portofoliu")
    slide.placeholders[1].text = "Generat automat cu AI"

    # B. Slide-uri de Conținut (Layout Custom)
    blank_layout = prs.slide_layouts[6] 

    for slide_data in data.get("slides", []):
        slide = prs.slides.add_slide(blank_layout)
        shapes = slide.shapes
        
        # 1. Titlu Slide (Sus)
        tb_title = shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(1))
        p = tb_title.text_frame.paragraphs[0]
        p.text = slide_data.get("title", "Slide")
        p.font.size = Pt(32)
        p.font.bold = True
        p.font.color.rgb = RGBColor(0, 51, 102) # Dark Blue

        # 2. Text Idei (Stânga)
        tb_body = shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(4.5), Inches(5))
        tf = tb_body.text_frame
        tf.word_wrap = True
        
        for point in slide_data.get("points", []):
            p = tf.add_paragraph()
            p.text = "• " + point
            p.font.size = Pt(18)
            p.space_after = Pt(14)

        # 3. Placeholder Imagine (Dreapta) - Chenar Gri
        shape = shapes.add_shape(1, Inches(5.5), Inches(1.8), Inches(4), Inches(3.5)) # 1 = Dreptunghi
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(240, 240, 240)
        shape.line.color.rgb = RGBColor(180, 180, 180)
        
        tf_shape = shape.text_frame
        tf_shape.text = "🖼️\nFOTO PRODUS\n(Drag & Drop aici)"
        for p in tf_shape.paragraphs:
            p.alignment = PP_ALIGN.CENTER
            p.font.color.rgb = RGBColor(120, 120, 120)

    # Salvare temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
        prs.save(tmp.name)
        return tmp.name

# --- 4. Interfața Grafică (UI) ---

st.title("🚀 Asistent Marketing & PPT Generator")
st.markdown("Analiză multimodală (Text + Imagini) și generare de prezentări.")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configurare")
    
    # Selector Model
    model_list = get_available_models()
    selected_model_name = st.selectbox(
        "Model AI:", 
        model_list, 
        format_func=lambda x: x.replace("models/", "").upper()
    )
    
    st.divider()
    uploaded_file = st.file_uploader("📂 Încarcă Catalog (PDF)", type=['pdf'])
    
    if st.button("🔄 Reset Chat"):
        st.session_state.clear()
        st.rerun()

# --- 5. Logica Principală ---

if "messages" not in st.session_state:
    st.session_state.messages = []

# Procesare PDF
if uploaded_file and "gemini_file" not in st.session_state:
    with st.spinner("📤 Urc catalogul în 'creierul' vizual al AI-ului..."):
        file_ref = upload_to_gemini(uploaded_file)
        if file_ref:
            st.session_state.gemini_file = file_ref
            st.session_state.file_name = uploaded_file.name
            st.success("✅ Catalog analizat! Acum pot vedea pozele produselor.")
        else:
            st.error("Eroare la procesarea fișierului.")

# Afișare Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input Chat
if prompt := st.chat_input("Ex: Ce produse sunt demodate vizual?"):
    
    if "gemini_file" not in st.session_state:
        st.error("Te rog încarcă PDF-ul întâi.")
    else:
        # 1. Salvare Mesaj User
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Generare Răspuns AI
        with st.chat_message("assistant"):
            with st.spinner("🔍 Mă uit pe internet și în catalog..."):
                
                # Context Internet
                web_data = search_internet(prompt)
                
                # Configurare Prompt Multimodal
                full_prompt = [
                    f"""Ești expert Marketing și Product Design.
                    CONTEXT CATALOG: Analizează fișierul PDF atașat (Text + Imagini).
                    CONTEXT INTERNET: {web_data}
                    ÎNTREBARE: {prompt}
                    
                    INSTRUCȚIUNI:
                    - Dacă e relevant, comentează despre designul produselor (imagini).
                    - Compară cu trendurile găsite pe net.
                    - Răspunde în română.""",
                    st.session_state.gemini_file
                ]
                
                # Apelare Model Selectat
                try:
                    model = genai.GenerativeModel(selected_model_name)
                    response = model.generate_content(full_prompt)
                    ai_reply = response.text
                    
                    st.markdown(ai_reply)
                    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                    
                    # Salvăm pentru PPT
                    st.session_state.last_analysis = ai_reply
                    
                except Exception as e:
                    st.error(f"Eroare model AI: {e}")

# --- 6. Secțiunea Generare PPT ---

if "last_analysis" in st.session_state:
    st.divider()
    st.subheader("🎬 Acțiuni")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if st.button("📊 Generează Prezentare (.pptx)"):
            with st.spinner(f"Generez slide-urile folosind {selected_model_name.replace('models/', '')}..."):
                
                # Pasul 1: Text -> JSON Structurat
                # Folosim ACELAȘI model selectat pentru a evita erorile 404
                try:
                    json_model = genai.GenerativeModel(
                        selected_model_name,
                        generation_config={"response_mime_type": "application/json"}
                    )
                except:
                    # Fallback pt modele vechi
                    json_model = genai.GenerativeModel(selected_model_name)

                prompt_slides = f"""
                Transformă analiza de mai jos într-o structură JSON pentru o prezentare PowerPoint (5-8 slide-uri).
                
                ANALIZA:
                {st.session_state.last_analysis}
                
                FORMAT JSON OBLIGATORIU:
                {{
                    "presentation_title": "Titlu Scurt",
                    "slides": [
                        {{ "title": "Titlu Slide", "points": ["Idee 1", "Idee 2"] }}
                    ]
                }}
                """
                
                try:
                    resp = json_model.generate_content(prompt_slides)
                    clean_json = resp.text.replace("```json", "").replace("```", "").strip()
                    
                    # Pasul 2: JSON -> PPTX File
                    pptx_path = create_presentation_file(clean_json)
                    
                    if pptx_path:
                        with open(pptx_path, "rb") as f:
                            st.download_button(
                                "📥 Descarcă PowerPoint",
                                f,
                                file_name="Marketing_Strategy.pptx",
                                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                            )
                        st.success("Gata! Text în stânga, loc pentru poze în dreapta.")
                    else:
                        st.error("Eroare la crearea fișierului PPTX.")
                        
                except Exception as e:
                    st.error(f"Eroare generare JSON: {e}")

    with col2:
        st.info("💡 **Tip:** Importă fișierul `.pptx` în **Gamma** sau **Google Slides** pentru design automat, sau doar trage pozele produselor peste chenarele gri.")
