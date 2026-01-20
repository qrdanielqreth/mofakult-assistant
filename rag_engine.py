"""
RAG Engine Module

Core logic for the RAG system. Connects to Pinecone vector store and sets up
the query/chat engine using OpenRouter for LLM inference.

This module is designed to be reusable - it can be imported by the Streamlit app
or integrated into an API later.

Supports both:
- Local development with .env files
- Streamlit Cloud with st.secrets
"""

import os
from dotenv import load_dotenv
from pinecone import Pinecone

from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openrouter import OpenRouter

# Load environment variables (for local development)
load_dotenv()


def get_secret(key: str, default: str = None) -> str:
    """
    Get a secret from environment variables or Streamlit secrets.
    
    Tries in order:
    1. Environment variable (for local dev with .env)
    2. Streamlit secrets (for Streamlit Cloud deployment)
    3. Default value
    
    Args:
        key: The secret key name
        default: Default value if not found
        
    Returns:
        The secret value or default
    """
    # First try environment variable
    value = os.getenv(key)
    if value:
        return value
    
    # Then try Streamlit secrets (only if running in Streamlit)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    
    return default


def get_settings() -> dict:
    """
    Load and validate required secrets from env or Streamlit Cloud.
    
    Returns:
        dict: Configuration settings
        
    Raises:
        ValueError: If required secrets are missing
    """
    required_keys = [
        "OPENROUTER_API_KEY",
        "OPENAI_API_KEY",
        "PINECONE_API_KEY",
    ]
    
    # Check for missing secrets
    missing = [key for key in required_keys if not get_secret(key)]
    if missing:
        raise ValueError(f"Missing required secrets: {', '.join(missing)}")
    
    return {
        "openrouter_api_key": get_secret("OPENROUTER_API_KEY"),
        "openai_api_key": get_secret("OPENAI_API_KEY"),
        "pinecone_api_key": get_secret("PINECONE_API_KEY"),
        "pinecone_index_name": get_secret("PINECONE_INDEX_NAME", "rag-index"),
        "company_name": get_secret("COMPANY_NAME", "Mofakult"),
    }


def get_embed_model() -> OpenAIEmbedding:
    """
    Initialize the OpenAI embedding model.
    
    Returns:
        OpenAIEmbedding: Configured embedding model
    """
    settings = get_settings()
    
    return OpenAIEmbedding(
        model="text-embedding-3-small",
        api_key=settings["openai_api_key"],
        dimensions=1536,
    )


def get_llm() -> OpenRouter:
    """
    Initialize the OpenRouter LLM.
    
    Returns:
        OpenRouter: Configured LLM client for OpenRouter
    """
    settings = get_settings()
    
    return OpenRouter(
        api_key=settings["openrouter_api_key"],
        model="google/gemini-2.0-flash-001",
        temperature=0.1,  # Niedrig für konsistentere, faktenbasierte Antworten
        max_tokens=4096,
        context_window=128000,  # Gemini 2.0 Flash supports 1M tokens, but we use a reasonable limit
    )


def get_vector_store() -> PineconeVectorStore:
    """
    Connect to Pinecone and return the vector store.
    
    Returns:
        PineconeVectorStore: Connected vector store
        
    Raises:
        ValueError: If the Pinecone index doesn't exist
    """
    settings = get_settings()
    
    # Initialize Pinecone client
    pc = Pinecone(api_key=settings["pinecone_api_key"])
    
    # Check if index exists
    index_name = settings["pinecone_index_name"]
    existing_indexes = [idx.name for idx in pc.list_indexes()]
    
    if index_name not in existing_indexes:
        raise ValueError(
            f"Pinecone index '{index_name}' not found. "
            f"Please run ingest.py first to create and populate the index."
        )
    
    # Connect to the index
    pinecone_index = pc.Index(index_name)
    
    return PineconeVectorStore(pinecone_index=pinecone_index)


def get_index() -> VectorStoreIndex:
    """
    Create a VectorStoreIndex from the Pinecone vector store.
    
    Returns:
        VectorStoreIndex: Index ready for querying
    """
    # Configure global settings
    Settings.embed_model = get_embed_model()
    Settings.llm = get_llm()
    
    # Get vector store and create index
    vector_store = get_vector_store()
    
    return VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=Settings.embed_model,
    )


def get_system_prompt() -> str:
    """
    Generate the system prompt with company name.
    
    Returns:
        str: System prompt for the chat engine
    """
    settings = get_settings()
    company_name = settings["company_name"]
    
    return f"""Du bist ein hilfreicher Assistent für {company_name}. Du beantwortest Fragen AUSSCHLIESSLICH basierend auf dem bereitgestellten Kontext aus den Firmendokumenten.

WICHTIGE REGELN:
- Antworte NUR mit Informationen aus dem Kontext - NIEMALS erfinden oder raten!
- Wenn die Information NICHT im Kontext steht, sage klar: "Diese Information habe ich nicht in den Dokumenten gefunden."
- Wenn mehrere widersprüchliche Informationen im Kontext vorhanden sind, weise darauf hin und nenne alle Varianten
- Antworte immer auf Deutsch
- Sei präzise und faktenbezogen
- Bei Fragen zu Personen: Nenne nur Namen die EXPLIZIT im Kontext stehen

VERBOTEN: Namen, Zahlen, Fakten oder Rollen erfinden die nicht im Kontext stehen!"""


def get_chat_engine() -> CondensePlusContextChatEngine:
    """
    Create and return a chat engine with memory for multi-turn conversations.
    
    This is the main entry point for the RAG system. The chat engine:
    - Retrieves relevant context from Pinecone
    - Maintains conversation history
    - Uses OpenRouter (Gemini 2.0 Flash) for response generation
    
    Returns:
        CondensePlusContextChatEngine: Ready-to-use chat engine
    """
    index = get_index()
    
    # Create memory buffer for conversation history
    # Using a reasonable limit that leaves room for context and response
    memory = ChatMemoryBuffer.from_defaults(token_limit=3000)
    
    # Create chat engine with context retrieval
    # Use more chunks for better context coverage
    chat_engine = CondensePlusContextChatEngine.from_defaults(
        retriever=index.as_retriever(similarity_top_k=8),
        memory=memory,
        llm=Settings.llm,
        system_prompt=get_system_prompt(),
        verbose=False,
        context_prompt=(
            "Hier ist der relevante Kontext aus den Firmendokumenten:\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n"
            "Beantworte die Frage NUR basierend auf diesem Kontext. Wenn die Antwort nicht im Kontext steht, sage es ehrlich."
        ),
    )
    
    return chat_engine


def get_query_engine():
    """
    Create and return a simple query engine for single Q&A (no memory).
    
    Useful for API integrations where conversation context isn't needed.
    
    Returns:
        QueryEngine: Ready-to-use query engine
    """
    index = get_index()
    
    return index.as_query_engine(
        similarity_top_k=5,
        streaming=True,
    )


# Quick test when running directly
if __name__ == "__main__":
    print("Testing RAG Engine...")
    
    try:
        settings = get_settings()
        print(f"✓ Environment variables loaded")
        print(f"  - Company: {settings['company_name']}")
        print(f"  - Index: {settings['pinecone_index_name']}")
        
        chat_engine = get_chat_engine()
        print("✓ Chat engine initialized successfully")
        
        # Test query
        response = chat_engine.chat("Hello, what can you help me with?")
        print(f"\nTest response:\n{response}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
