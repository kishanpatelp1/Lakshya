"""LLM and embedding factory - supports Ollama, DeepSeek API, OpenAI, and Groq."""

from typing import Any

from src.config import get_settings


def get_llm(model: str | None = None, temperature: float = 0.3) -> Any:
    """Get the configured LLM (Ollama/DeepSeek/OpenAI/Groq)."""
    s = get_settings()
    model = s.get_llm_model(model)
    temp = temperature if temperature is not None else s.llm_temperature

    if s.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            base_url=s.ollama_base_url,
            temperature=temp,
        )

    if s.llm_provider == "deepseek":
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model,
                api_key=s.deepseek_api_key or "",
                base_url=s.deepseek_base_url,
                temperature=temp,
            )
        except ImportError:
            raise RuntimeError("langchain-openai required for DeepSeek API. Install: pip install langchain-openai")

    if s.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=s.openai_api_key or "",
            temperature=temp,
        )

    if s.llm_provider == "groq":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=s.groq_api_key or "",
            base_url=s.groq_base_url,
            temperature=temp,
        )

    if s.llm_provider == "claude":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=s.anthropic_api_key or "",
            temperature=temp,
        )

    raise ValueError(f"Unknown llm_provider: {s.llm_provider}")


def get_embeddings() -> Any:
    """Get the configured embedding model (Ollama nomic-embed-text / OpenAI)."""
    s = get_settings()

    if s.embedding_provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=s.embedding_model,
            base_url=s.ollama_base_url,
        )

    if s.embedding_provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=s.embedding_model or "text-embedding-3-small",
            api_key=s.openai_api_key or "",
        )

    raise ValueError(f"Unknown embedding_provider: {s.embedding_provider}")


def get_embedding_dim() -> int:
    """Return embedding dimension for the current config."""
    return get_settings().embedding_dim
