import streamlit as st
import google.generativeai as genai
from tavily import TavilyClient
from pptx import Presentation
from pptx.util import Inches, Pt
import tempfile
import os
import json
import re

# --- 1. Configurare Pagină ---
st.set_page_config(page_title="Marketing Portfolio Optimizer + Slides", page_icon="📊", layout="wide")

# --- 2. Gestionare Secrete ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
except FileNotFoundError:
    st.error("⚠️ Configurează cheile API în .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# --- 3. Funcții Helper (AI & PPTX) ---

@st.cache_data(ttl=3600)
def get_available_models():
    """Obține lista modelelor Gemini."""
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name]
        return sorted(models, reverse=True)
    except:
        return ["models/gemini-1.5-flash"]

def upload_to_gemini(uploaded_file):
    """Upload fișier pentru analiză vizuală."""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
        file_ref = genai.upload_file(tmp_path, mime_type="application/pdf")
        os.remove(tmp_path)
        return file_ref
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None

def search_internet(query):
    try:
        res = tavily_client.search(query=query, search_depth="advanced", max_results=4)
        return "\n".join([f"- {r['content']} ({r['url']})" for r in res.get('results', [])])
    except:
        return "Nu s-au găsit date pe internet."

def create_presentation_file(slides_json):
    """
    Generează un fișier PPTX din datele JSON primite de la AI.
    """
    prs = Presentation()
    
    # Titlu Slides
    try:
        data = json.loads(slides_json)
        
        # 1. Slide de Titlu
        title_slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        
        title.text = data.get("presentation_title", "Analiză Portofoliu")
        subtitle.text = "Generat automat cu AI"

        # 2. Slide-uri de conținut
        bullet_slide_layout = prs.slide_layouts[1]
        
        for slide_data in data.get("slides", []):
            slide = prs.slides.add_slide(bullet_slide_layout)
            shapes = slide.shapes
            
            # Titlu Slide
            title_shape = shapes.title
            title_shape.text = slide_data.get("title", "Slide")
            
            # Conținut (Bullets)
            body_shape = shapes.placeholders[1]
            tf = body_shape.text_frame
            
            content_points = slide_data.get("points", [])
            if content_points:
                tf.text = content_points[0] # Primul punct
                for point in content_points[1:]:
                    p = tf.add_paragraph()
                    p.text = point
                    p.level = 0

        # Salvare în fișier temporar
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
            prs.save(tmp.name)
            return tmp.name
            
    except Exception as e:
        st.error(f"Eroare la generarea PPT: {e}")
        return None

# --- 4. Interfață ---

st.title("📊 Asistent Marketing & Generator Prezentări")
st.markdown("Analizează catalogul, caută trenduri și **generează o prezentare PPT** instant.")

with st.sidebar:
    st.header("⚙️ Setări")
    model_name = st.selectbox("Model AI", get_available_models(), format_func=lambda x: x.replace("models/", "").upper())
    uploaded_file = st.file_uploader("Catalog PDF", type=['pdf'])
    
    if st.button("Reset"):
        st.session_state.clear()
        st.rerun()

# --- 5. Logica ---

if "messages" not in st.session_state:
    st.session_state.messages = []

# Procesare PDF
if uploaded_file and "gemini_file" not in st.session_state:
    with st.spinner("Procesez PDF-ul..."):
        ref = upload_to_gemini(uploaded_file)
        if ref:
            st.session_state.gemini_file = ref
            st.success("PDF Încărcat!")

# Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input User
if prompt := st.chat_input("Ex: Propune o strategie pentru pixuri ecologice"):
    
    if "gemini_file" not in st.session_state:
        st.error("Încarcă PDF-ul.")
    else:
        # User Message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # AI Analysis
        with st.chat_message("assistant"):
            with st.spinner("Analizez și caut pe net..."):
                web_data = search_internet(prompt)
                model = genai.GenerativeModel(model_name)
                
                # Pasul 1: Analiza Text
                analysis_prompt = [
                    f"""Ești expert Marketing.
                    CONTEXT PDF: Analizează fișierul atașat.
                    CONTEXT NET: {web_data}
                    ÎNTREBARE: {prompt}
                    Răspunde detaliat în română.""",
                    st.session_state.gemini_file
                ]
                
                response = model.generate_content(analysis_prompt)
                ai_text = response.text
                st.markdown(ai_text)
                st.session_state.messages.append({"role": "assistant", "content": ai_text})
                
                # Salvăm ultimul context pentru generarea prezentării
                st.session_state.last_analysis = ai_text
                st.session_state.last_prompt = prompt

# --- 6. Butonul Magic: Generare Prezentare ---

if "last_analysis" in st.session_state:
    st.divider()
    st.subheader("🎬 Acțiuni")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if st.button("Generează Prezentare PPT (.pptx)"):
            with st.spinner(f"Generez structura folosind modelul {model_name.replace('models/', '')}..."):
                
                # FIX: Folosim 'model_name' (cel ales de tine), nu unul hardcoded.
                # Modelele 1.5 suportă nativ JSON mode.
                try:
                    json_model = genai.GenerativeModel(
                        model_name, 
                        generation_config={"response_mime_type": "application/json"}
                    )
                except:
                    # Fallback pentru modele mai vechi care nu suportă config JSON explicit
                    json_model = genai.GenerativeModel(model_name)
                
                slide_prompt = f"""
                Acționează ca un expert în prezentări de business.
                Pe baza analizei de mai jos, creează o structură pentru o prezentare PowerPoint de 5-7 slide-uri.
                
                ANALIZA:
                {st.session_state.last_analysis}
                
                Output-ul TREBUIE să fie un JSON valid (fără ```json sau alte marcaje) cu această structură:
                {{
                    "presentation_title": "Titlul Principal",
                    "slides": [
                        {{
                            "title": "Titlu Slide 1",
                            "points": ["Idee 1", "Idee 2", "Idee 3"]
                        }}
                    ]
                }}
                """
                
                try:
                    # Generăm structura JSON
                    json_response = json_model.generate_content(slide_prompt)
                    slides_json = json_response.text
                    
                    # Curățăm textul în caz că modelul pune markdown ```json ... ```
                    # Deși JSON mode ar trebui să prevină asta, e bine să fim siguri.
                    slides_json = slides_json.replace("```json", "").replace("```", "").strip()
                    
                    # Creăm fișierul PPTX
                    pptx_path = create_presentation_file(slides_json)
                    
                    if pptx_path:
                        with open(pptx_path, "rb") as file:
                            st.download_button(
                                label="📥 Descarcă Prezentarea PowerPoint",
                                data=file,
                                file_name="Marketing_Strategy.pptx",
                                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                            )
                        st.success("Prezentarea a fost generată! O poți deschide în PowerPoint sau importa în Gamma.")
                    
                except Exception as e:
                    st.error(f"Eroare la generare slide-uri: {e}")
                    st.warning("Încearcă să selectezi alt model din lista din stânga (ex: Gemini 1.5 Pro).")

    with col2:
        st.info("💡 **Tip:** Fișierul `.pptx` generat este 'scheletul' perfect. Importă-l în **Gamma** sau **Google Slides** pentru design.")
