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
    st.error("⚠️ Cheile API nu sunt configurate! Configurează secrets.toml sau Streamlit Cloud Secrets.")
    st.stop()

# Configurare Clienți API
genai.configure(api_key=GOOGLE_API_KEY)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# --- 3. Funcție pentru preluarea modelelor disponibile ---
@st.cache_data(ttl=3600) # Salvăm lista în cache 1 oră ca să nu interogăm Google la fiecare click
def get_available_gemini_models():
    """Interoghează API-ul Google și returnează doar modelele Gemini generative."""
    models_list = []
    try:
        for m in genai.list_models():
            # Filtrăm: Vrem doar modele 'gemini' care suportă 'generateContent'
            if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name:
                models_list.append(m.name)
        # Le sortăm invers alfabetic (de obicei cele mai noi '1.5' apar ultimele sau primele în funcție de nume)
        models_list.sort(reverse=True)
        return models_list
    except Exception as e:
        st.error(f"Nu am putut prelua lista de modele: {e}")
        return ["models/gemini-1.5-flash"] # Fallback în caz de eroare

# --- 4. Interfața Grafică (UI) ---
st.title("📈 Asistent AI: Optimizare Portofoliu")
st.markdown("Analiză dinamică folosind modelele live de la Google.")

with st.sidebar:
    st.header("⚙️ Configurare AI")
    
    # Preluăm lista live
    available_models = get_available_gemini_models()
    
    # Selector Dinamic
    if available_models:
        selected_model_name = st.selectbox(
            "Selectează Modelul AI (Live din Google):",
            available_models,
            index=0, # Selectează primul implicit
            format_func=lambda x: x.replace("models/", "").upper() # Afișare mai curată (fără 'models/')
        )
    else:
        st.error("Niciun model disponibil.")
        st.stop()

    st.divider()
    
    st.header("📂 Documente")
    uploaded_file = st.file_uploader("Încarcă Catalogul (PDF)", type=['pdf'])
    
    if st.button("🗑️ Șterge Istoric Chat"):
        st.session_state.messages = []
        st.rerun()

# --- 5. Funcții Backend ---

def extract_text_from_pdf(pdf_file):
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        st.error(f"Eroare PDF: {e}")
        return None

def search_internet(query):
    try:
        response = tavily_client.search(query=query, search_depth="advanced", max_results=5, include_answer=True)
        context_parts = []
        if 'answer' in response:
            context_parts.append(f"Tavily Answer: {response['answer']}")
        for res in response.get('results', []):
            context_parts.append(f"- {res['content']} (Sursa: {res['url']})")
        return "\n".join(context_parts)
    except Exception as e:
        return f"Eroare Tavily: {e}"

# --- 6. Logica Principală ---

if "messages" not in st.session_state:
    st.session_state.messages = []

# Procesare PDF
if uploaded_file:
    if "current_file_name" not in st.session_state or st.session_state.current_file_name != uploaded_file.name:
        with st.spinner("⏳ Procesez catalogul..."):
            pdf_text = extract_text_from_pdf(uploaded_file)
            if pdf_text:
                st.session_state.pdf_content = pdf_text
                st.session_state.current_file_name = uploaded_file.name
                st.success(f"✅ Gata! Catalog analizat.")

# Afișare Chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input User
if prompt := st.chat_input("Întreabă ceva despre catalog..."):
    
    if "pdf_content" not in st.session_state:
        st.error("Te rog încarcă PDF-ul.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            msg_placeholder = st.empty()
            
            with st.spinner(f"Rulez modelul {selected_model_name.replace('models/', '')}..."):
                
                # Context Internet
                web_data = search_internet(prompt)
                
                # Configurare Model Dinamic
                model = genai.GenerativeModel(selected_model_name)
                
                # Prompt
                full_prompt = f"""
                Ești expert în Marketing.
                CATALOG PDF: {st.session_state.pdf_content[:60000]}
                INTERNET DATA: {web_data}
                ÎNTREBARE: {prompt}
                Răspunde detaliat în română.
                """

                try:
                    response = model.generate_content(full_prompt, stream=True)
                    full_resp = ""
                    for chunk in response:
                        if chunk.text:
                            full_resp += chunk.text
                            msg_placeholder.markdown(full_resp + "▌")
                    msg_placeholder.markdown(full_resp)
                    st.session_state.messages.append({"role": "assistant", "content": full_resp})
                except Exception as e:
                    msg_placeholder.error(f"Eroare generare: {e}")
