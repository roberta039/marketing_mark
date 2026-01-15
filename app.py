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
import requests # <--- Nou: Pentru a descărca imaginea
from io import BytesIO # <--- Nou: Pentru a procesa imaginea în memorie

# --- 1. Configurare Pagină ---
st.set_page_config(page_title="Marketing AI + Imagini", page_icon="🎨", layout="wide")

# --- 2. Secrete ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
except:
    st.error("Lipsesc cheile API!")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# --- 3. Funcții Backend ---

@st.cache_data(ttl=3600)
def get_available_models():
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
    except: return "No internet data."

# --- FUNCȚIE NOUĂ: Generare Imagine ---
def generate_image_from_prompt(prompt_text):
    """
    Folosește Pollinations.ai (Gratuit, Model Flux/SDXL) pentru a genera imaginea.
    Nu necesită API Key.
    """
    # Curățăm promptul pentru URL
    clean_prompt = prompt_text.replace(" ", "%20")
    # Modelul 'flux' este cel mai bun open-source momentan pentru realism
    url = f"https://pollinations.ai/p/{clean_prompt}?width=1024&height=1024&model=flux&seed=42"
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return BytesIO(response.content)
        else:
            return None
    except Exception as e:
        print(f"Eroare generare imagine: {e}")
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
    slide.placeholders[1].text = "Generat cu AI (Gemini + Flux)"

    # Layout Custom
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
            p.font.size = Pt(16)
            p.space_after = Pt(10)

        # 3. IMAGINE (Dreapta)
        image_prompt = slide_data.get("image_prompt", "Business minimalist product")
        
        # Facem un placeholder vizual în Streamlit ca să știe userul că lucrăm
        # Notă: Nu putem afișa progresul aici ușor, dar funcția rulează.
        
        generated_image_bytes = generate_image_from_prompt(image_prompt)
        
        if generated_image_bytes:
            # Inserăm imaginea reală
            shapes.add_picture(generated_image_bytes, Inches(5.5), Inches(1.8), Inches(4), Inches(4))
        else:
            # Fallback: Dacă pică netul, punem chenarul gri
            shape = shapes.add_shape(1, Inches(5.5), Inches(1.8), Inches(4), Inches(4))
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(200, 200, 200)
            shape.text_frame.text = "Imagine indisponibilă"

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
        prs.save(tmp.name)
        return tmp.name

# --- 4. UI ---

st.title("🎨 Asistent Marketing (Text + Imagini)")

with st.sidebar:
    model_name = st.selectbox("Model", get_available_models(), format_func=lambda x: x.replace("models/", "").upper())
    uploaded_file = st.file_uploader("Catalog PDF", type=['pdf'])

if "messages" not in st.session_state: st.session_state.messages = []

# Procesare PDF
if uploaded_file and "gemini_file" not in st.session_state:
    with st.spinner("Procesez PDF..."):
        st.session_state.gemini_file = upload_to_gemini(uploaded_file)
        st.success("PDF OK")

# Chat UI
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("Ex: Vreau o gamă nouă de produse de vară"):
    if "gemini_file" not in st.session_state: st.error("Pune PDF-ul.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analizez..."):
                web = search_internet(prompt)
                model = genai.GenerativeModel(model_name)
                # Prompt simplificat pentru chat
                resp = model.generate_content([f"Context PDF + Net: {web}. Întrebare: {prompt}", st.session_state.gemini_file])
                st.markdown(resp.text)
                st.session_state.messages.append({"role": "assistant", "content": resp.text})
                st.session_state.last_analysis = resp.text

# --- 5. Generare PPT cu Imagini ---

if "last_analysis" in st.session_state:
    st.divider()
    if st.button("✨ Generează Prezentare cu Imagini AI"):
        
        progress_bar = st.progress(0, text="Pregătesc structura...")
        
        # 1. Structura JSON + Prompturi vizuale
        try:
            json_model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
            
            prompt_slides = f"""
            Pe baza analizei: {st.session_state.last_analysis}
            Generează un JSON pentru 4-5 slide-uri.
            
            IMPORTANT: Pentru fiecare slide, creează un câmp 'image_prompt' care descrie vizual o imagine atractivă pentru acel slide, în engleză (pentru generatorul de imagini).
            
            FORMAT:
            {{
                "presentation_title": "Titlu",
                "slides": [
                    {{ 
                        "title": "Titlu Slide", 
                        "points": ["Idee 1"], 
                        "image_prompt": "Cinematic photo of a modern eco friendly bamboo pen on a wooden desk, soft lighting, 4k" 
                    }}
                ]
            }}
            """
            
            resp = json_model.generate_content(prompt_slides)
            json_text = resp.text.replace("```json", "").replace("```", "").strip()
            
            progress_bar.progress(30, text="Generez imaginile (poate dura 10-20 secunde)...")
            
            # 2. Creare PPTX (Aici se descarcă imaginile)
            pptx_path = create_presentation_with_images(json_text)
            
            progress_bar.progress(100, text="Gata!")
            
            if pptx_path:
                with open(pptx_path, "rb") as f:
                    st.download_button("📥 Descarcă PPTX (Cu Imagini)", f, "Strategie_Vizuala.pptx")
                    
        except Exception as e:
            st.error(f"Eroare: {e}")
