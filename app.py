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
import urllib.parse  # <--- FIX: Necesar pentru a codifica URL-ul corect
from io import BytesIO

# --- 1. Configurare Pagină ---
st.set_page_config(
    page_title="Marketing AI + Imagini", 
    page_icon="🎨", 
    layout="wide"
)

# --- 2. Secrete ---
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
    """Returnează modelele Gemini disponibile."""
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
    except: return "Fără date de pe internet."

# --- FUNCȚIE GENERARE IMAGINE (REPARATĂ) ---
def generate_image_from_prompt(prompt_text):
    """
    Generează imagine folosind Pollinations.ai.
    FIX: Folosește urllib quote și verifică header-ul răspunsului.
    """
    try:
        # 1. Codare URL corectă (transformă spațiile și caracterele speciale)
        encoded_prompt = urllib.parse.quote(prompt_text)
        
        # 2. Construire URL (Adăugăm .jpg la final pentru a forța formatul)
        # model=flux este excelent pentru realism
        # nologo=true ascunde logo-ul Pollinations dacă e posibil
        url = f"https://pollinations.ai/p/{encoded_prompt}.jpg?width=1024&height=768&model=flux&nologo=true&seed=42"
        
        # 3. Request cu timeout
        response = requests.get(url, timeout=20)
        
        # 4. Verificare Critică: Este imagine?
        content_type = response.headers.get("Content-Type", "")
        if response.status_code == 200 and "image" in content_type:
            return BytesIO(response.content)
        else:
            print(f"⚠️ Eroare API Imagine: Primit {content_type} în loc de image")
            return None
            
    except Exception as e:
        print(f"⚠️ Excepție generare imagine: {e}")
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
    slide.placeholders[1].text = "Generat cu AI (Gemini + Pollinations)"

    # Layout Custom (Blank)
    blank_layout = prs.slide_layouts[6] 

    for i, slide_data in enumerate(data.get("slides", [])):
        slide = prs.slides.add_slide(blank_layout)
        shapes = slide.shapes
        
        # 1. Titlu
        tb = shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(1))
        p = tb.text_frame.paragraphs[0]
        p.text = slide_data.get("title", "Slide")
        p.font.size = Pt(32)
        p.font.bold = True
        p.font.color.rgb = RGBColor(0, 51, 102)

        # 2. Text (Stânga)
        tb_body = shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(4.5), Inches(5))
        tf = tb_body.text_frame
        tf.word_wrap = True
        for point in slide_data.get("points", []):
            p = tf.add_paragraph()
            p.text = "• " + point
            p.font.size = Pt(18)
            p.space_after = Pt(12)

        # 3. IMAGINE (Dreapta)
        image_prompt = slide_data.get("image_prompt", "")
        image_bytes = None
        
        if image_prompt:
            # Încercăm să generăm imaginea
            image_bytes = generate_image_from_prompt(image_prompt)
        
        if image_bytes:
            # Succes: Inserăm imaginea
            try:
                shapes.add_picture(image_bytes, Inches(5.5), Inches(1.8), Inches(4.2), Inches(3.2))
            except Exception as e:
                # Fallback extrem: Dacă totuși imaginea e coruptă
                print(f"Nu s-a putut insera imaginea: {e}")
                image_bytes = None # Trecem pe fallback vizual
        
        if not image_bytes:
            # Fallback: Chenar Gri
            shape = shapes.add_shape(1, Inches(5.5), Inches(1.8), Inches(4.2), Inches(3.2))
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(220, 220, 220)
            shape.line.color.rgb = RGBColor(180, 180, 180)
            
            tf_shape = shape.text_frame
            tf_shape.text = "🖼️\n(Imagine Indisponibilă)\nInserare manuală"
            for p in tf_shape.paragraphs:
                p.alignment = PP_ALIGN.CENTER
                p.font.color.rgb = RGBColor(100, 100, 100)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
        prs.save(tmp.name)
        return tmp.name

# --- 4. UI ---

st.title("🎨 Asistent Marketing (Text + Imagini)")

with st.sidebar:
    st.header("Setări")
    model_name = st.selectbox("Model", get_available_models(), format_func=lambda x: x.replace("models/", "").upper())
    uploaded_file = st.file_uploader("Catalog PDF", type=['pdf'])
    
    if st.button("Șterge Istoric"):
        st.session_state.clear()
        st.rerun()

if "messages" not in st.session_state: st.session_state.messages = []

# Procesare PDF
if uploaded_file and "gemini_file" not in st.session_state:
    with st.spinner("Procesez PDF..."):
        ref = upload_to_gemini(uploaded_file)
        if ref:
            st.session_state.gemini_file = ref
            st.success("PDF Gata!")
        else:
            st.error("Eroare upload PDF.")

# Chat UI
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("Ex: Vreau o strategie pentru produse de vară"):
    if "gemini_file" not in st.session_state: st.error("Încarcă Catalogul PDF.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analizez..."):
                web = search_internet(prompt)
                
                # Prompt simplificat
                full_prompt = [f"Context PDF + Net: {web}. Întrebare: {prompt}", st.session_state.gemini_file]
                
                try:
                    model = genai.GenerativeModel(model_name)
                    resp = model.generate_content(full_prompt)
                    st.markdown(resp.text)
                    st.session_state.messages.append({"role": "assistant", "content": resp.text})
                    st.session_state.last_analysis = resp.text
                except Exception as e:
                    st.error(f"Eroare AI: {e}")

# --- 5. Generare PPT cu Imagini ---

if "last_analysis" in st.session_state:
    st.divider()
    if st.button("✨ Generează Prezentare (Cu Imagini AI)"):
        
        progress_bar = st.progress(0, text="Planific slide-urile...")
        
        try:
            # 1. Obținere JSON folosind modelul selectat
            try:
                json_model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
            except:
                json_model = genai.GenerativeModel(model_name) # Fallback

            prompt_slides = f"""
            Pe baza analizei: {st.session_state.last_analysis}
            Generează JSON pentru 4-5 slide-uri.
            
            CERINȚĂ SPECIALĂ:
            Include câmpul 'image_prompt' cu o descriere vizuală în ENGLEZĂ pentru o imagine fotorealistă (fără text în imagine).
            
            FORMAT:
            {{
                "presentation_title": "Titlu",
                "slides": [
                    {{ 
                        "title": "Titlu Slide", 
                        "points": ["Punct 1", "Punct 2"], 
                        "image_prompt": "Professional photography of a red notebook on a white desk, 8k resolution" 
                    }}
                ]
            }}
            """
            
            resp = json_model.generate_content(prompt_slides)
            json_text = resp.text.replace("```json", "").replace("```", "").strip()
            
            progress_bar.progress(20, text="Generez imaginile (acest pas durează puțin)...")
            
            # 2. Creare PPTX
            pptx_path = create_presentation_with_images(json_text)
            
            progress_bar.progress(100, text="Gata!")
            
            if pptx_path:
                with open(pptx_path, "rb") as f:
                    st.download_button("📥 Descarcă PPTX", f, "Prezentare_AI.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")
            else:
                st.error("Eroare la crearea fișierului.")
                
        except Exception as e:
            st.error(f"Eroare proces: {e}")
