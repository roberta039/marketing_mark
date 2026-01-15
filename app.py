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
import random
import time 

# --- 1. Configurare Pagină ---
st.set_page_config(page_title="Marketing AI (Stable)", page_icon="🎨", layout="wide")

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

# --- FUNCȚIE GENERARE IMAGINE CU SISTEM ANTI-BLOCK ---
def generate_image_free(prompt_text):
    """
    Generează imagine cu Pollinations.
    INCLUDE: Retry logic și pauze mari pentru a evita 'Rate Limit'.
    """
    # Încercăm de maxim 3 ori dacă primim eroare
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # 1. Pauză Variabilă (Foarte importantă!)
            # Așteptăm între 5 și 8 secunde aleatoriu. Asta păcălește serverul că suntem umani.
            sleep_time = random.uniform(5, 8) 
            # Dacă e a doua încercare (după eroare), așteptăm mai mult (10s)
            if attempt > 0:
                sleep_time = 12
                print(f"Reîncercare {attempt}... Aștept {sleep_time} secunde.")
            
            time.sleep(sleep_time)

            # 2. Pregătire URL
            short_prompt = prompt_text[:200]
            encoded_prompt = urllib.parse.quote(short_prompt)
            random_seed = random.randint(1, 999999)
            
            # URL Pollinations
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&model=flux&nologo=true&seed={random_seed}"
            
            # 3. Headers (Ca un browser real)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://google.com"
            }
            
            # 4. Request
            response = requests.get(url, headers=headers, timeout=40)
            
            # 5. Verificare Succes
            if response.status_code == 200:
                # Verificăm dacă am primit chiar o imagine, nu un text de eroare
                if "image" in response.headers.get("Content-Type", ""):
                    return BytesIO(response.content)
            elif response.status_code == 429:
                print("Rate limit atins. Mai încerc o dată...")
                continue # Trece la următoarea iterație a buclei (reîncearcă)

        except Exception as e:
            print(f"Eroare încercare {attempt}: {e}")
            
    # Dacă am ieșit din buclă fără succes
    return None

def create_presentation_with_images(slides_json, progress_callback=None):
    prs = Presentation()
    try:
        data = json.loads(slides_json)
    except:
        return None

    # Slide Titlu
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = data.get("presentation_title", "Marketing Strategy")
    slide.placeholders[1].text = "Generat Automat"

    # Layout Custom
    blank_layout = prs.slide_layouts[6] 
    
    total_slides = len(data.get("slides", []))

    for i, slide_data in enumerate(data.get("slides", [])):
        
        # Actualizăm bara de progres din interfață
        if progress_callback:
            progress_callback(int((i / total_slides) * 80) + 20, f"Generez Slide {i+1}/{total_slides} (Aștept serverul foto)...")

        slide = prs.slides.add_slide(blank_layout)
        shapes = slide.shapes
        
        # Titlu
        tb = shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(1))
        tb.text_frame.paragraphs[0].text = slide_data.get("title", "Slide")
        tb.text_frame.paragraphs[0].font.size = Pt(32)
        tb.text_frame.paragraphs[0].font.bold = True
        tb.text_frame.paragraphs[0].font.color.rgb = RGBColor(0, 51, 102)

        # Body
        tb_body = shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(4.5), Inches(5))
        tf = tb_body.text_frame
        tf.word_wrap = True
        for point in slide_data.get("points", []):
            p = tf.add_paragraph()
            p.text = "• " + point
            p.font.size = Pt(18)
            p.space_after = Pt(12)

        # IMAGINE
        image_prompt = slide_data.get("image_prompt", "")
        image_bytes = None
        
        if image_prompt:
            image_bytes = generate_image_free(image_prompt)
        
        if image_bytes:
            try:
                shapes.add_picture(image_bytes, Inches(5.5), Inches(1.8), Inches(4.2), Inches(4.2))
            except:
                image_bytes = None
        
        if not image_bytes:
            # Fallback
            shape = shapes.add_shape(1, Inches(5.5), Inches(1.8), Inches(4.2), Inches(4.2))
            shape.fill.solid()
            shape.fill.fore_color.rgb = RGBColor(220, 220, 220)
            tf_shape = shape.text_frame
            tf_shape.text = "Imagine Indisponibilă\n(Rate Limit)"
            tf_shape.paragraphs[0].alignment = PP_ALIGN.CENTER
            tf_shape.paragraphs[0].font.color.rgb = RGBColor(100,100,100)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp:
        prs.save(tmp.name)
        return tmp.name

# --- 4. UI ---

st.title("🚀 Asistent Marketing (Stabilizat)")

with st.sidebar:
    st.header("Configurare")
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

if prompt := st.chat_input("Ex: Vreau produse premium"):
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
    if st.button("✨ Generează Prezentare (Mod Lent & Sigur)"):
        
        progress_bar = st.progress(0, text="Structura prezentării...")
        
        try:
            try:
                json_model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
            except:
                json_model = genai.GenerativeModel(model_name)

            prompt_slides = f"""
            Pe baza analizei: {st.session_state.last_analysis}
            Generează JSON pentru 4-5 slide-uri.
            Include 'image_prompt' (în ENGLEZĂ, max 15 cuvinte).
            
            FORMAT:
            {{
                "presentation_title": "Titlu",
                "slides": [
                    {{ "title": "Titlu", "points": ["Punct 1"], "image_prompt": "Red pen on desk" }}
                ]
            }}
            """
            
            resp = json_model.generate_content(prompt_slides)
            json_text = resp.text.replace("```json", "").replace("```", "").strip()
            
            # Apelăm funcția cu callback pentru progres
            # Asta îi va arăta utilizatorului că nu s-a blocat, ci doar așteaptă
            pptx_path = create_presentation_with_images(json_text, progress_bar.progress)
            
            progress_bar.progress(100, text="Gata! Poți descărca.")
            
            if pptx_path:
                with open(pptx_path, "rb") as f:
                    st.download_button("📥 Descarcă PPTX", f, "Prezentare_Finala.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")
            else:
                st.error("Eroare la generare fișier.")
                
        except Exception as e:
            st.error(f"Eroare proces: {e}")
