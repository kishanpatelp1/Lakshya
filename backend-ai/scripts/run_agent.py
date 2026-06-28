import sys
import os
import uuid
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

DEFAULT_PDF_PATH = str(ROOT_DIR / "data" / "RIL-Integrated-Annual-Report-2024-25.pdf")
DEFAULT_QUERY = "What are the key financial highlights and revenue figures from the uploaded document?"

PROVIDERS = ["ollama", "deepseek", "openai", "groq", "claude"]


def extract_pdf_chunks(pdf_path, max_pages=10):
    try:
        import fitz
        print("Using PyMuPDF for extraction...")
        doc = fitz.open(pdf_path)
        return [page.get_text() for idx, page in enumerate(doc) if idx < max_pages]
    except ImportError:
        try:
            print("PyMuPDF not found, falling back to PyPDFLoader...")
            from langchain_community.document_loaders import PyPDFLoader
            loader = PyPDFLoader(pdf_path)
            docs = loader.load_and_split()
            return [doc.page_content for doc in docs[:max_pages]]
        except ImportError:
            print("Please install PyMuPDF (fitz) or langchain-community")
            return []


def parse_args():
    parser = argparse.ArgumentParser(description="Run local PDF analysis through the research agent.")
    parser.add_argument(
        "--pdf",
        default=DEFAULT_PDF_PATH,
        help="Absolute or relative path to input PDF.",
    )
    parser.add_argument(
        "--query",
        default=DEFAULT_QUERY,
        help="User query to analyze against PDF content.",
    )
    parser.add_argument(
        "--expertise-level",
        default="intermediate",
        choices=["beginner", "intermediate", "advanced"],
        help="Controls explanation depth in synthesis output.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Maximum pages to extract from the PDF.",
    )
    parser.add_argument(
        "--provider",
        choices=PROVIDERS,
        default=None,
        help=(
            f"LLM provider to use: {', '.join(PROVIDERS)}. "
            "Overrides LLM_PROVIDER in .env for this run. "
            "Example: --provider claude"
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Model name override for this run (overrides LLM_MODEL in .env). "
            "Example: --model claude-opus-4-7"
        ),
    )
    return parser.parse_args()


def run():
    args = parse_args()

    # Apply provider/model overrides BEFORE importing src modules so that
    # get_settings() (which is lru_cache'd) picks them up on first access.
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
        print(f"[CLI] Provider overridden to: {args.provider}")
    if args.model:
        os.environ["LLM_MODEL"] = args.model
        print(f"[CLI] Model overridden to: {args.model}")

    # Deferred import — must happen after env overrides above.
    from src.agents import build_research_agent

    pdf_path = os.path.abspath(args.pdf)
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        return

    print("Extracting text from PDF...")
    chunks = extract_pdf_chunks(pdf_path, max_pages=max(1, args.max_pages))
    if not chunks:
        print("Failed to extract chunks")
        return

    print(f"Extracted {len(chunks)} pages/chunks from PDF.")

    upload_id = uuid.uuid4()
    user_id = uuid.uuid4()
    thread_id = str(uuid.uuid4())

    user_message = (
        f"{args.query}\n\n"
        f"[Context: user_id={user_id}, upload_id={upload_id}, "
        f"expertise_level={args.expertise_level}]\n\n"
        f"--- Extracted PDF content (first {len(chunks)} pages) ---\n"
        + "\n\n---PAGE BREAK---\n\n".join(chunks)
    )

    print("Building deep agent...")
    agent = build_research_agent()

    print(f"Running agent with query: '{args.query}'...")
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config={"configurable": {"thread_id": thread_id}},
    )

    response_text = result["messages"][-1].content

    print("\n" + "=" * 50)
    print("AGENT RESPONSE:")
    print("=" * 50)
    print(response_text)


if __name__ == "__main__":
    run()
