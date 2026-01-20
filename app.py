"""
RAG Chat Application - Modern Light UI

Streamlit-based chat interface for the RAG system.
Clean, modern light design with smooth interactions.

Supports both:
- Local development with .env files
- Streamlit Cloud with st.secrets

Features:
- Chat with company documents
- Conversation logging to Google Sheets

Usage:
    streamlit run app.py
"""

import streamlit as st
from dotenv import load_dotenv
import os
import time
import uuid

# Load environment variables early (for local development)
load_dotenv()


def get_secret(key: str, default: str = None) -> str:
    """Get a secret from environment variables or Streamlit secrets."""
    # First try environment variable
    value = os.getenv(key)
    if value:
        return value
    
    # Then try Streamlit secrets
    try:
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    
    return default


# Get company name for branding
COMPANY_NAME = get_secret("COMPANY_NAME", "Mofakult")

# Page configuration
st.set_page_config(
    page_title=f"{COMPANY_NAME} Assistant",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Modern Light CSS Design
st.markdown("""
<style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Root variables - Light Theme */
    :root {
        --primary: #2563eb;
        --primary-light: #3b82f6;
        --primary-dark: #1d4ed8;
        --accent: #f97316;
        --bg-main: #f8fafc;
        --bg-white: #ffffff;
        --bg-gray: #f1f5f9;
        --bg-hover: #e2e8f0;
        --text-primary: #0f172a;
        --text-secondary: #475569;
        --text-muted: #94a3b8;
        --border: #e2e8f0;
        --border-light: #f1f5f9;
        --success: #10b981;
        --error: #ef4444;
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
        --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1);
        --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1);
    }
    
    /* Global styles */
    .main, .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: var(--bg-main) !important;
    }
    
    /* Hide Streamlit elements */
    #MainMenu, footer, header {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* ===== HEADER ===== */
    .hero-section {
        text-align: center;
        padding: 2rem 1rem;
        margin-bottom: 0.5rem;
    }
    
    .hero-logo {
        width: 56px;
        height: 56px;
        background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
        border-radius: 16px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 1.75rem;
        margin-bottom: 1rem;
        box-shadow: var(--shadow-md);
    }
    
    .hero-title {
        font-family: 'Inter', sans-serif;
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--text-primary);
        margin-bottom: 0.5rem;
        letter-spacing: -0.025em;
    }
    
    .hero-subtitle {
        font-family: 'Inter', sans-serif;
        font-size: 0.95rem;
        color: var(--text-secondary);
        font-weight: 400;
        max-width: 420px;
        margin: 0 auto;
        line-height: 1.6;
    }
    
    /* ===== CHAT CONTAINER ===== */
    [data-testid="stChatMessageContent"] {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.925rem !important;
        line-height: 1.65 !important;
        color: var(--text-primary) !important;
    }
    
    [data-testid="stChatMessageContent"] p {
        margin-bottom: 0.75rem;
    }
    
    [data-testid="stChatMessageContent"] p:last-child {
        margin-bottom: 0;
    }
    
    /* User message */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background: var(--bg-white) !important;
        border-radius: 16px !important;
        border: 1px solid var(--border) !important;
        margin: 0.75rem 0 !important;
        padding: 1rem 1.25rem !important;
        box-shadow: var(--shadow-sm) !important;
    }
    
    /* Assistant message */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%) !important;
        border-radius: 16px !important;
        border: 1px solid #dbeafe !important;
        margin: 0.75rem 0 !important;
        padding: 1rem 1.25rem !important;
    }
    
    /* Avatar styling */
    [data-testid="stChatMessageAvatarUser"] {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
        border-radius: 10px !important;
    }
    
    [data-testid="stChatMessageAvatarAssistant"] {
        background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%) !important;
        border-radius: 10px !important;
    }
    
    /* ===== CHAT INPUT ===== */
    .stChatInput > div {
        background: var(--bg-white) !important;
        border: 2px solid var(--border) !important;
        border-radius: 14px !important;
        padding: 0.25rem !important;
        transition: all 0.2s ease;
        box-shadow: var(--shadow-sm);
    }
    
    .stChatInput > div:focus-within {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
    }
    
    .stChatInput textarea {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.925rem !important;
        color: var(--text-primary) !important;
    }
    
    .stChatInput textarea::placeholder {
        color: var(--text-muted) !important;
    }
    
    /* Send button */
    .stChatInput button {
        background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%) !important;
        border-radius: 10px !important;
        transition: all 0.2s ease !important;
    }
    
    .stChatInput button:hover {
        transform: scale(1.05) !important;
        box-shadow: var(--shadow-md) !important;
    }
    
    /* ===== SIDEBAR ===== */
    [data-testid="stSidebar"] {
        background: var(--bg-white) !important;
        border-right: 1px solid var(--border);
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: var(--text-secondary);
    }
    
    [data-testid="stSidebar"] h3 {
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 0.9rem;
    }
    
    /* Sidebar stats */
    .sidebar-stat {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem 0;
        border-bottom: 1px solid var(--border-light);
    }
    
    .sidebar-stat-label {
        color: var(--text-secondary);
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    .sidebar-stat-value {
        color: var(--text-primary);
        font-weight: 600;
        font-size: 0.9rem;
        background: var(--bg-gray);
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
    }
    
    /* Clear button */
    [data-testid="stSidebar"] .stButton button {
        width: 100%;
        background: var(--bg-white) !important;
        color: var(--error) !important;
        border: 1px solid #fecaca !important;
        border-radius: 10px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        padding: 0.6rem 1rem !important;
        transition: all 0.2s ease !important;
    }
    
    [data-testid="stSidebar"] .stButton button:hover {
        background: #fef2f2 !important;
        border-color: #fca5a5 !important;
    }
    
    /* Tips card */
    .tips-box {
        background: var(--bg-gray);
        border-radius: 12px;
        padding: 1rem;
        margin-top: 1rem;
    }
    
    .tips-box h4 {
        color: var(--text-primary);
        font-size: 0.8rem;
        font-weight: 600;
        margin-bottom: 0.6rem;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    
    .tips-box ul {
        margin: 0;
        padding-left: 1rem;
    }
    
    .tips-box li {
        color: var(--text-secondary);
        font-size: 0.8rem;
        margin-bottom: 0.35rem;
        line-height: 1.4;
    }
    
    /* ===== SPINNER ===== */
    .stSpinner > div {
        border-color: var(--primary) transparent transparent !important;
    }
    
    /* ===== ERROR STATE ===== */
    .error-box {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 12px;
        padding: 1.25rem;
        margin: 1.5rem 0;
    }
    
    .error-box h4 {
        color: #dc2626;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 0.4rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .error-box p {
        color: #b91c1c;
        font-size: 0.875rem;
        margin: 0;
    }
    
    /* ===== RESPONSIVE ===== */
    @media (max-width: 768px) {
        .hero-title {
            font-size: 1.5rem;
        }
        .hero-subtitle {
            font-size: 0.875rem;
        }
    }
    
    /* Footer */
    .footer-text {
        text-align: center;
        color: var(--text-muted);
        font-size: 0.7rem;
        margin-top: 2rem;
        padding-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def initialize_chat_engine():
    """
    Initialize the RAG chat engine.
    Returns the engine or (None, error_message) if initialization fails.
    """
    try:
        from rag_engine import get_chat_engine
        return get_chat_engine()
    except ValueError as e:
        return None, str(e)
    except Exception as e:
        return None, f"Initialisierung fehlgeschlagen: {str(e)}"


def display_header():
    """Display the modern hero header."""
    st.markdown(f"""
    <div class="hero-section">
        <div class="hero-logo">💬</div>
        <h1 class="hero-title">{COMPANY_NAME} Assistant</h1>
        <p class="hero-subtitle">Frag mich alles über eure Firmendokumente – ich durchsuche die Wissensdatenbank und liefere dir präzise Antworten.</p>
    </div>
    """, unsafe_allow_html=True)


def display_error(error_message: str):
    """Display an error message with modern styling."""
    st.markdown(f"""
    <div class="error-box">
        <h4>⚠️ Setup erforderlich</h4>
        <p>{error_message}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    ### 🛠️ Schnellstart
    
    1. **Umgebungsvariablen** – `env.template` → `.env` kopieren, API-Keys eintragen
    2. **Google Credentials** – `credentials.json` ins Projektverzeichnis
    3. **Indexieren** – `python ingest.py` ausführen
    4. **Starten** – `streamlit run app.py`
    """)


def display_sidebar():
    """Display the sidebar with stats and controls."""
    with st.sidebar:
        st.markdown("### 📊 Session")
        
        # Stats
        msg_count = len(st.session_state.messages)
        st.markdown(f"""
        <div class="sidebar-stat">
            <span class="sidebar-stat-label">Nachrichten</span>
            <span class="sidebar-stat-value">{msg_count}</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Clear button
        if st.button("🗑️ Chat löschen", use_container_width=True):
            st.session_state.messages = []
            if st.session_state.chat_engine:
                st.session_state.chat_engine = None
                st.session_state.init_error = None
            st.rerun()
        
        # Tips
        st.markdown("""
        <div class="tips-box">
            <h4>💡 Tipps</h4>
            <ul>
                <li>Stelle spezifische Fragen</li>
                <li>Der Assistent merkt sich den Kontext</li>
                <li>Bei Unsicherheit nachfragen</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="footer-text">
            Powered by RAG Technology
        </div>
        """, unsafe_allow_html=True)


def get_session_id() -> str:
    """Generate or retrieve a unique session ID."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]
    return st.session_state.session_id


def main():
    """Main application function."""
    display_header()
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "chat_engine" not in st.session_state:
        st.session_state.chat_engine = None
        st.session_state.init_error = None
    
    # Initialize chat logger
    if "chat_logger" not in st.session_state:
        try:
            from chat_logger import get_logger
            st.session_state.chat_logger = get_logger()
        except Exception as e:
            st.session_state.chat_logger = None
            print(f"[App] Chat logger not available: {e}")
    
    # Initialize chat engine
    if st.session_state.chat_engine is None and st.session_state.init_error is None:
        with st.spinner("Verbinde mit Wissensdatenbank..."):
            result = initialize_chat_engine()
            if isinstance(result, tuple):
                st.session_state.init_error = result[1]
            else:
                st.session_state.chat_engine = result
    
    # Handle initialization error
    if st.session_state.init_error:
        display_error(st.session_state.init_error)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Erneut verbinden", use_container_width=True):
                st.session_state.chat_engine = None
                st.session_state.init_error = None
                st.rerun()
        return
    
    # Display sidebar
    display_sidebar()
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Stelle eine Frage..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Suche in Dokumenten..."):
                start_time = time.time()
                try:
                    response = st.session_state.chat_engine.chat(prompt)
                    response_text = str(response)
                    response_time = time.time() - start_time
                    
                    st.markdown(response_text)
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text
                    })
                    
                    # Log conversation to Google Sheets
                    if st.session_state.chat_logger and st.session_state.chat_logger.enabled:
                        try:
                            st.session_state.chat_logger.log_conversation(
                                session_id=get_session_id(),
                                user_message=prompt,
                                assistant_response=response_text,
                                response_time=response_time
                            )
                        except Exception as log_error:
                            print(f"[App] Logging error: {log_error}")
                    
                except Exception as e:
                    error_msg = f"Fehler: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })


if __name__ == "__main__":
    main()
