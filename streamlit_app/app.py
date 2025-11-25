"""Streamlit frontend for mini-lumina RAG system."""

import streamlit as st
import requests
import os
from typing import Dict, Any

# Configure page
st.set_page_config(
    page_title="mini-lumina",
    page_icon="🔦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Backend URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def check_backend_health() -> bool:
    """Check if backend is healthy."""
    try:
        response = requests.get(f"{BACKEND_URL}/healthz", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def ask_question(
    question: str,
    top_k: int = 5,
    temperature: float = 0.7,
    filter_criteria: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Send question to backend API.

    Args:
        question: User question
        top_k: Number of documents to retrieve
        temperature: LLM temperature
        filter_criteria: Optional metadata filters

    Returns:
        API response
    """
    try:
        payload = {
            "question": question,
            "top_k": top_k,
            "temperature": temperature,
        }

        if filter_criteria:
            payload["filter_criteria"] = filter_criteria

        response = requests.post(
            f"{BACKEND_URL}/ask",
            json=payload,
            timeout=60,
        )

        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        st.error("Request timed out. The backend might be processing a complex query.")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot connect to backend at {BACKEND_URL}. Is it running?")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"API error: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return None


def main():
    """Main Streamlit app."""

    # Header
    st.title("🔦 mini-lumina")
    st.markdown("*A minimal RAG system powered by MongoDB Atlas vector search*")

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")

        # Backend health check
        if check_backend_health():
            st.success(f"✅ Connected to backend")
        else:
            st.error(f"❌ Backend unavailable at {BACKEND_URL}")
            st.info("Make sure the FastAPI backend is running.")

        st.markdown("---")

        # Retrieval settings
        st.subheader("Retrieval Settings")

        top_k = st.slider(
            "Number of documents to retrieve",
            min_value=1,
            max_value=20,
            value=5,
            help="How many relevant documents to retrieve from the database",
        )

        temperature = st.slider(
            "LLM Temperature",
            min_value=0.0,
            max_value=2.0,
            value=0.7,
            step=0.1,
            help="Higher values make output more random, lower values more deterministic",
        )

        st.markdown("---")

        # Filters (optional)
        st.subheader("Filters (Optional)")

        use_filters = st.checkbox("Enable metadata filters")

        filter_criteria = None
        if use_filters:
            filter_key = st.text_input(
                "Filter key",
                placeholder="metadata.source",
                help="Example: metadata.source",
            )
            filter_value = st.text_input(
                "Filter value",
                placeholder="document.pdf",
                help="Example: document.pdf",
            )

            if filter_key and filter_value:
                filter_criteria = {filter_key: filter_value}
                st.info(f"Filter: `{filter_key} = {filter_value}`")

        st.markdown("---")

        # About
        st.subheader("About")
        st.markdown(
            """
        **mini-lumina** is a production-ready RAG system featuring:
        - MongoDB Atlas vector search
        - OpenAI/Azure OpenAI embeddings
        - FastAPI backend
        - Docker deployment
        - CI/CD with GitHub Actions
        """
        )

    # Main content
    st.markdown("---")

    # Question input
    question = st.text_area(
        "Ask a question",
        placeholder="What would you like to know?",
        height=100,
        help="Enter your question and press Ctrl+Enter or click 'Ask'",
    )

    col1, col2, col3 = st.columns([1, 1, 4])

    with col1:
        ask_button = st.button("🔍 Ask", type="primary", use_container_width=True)

    with col2:
        clear_button = st.button("🗑️ Clear", use_container_width=True)

    if clear_button:
        st.rerun()

    # Process question
    if ask_button or (question and st.session_state.get("auto_submit")):
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Thinking..."):
                result = ask_question(
                    question=question,
                    top_k=top_k,
                    temperature=temperature,
                    filter_criteria=filter_criteria,
                )

            if result:
                st.markdown("---")

                # Display answer
                st.subheader("💡 Answer")
                st.markdown(result["answer"])

                # Display metadata
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Response time", f"{result['latency_ms']:.0f} ms")
                with col2:
                    st.metric("Sources retrieved", len(result["sources"]))

                st.markdown("---")

                # Display sources
                st.subheader("📚 Sources")

                if result["sources"]:
                    for i, source in enumerate(result["sources"], 1):
                        with st.expander(
                            f"Source {i} (Score: {source['score']:.4f})",
                            expanded=(i == 1),
                        ):
                            st.markdown(f"**Text:**\n\n{source['text']}")

                            if source["metadata"]:
                                st.markdown("**Metadata:**")
                                for key, value in source["metadata"].items():
                                    st.text(f"  • {key}: {value}")
                else:
                    st.info("No sources found.")

    # Examples
    st.markdown("---")
    st.subheader("💡 Example Questions")

    example_col1, example_col2, example_col3 = st.columns(3)

    example_questions = [
        "What is machine learning?",
        "Explain neural networks",
        "How does deep learning work?",
    ]

    for i, (col, example) in enumerate(
        zip([example_col1, example_col2, example_col3], example_questions)
    ):
        with col:
            if st.button(example, key=f"example_{i}", use_container_width=True):
                st.session_state.question = example
                st.rerun()

    # Footer
    st.markdown("---")
    st.markdown(
        "<center>Built with ❤️ using FastAPI, MongoDB Atlas, and Streamlit</center>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
