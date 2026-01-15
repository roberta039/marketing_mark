import streamlit as st
import google.generativeai as genai
from tavily import TavilyClient
import PyPDF2
import os

# --- 1. Configurare Pagină ---
st.set_page_config(
    page_title="Marketing Portfolio Optimizer",
    page_icon="📈",
    layout="wide"
)

# --- 2. Gestionare Secrete (API Keys) ---
# Încercăm să încărcăm cheile din st.secrets (Setările din Streamlit Cloud)
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    TAVILY_API_KEY = st.secrets["TAVILY_API_KEY"]
except FileNotFoundError:
    st.error("⚠️ Cheile API nu sunt configurate! Te rog configurează 'GOOGLE_API_KEY' și 'TAVILY_API_KEY' în Streamlit Secrets.")
    st.stop()

# Configurare Clienti API
genai.configure(api_key=GOOGLE_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# --- 3. Interfața Grafică (UI) ---
st.title("📈 Asistent AI: Optimizare Portofoliu Promoționale")
st.markdown("""
**Salut!** Sunt asistentul tău virtual pentru analiză de produs.
1. Încarcă catalogul PDF curent.
2. Întreabă-mă orice despre optimizare, trenduri sau comparații cu piața.
""")

with st.sidebar:
    st.header("📂 Documente")
    uploaded_file = st.file_uploader("Încarcă Catalogul (PDF)", type=['pdf'])
    
    st.markdown("---")
    st.markdown("**Cum funcționează?**")
    st.markdown("1. AI-ul citește tot PDF-ul.")
    st.markdown("2. Caută pe internet informații live despre trenduri.")
    st.markdown("3. Îți oferă sfaturi strategice.")
    
    if st.button("Șterge Istoric Chat"):
        st.session_state.messages = []
        st.rerun()

# --- 4. Funcții Backend ---

def extract_text_from_pdf(pdf_file):
    """Citește textul din PDF pagină cu pagină."""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        st.error(f"Eroare la citirea PDF-ului: {e}")
        return None

def search_internet(query):
    """Caută pe internet folosind Tavily pentru context actualizat."""
    try:
        # Căutare avansată pentru a obține conținut relevant
        response = tavily_client.search(
            query=query, 
            search_depth="advanced", 
            max_results=5,
            include_answer=True
        )
        
        # Construim un rezumat al surselor găsite
        context_parts = []
        if 'answer' in response:
            context_parts.append(f"Răspuns direct Tavily: {response['answer']}")
        
        for res in response.get('results', []):
            context_parts.append(f"- {res['content']} (Sursa: {res['url']})")
            
        return "\n".join(context_parts)
    except Exception as e:
        return f"Eroare la căutarea pe internet: {e}"

# --- 5. Logica Principală a Aplicației ---

# Inițializare istoric chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# Procesare PDF (doar când se încarcă un fișier nou)
if uploaded_file:
    # Verificăm dacă fișierul a fost deja procesat ca să nu pierdem timp
    if "current_file_name" not in st.session_state or st.session_state.current_file_name != uploaded_file.name:
        with st.spinner("⏳ Citesc și analizez catalogul... (poate dura câteva secunde)"):
            pdf_text = extract_text_from_pdf(uploaded_file)
            if pdf_text:
                st.session_state.pdf_content = pdf_text
                st.session_state.current_file_name = uploaded_file.name
                st.success(f"✅ Catalogul '{uploaded_file.name}' a fost procesat! Poți începe conversația.")
            else:
                st.warning("Nu am putut extrage text din acest PDF.")

# Afișare mesaje anterioare
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Zona de input pentru utilizator
if prompt := st.chat_input("Ex: Ce produse eco-friendly sunt în trend și lipsesc din catalogul nostru?"):
    
    if "pdf_content" not in st.session_state:
        st.error("Te rog încarcă mai întâi un catalog PDF în bara din stânga.")
    else:
        # 1. Adăugăm mesajul utilizatorului în istoric
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Procesare Răspuns AI
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            with st.spinner("🔍 Caut pe internet și compar cu catalogul tău..."):
                
                # a) Cutare pe internet
                web_knowledge = search_internet(prompt)
                
                # b) Configurare Model AI (Gemini 1.5 Flash)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # c) Construire Prompt Complex
                system_instruction = f"""
                Ești un Senior Product Manager și Marketing Strategist pentru o companie de produse promoționale.
                
                SARCINA TA:
                Ajută echipa de marketing să optimizeze portofoliul răspunzând la întrebarea utilizatorului.
                
                DATE DISPONIBILE:
                1. CATALOGUL NOSTRU (PDF): 
                {st.session_state.pdf_content[:60000]} 
                *(Text trunchiat pentru optimizare dacă e prea lung)*
                
                2. INFORMAȚII EXTERNE (INTERNET - TRENDURI/COMPETIȚIE):
                {web_knowledge}
                
                INSTRUCȚIUNI DE RĂSPUNS:
                - Analizează ce avem în catalog vs ce se cere pe piață (conform datelor de pe internet).
                - Fii critic dar constructiv. Dacă un produs e demodat, spune-o clar.
                - Oferă sugestii concrete (nume de produse, materiale, culori).
                - Răspunde în limba Română, formatat frumos cu Markdown (bold, liste).
                """
                
                full_prompt = f"{system_instruction}\n\nÎNTREBAREA UTILIZATORULUI: {prompt}"

                try:
                    # Generare răspuns stream (să apară textul pe măsură ce e scris)
                    response = model.generate_content(full_prompt, stream=True)
                    full_response = ""
                    for chunk in response:
                        if chunk.text:
                            full_response += chunk.text
                            message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                    
                    # Salvare în istoric
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                
                except Exception as e:
                    error_msg = f"A apărut o eroare la generare: {e}"
                    message_placeholder.error(error_msg)
