import streamlit as st
import google.generativeai as genai
from tavily import TavilyClient
import PyPDF2
import os

# --- Configurare Pagină ---
st.set_page_config(page_title="Marketing Portfolio Optimizer", page_icon="🚀", layout="wide")

st.title("🚀 Asistent Optimizare Portofoliu (Marketing)")
st.markdown("""
Acest tool analizează catalogul PDF încărcat și folosește internetul pentru a găsi trenduri noi.
""")

# --- Sidebar pentru setări ---
with st.sidebar:
    st.header("Configurare")
    # Aici userul introduce cheile. În producție poți folosi st.secrets
    gemini_api_key = st.text_input("Google Gemini API Key", type="password")
    tavily_api_key = st.text_input("Tavily API Key", type="password")
    
    st.info("Încarcă catalogul, apoi discută cu AI-ul despre optimizare.")
    uploaded_file = st.file_uploader("Încarcă Catalog PDF", type=['pdf'])

# --- Funcții Utilitare ---

def extract_text_from_pdf(pdf_file):
    """Extrage textul din PDF."""
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text

def search_internet(query, api_key):
    """Caută pe net folosind Tavily."""
    try:
        tavily = TavilyClient(api_key=api_key)
        response = tavily.search(query=query, search_depth="advanced", max_results=3)
        context = "\n".join([f"- {res['content']} (Sursa: {res['url']})" for res in response['results']])
        return context
    except Exception as e:
        return f"Eroare la căutarea pe internet: {e}"

# --- Logica Principală ---

if gemini_api_key and tavily_api_key and uploaded_file:
    
    # 1. Configurare AI
    genai.configure(api_key=gemini_api_key)
    
    # Folosim Gemini 1.5 Flash pentru viteză și context mare
    model = genai.GenerativeModel('gemini-1.5-flash')

    # 2. Procesare PDF (doar o dată, salvăm în session_state)
    if "pdf_content" not in st.session_state:
        with st.spinner("Analizez catalogul PDF..."):
            text_content = extract_text_from_pdf(uploaded_file)
            st.session_state["pdf_content"] = text_content
            st.success("Catalog analizat cu succes!")

    # 3. Inițializare Chat
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Afișare istoric chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 4. Input Utilizator
    if prompt := st.chat_input("Ex: Ce produse sunt demodate? Ce trenduri noi sunt pe piață?"):
        
        # Adaugă mesajul utilizatorului
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 5. Generare Răspuns
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            with st.spinner("Caut informații pe internet și analizez catalogul..."):
                # a) Căutăm pe internet context relevant pentru întrebare
                web_context = search_internet(prompt, tavily_api_key)
                
                # b) Construim prompt-ul final pentru Gemini
                final_prompt = f"""
                Ești un expert în Marketing și Management de Produs.
                
                CONTEXT CATALOG COMPANIE (PDF):
                {st.session_state['pdf_content'][:50000]} 
                *(Nota: Am limitat textul pentru siguranță, dar Gemini duce mult mai mult)*

                CONTEXT DIN INTERNET (TRENDURI/COMPETIȚIE):
                {web_context}

                ÎNTREBAREA UTILIZATORULUI:
                {prompt}

                INSTRUCȚIUNI:
                - Analizează produsele din catalog în raport cu informațiile de pe internet.
                - Propune optimizări, eliminări de produse vechi sau idei noi.
                - Fii concis, profesionist și oferă pași acționabili.
                - Răspunde în limba română.
                """

                try:
                    response = model.generate_content(final_prompt)
                    ai_reply = response.text
                except Exception as e:
                    ai_reply = f"A apărut o eroare la generare: {e}"

            # Afișează și salvează răspunsul
            message_placeholder.markdown(ai_reply)
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})

else:
    st.warning("Te rog introdu cheile API în stânga și încarcă un fișier PDF pentru a începe.")
