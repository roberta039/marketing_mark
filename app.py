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
import requests
import urllib.parse
from io import BytesIO

# --- 1. Configurare Pagină ---
st.set_page_config(page_title="Marketing AI (Free)", page_icon="🚀", layout="wide")

# --- 2. Secrete (Doar cele gratuite) ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
except:
    st.error("⚠️ Lipsesc cheile API! Verifică .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# --- 3. Funcții Backend ---

@st.cache_data(ttl=3600)
def get_available_models():
    """Obține modelele Gemini gratuite."""
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name]
        return sorted(models, reverse=True)
    except:
        return ["models/gemini-1.5-flash"]

def upload_to_gemini(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name
        ref = genai.upload_file(tmp_path, mime_type="application/pdf")
        os.remove(tmp_path)
        return ref
    except: return None

def search_internet(query):
    try:
        res = tavily_client.search(query=query, search_depth="advanced", max_results=3)
        return "\n".join([f"- {r['content']}" for r in res.get('results', [])])
    except: return "Fără date internet."

# --- FUNCȚIE GENERARE IMAGINE GRATUITĂ (POLLINATIONS) ---
def generate_image_free(prompt_text):
    """
    Generează imagine gratuit folosind Pollinations (Model Flux).
    Include protecție anti-eroare și headers de browser.
    """
    try:
        # 1. Scurtăm promptul (URL-urile lungi crapă)
        short_prompt = prompt_text[:200]
        
        # 2. Codăm URL-ul (spații -> %20)
        encoded_prompt = urllib.parse.quote(short_prompt)
        
        # 3. URL Pollinations (Model Flux = Calitate bună)
        url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&model=flux&nologo=true&seed=100"
        
        # 4. Headers: Ne prefacem că suntem Chrome ca să nu ne blocheze
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # 5. Request
        response = requests.get(url, headers=headers, timeout=30)
        
        # 6. Verificare conținut
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            return BytesIO(response.content)
        else:
            print(f"Server Refusal: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Eroare Imagine: {e}")
        return None

def create_presentation_with_images(slides_json):
    prs = Presentation()
    try:
        data = json.loads(slides_json)
    except:
        return None

    # Slide Titlu
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = data.get("presentation_title", "Marketing")
    slide.placeholders[1].text = "Generat Gratuit cu AI (Gemini + Flux)"

    # Layout Custom
    blank_layout = prs.slide_layouts[6] 

    for slide_data in data.get("slides", []):
        slide = prs.slides.add_slide(blank_layout)
        shapes = slide.shapes
        
        # Text UI
        tb = shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(1))
        tb.text_frame.paragraphs[0].text = slide_data.get("title", "Slide")
        tb.text_frame.paragraphs[0].font.size = Pt(32)
        tb.text_frame.paragraphs[0].font.bold = True
        tb.text_frame.paragraphs[0].font.color.rgb = RGBColor(0, 51, 102)

        tb_body = shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(4.5), Inches(5))
        tf = tb_body.text_frame
        tf.word_wrap = True
        for point in slide_data.get("points", []):
            p = tf.add_paragraph()
            p.text = "• " + point
            p.font.size = Pt(18)
            p.space_after = Pt(12)

        # IMAGINE GRATUITĂ
        image_prompt = slide_data.get("image_prompt", "")
        image_bytes = None
        
        if image_prompt:
            image_bytes = generate_image_free(image_prompt)
        
        # Inserare sau Fallback
        if image_bytes:
            try:
                shapes.add_picture(image_bytes, Inches(5.5), Inches(1.8), Inches(4.2), Inches(4.2))
            except:
                image_bytes = None
        
        if not image_bytes:
            shape = shapes.add_shape(1, Inches(5.5), Inches(1.8), Inches(4.2), Inches(4.2))
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(220, 220, 220)
            tf_shape = shape.text_frame
            tf_shape.text = "Imagine Indisponibilă\n(Eroare conexiune)"
            tf_shape.paragraphs[0].alignment = PP_ALIGN.CENTER
            tf_shape.paragraphs[0].font.color.rgb = RGBColor(100,100,100)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
        prs.save(tmp.name)
        return tmp.name

# --- 4. UI ---

st.title("🚀 Asistent Marketing (Gratuit & Vizual)")

with st.sidebar:
    st.header("Configurare")
    # Filtru pentru a arăta numele frumos
    model_name = st.selectbox("Model AI", get_available_models(), format_func=lambda x: x.replace("models/", "").upper())
    uploaded_file = st.file_uploader("Catalog PDF", type=['pdf'])
    
    if st.button("Șterge Istoric"):
        st.session_state.clear()
        st.rerun()

if "messages" not in st.session_state: st.session_state.messages = []

# Procesare PDF
if uploaded_file and "gemini_file" not in st.session_state:
    with st.spinner("⏳ Analizez PDF-ul..."):
        ref = upload_to_gemini(uploaded_file)
        if ref:
            st.session_state.gemini_file = ref
            st.success("✅ Catalog încărcat!")

# Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("Ex: Idei de promovare pentru produsele noi"):
    if "gemini_file" not in st.session_state: st.error("Te rog încarcă PDF-ul.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("🤖 Gândesc..."):
                web = search_internet(prompt)
                try:
                    model = genai.GenerativeModel(model_name)
                    # Prompt Combinat
                    resp = model.generate_content([f"Context PDF + Net: {web}. Întrebare: {prompt}", st.session_state.gemini_file])
                    st.markdown(resp.text)
                    st.session_state.messages.append({"role": "assistant", "content": resp.text})
                    st.session_state.last_analysis = resp.text
                except Exception as e:
                    st.error(f"Eroare AI: {e}")

# --- 5. Generare PPT ---

if "last_analysis" in st.session_state:
    st.divider()
    if st.button("✨ Generează Prezentare (Cu Imagini Gratuite)"):
        
        progress_bar = st.progress(0, text="Structura prezentării...")
        
        try:
            # Configurare JSON
            try:
                json_model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
            except:
                json_model = genai.GenerativeModel(model_name)

            prompt_slides = f"""
            Pe baza analizei: {st.session_state.last_analysis}
            Generează JSON pentru 4-5 slide-uri.
            
            IMPORTANT:
            Include 'image_prompt' (în ENGLEZĂ, max 20 cuvinte) descriind o fotografie de produs profesională.
            
            FORMAT:
            {{
                "presentation_title": "Titlu",
                "slides": [
                    {{ 
                        "title": "Titlu", 
                        "points": ["Punct 1"], 
                        "image_prompt": "Minimalist photo of red pen on desk" 
                    }}
                ]
            }}
            """
            
            resp = json_model.generate_content(prompt_slides)
            json_text = resp.text.replace("```json", "").replace("```", "").strip()
            
            progress_bar.progress(20, text="Generez imagini cu Pollinations AI (Durează ~10 secunde)...")
            
            pptx_path = create_presentation_with_images(json_text)
            
            progress_bar.progress(100, text="Gata!")
            
            if pptx_path:
                with open(pptx_path, "rb") as f:
                    st.download_button("📥 Descarcă PPTX", f, "Prezentare_Free.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")
            else:
                st.error("Eroare la generare fișier.")
                
        except Exception as e:
            st.error(f"Eroare proces: {e}")
