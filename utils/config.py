import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel

# Determine project base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Storage directories
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Configuration values
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Databases paths
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "personal_brain.db"))
# Ensure relative paths are resolved against base directory
if not os.path.isabs(DATABASE_PATH):
    DATABASE_PATH = str(BASE_DIR / DATABASE_PATH)

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", str(DATA_DIR / "faiss_index"))
if not os.path.isabs(FAISS_INDEX_PATH):
    FAISS_INDEX_PATH = str(BASE_DIR / FAISS_INDEX_PATH)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def get_llm() -> BaseChatModel:
    """Initializes and returns the configured LangChain chat model.

    Raises ValueError if provider settings or API keys are missing.
    """
    if LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not set. Please update your d:\\personal_ai_os\\.env file."
            )
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
            temperature=0.2
        )
        
    elif LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is not set. Please update your d:\\personal_ai_os\\.env file."
            )
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GEMINI_API_KEY,
            temperature=0.2
        )
        
    elif LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_MODEL,
            temperature=0.2
        )
        
    else:
        raise ValueError(
            f"Unsupported LLM provider '{LLM_PROVIDER}'. Choose from: 'openai', 'gemini', 'ollama'."
        )
