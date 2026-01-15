import streamlit as st
import google.generativeai as genai
from tavily import TavilyClient
import PyPDF2

# --- 1. Configurare Pagină ---
st.set_page_config(
    page_title="Marketing Portfolio Optimizer",
    page_icon="📈",
    layout="wide"
)

# --- 2. Gestionare Secrete (API Keys) ---
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
Alege modelul AI potrivit, încarcă catalogul și hai să optimizăm portofoliul!
""")

# Dicționar cu modelele disponibile și numele lor prietenoase
AVAILABLE_MODELS = {
    "Gemini 1.5 Flash (Rapid & Context Mare)": "gemini-1.5-flash",
    "Gemini 1.5 Pro (Inteligență Maximă)": "gemini-1.5-pro",
    "Gemini 1.0 Pro (Versiunea Standard)": "gemini-1.0-pro"
}

with st.sidebar:
    st.header("⚙️ Setări AI")
    
    # Selector pentru Model
    selected_model_name = st.selectbox(
        "Alege Modelul AI:",
        list(AVAILABLE_MODELS.keys()),
        index=0, # Default: Flash
        help="Flash este rapid și bun pentru documente mari. Pro este mai lent dar oferă analize mai profunde."
    )
    # Extragem ID-ul tehnic al modelului (ex: 'gemini-1.5-flash')
    model_api_id = AVAILABLE_MODELS[selected_model_name]

    st.divider()
    
    st.header("📂 Documente")
    uploaded_file = st.file_uploader("Încarcă Catalogul (PDF)", type=['pdf'])
    
    st.info(f"Model activ: **{model_api_id}**")
    
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
        response = tavily_client.search(
            query=query, 
            search_depth="advanced", 
            max_results=5,
            include_answer=True
        )
        
        context_parts = []
        if 'answer' in response:
            context_parts.append(f"Răspuns direct Tavily: {response['answer']}")
        
        for res in response.get('results', []):
            context_parts.append(f"- {res['content']} (Sursa: {res['url']})")
            
        return "\n".join(context_parts)
    except Exception as e:
        return f"Eroare la căutarea pe internet: {e}"

# --- 5. Logica Principală a Aplicației ---

if "messages" not in st.session_state:
    st.session_state.messages = []

# Procesare PDF
if uploaded_file:
    if "current_file_name" not in st.session_state or st.session_state.current_file_name != uploaded_file.name:
        with st.spinner("⏳ Citesc și analizez catalogul..."):
            pdf_text = extract_text_from_pdf(uploaded_file)
            if pdf_text:
                st.session_state.pdf_content = pdf_text
                st.session_state.current_file_name = uploaded_file.name
                st.success(f"✅ Catalogul '{uploaded_file.name}' a fost procesat! Poți începe conversația.")
            else:
                st.warning("Nu am putut extrage text din acest PDF.")

# Afișare istoric
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input Utilizator
if prompt := st.chat_input("Ex: Ce produse eco-friendly sunt în trend și lipsesc din catalogul nostru?"):
    
    if "pdf_content" not in st.session_state:
        st.error("Te rog încarcă mai întâi un catalog PDF în bara din stânga.")
    else:
        # Salvare mesaj user
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generare Răspuns
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            
            with st.spinner(f"🔍 Caut pe internet și analizez cu {selected_model_name}..."):
                
                # a) Căutare Internet
                web_knowledge = search_internet(prompt)
                
                # b) Configurare Model Selectat din Listă
                model = genai.GenerativeModel(model_api_id)
                
                # c) Prompt
                system_instruction = f"""
                Ești un Senior Product Manager și Marketing Strategist.
                
                MODEL AI FOLOSIT: {selected_model_name}
                
                SARCINA:
                Ajută echipa de marketing să optimizeze portofoliul.
                
                CONTEXT CATALOG (PDF): 
                {st.session_state.pdf_content[:60000]} 
                
                CONTEXT INTERNET:
                {web_knowledge}
                
                INSTRUCȚIUNI:
                - Analizează ce avem în catalog vs ce se cere pe piață.
                - Fii critic dar constructiv.
                - Oferă sugestii concrete.
                """
                
                full_prompt = f"{system_instruction}\n\nÎNTREBAREA UTILIZATORULUI: {prompt}"

                try:
                    response = model.generate_content(full_prompt, stream=True)
                    full_response = ""
                    for chunk in response:
                        if chunk.text:
                            full_response += chunk.text
                            message_placeholder.markdown(full_response + "▌")
                    
                    message_placeholder.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                
                except Exception as e:
                    message_placeholder.error(f"Eroare generare ({model_api_id}): {e}")
