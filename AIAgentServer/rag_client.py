import json
import os
import math
from typing import List, Tuple, Optional, Iterable, Hashable, Dict, Any
from pathlib import Path

import torch
from sentence_transformers import CrossEncoder
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_openai.embeddings import OpenAIEmbeddings
from dotenv import load_dotenv
load_dotenv()

def rerank_documents(
    query: str,
    documents: List[Document],
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
) -> List[Tuple[Document, float]]:
    """
    Reranks a list of documents based on a query using a CrossEncoder model.

    Uses sigmoid(raw_logit) so scores are in [0, 1], where:
      - 1.0 ~ very strong match
      - 0.5 ~ neutral / ~50% similarity
      - 0.0 ~ very weak match
    """
    if not documents:
        return []

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CrossEncoder(reranker_model_name, device=device)

    sentence_pairs = [[query, doc.page_content] for doc in documents]
    raw_scores = model.predict(sentence_pairs)  # unbounded logits

    # Convert raw logits → probability-like similarity [0, 1]
    normalized_scores = [
        torch.sigmoid(torch.tensor(s)).item()
        for s in raw_scores
    ]

    doc_scores = sorted(
        zip(documents, normalized_scores),
        key=lambda x: x[1],
        reverse=True,
    )
    return doc_scores


def _default_dedupe_key(doc: Document) -> Hashable:
    """
    Heuristic for determining a uniqueness key for a Document.
    Adjust this to your metadata schema (e.g., 'issue_key', 'jira_key', 'issue_id').
    """
    md = doc.metadata or {}
    # Prefer specific IDs if they exist
    for candidate_key in ("issue_key", "jira_key", "issue_id", "source", "id"):
        if candidate_key in md:
            return md[candidate_key]

    # Fallback: page_content (can be long, but deterministic)
    return doc.page_content


def dedupe_reranked_documents(
    reranked: Iterable[Tuple[Document, float]],
    key_fn=_default_dedupe_key,
) -> List[Tuple[Document, float]]:
    """
    Remove duplicate documents from a reranked list while preserving order.
    """
    seen = set()
    unique_results: List[Tuple[Document, float]] = []

    for doc, score in reranked:
        key = key_fn(doc)
        if key in seen:
            continue
        seen.add(key)
        unique_results.append((doc, score))

    return unique_results


def _parse_jira_issue_from_content(
    content: str,
    metadata: Optional[dict] = None,
) -> Dict[str, Optional[str]]:
    """
    Parse a JIRA issue from the Document.page_content text.

    Expected format (lines starting with these prefixes):
      Issue Key:
      Description:
      Steps to Reproduce:
      Root Cause:
      Fix Implemented:
    """
    metadata = metadata or {}

    # Initialize defaults
    issue_key = None
    description = None
    steps = None
    root_cause = None
    fix_implemented = None

    # Simple line-based parsing
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.lower().startswith("issue key:"):
            issue_key = line.split(":", 1)[1].strip()
        elif line.lower().startswith("description:"):
            description = line.split(":", 1)[1].strip()
        elif line.lower().startswith("steps to reproduce:"):
            steps = line.split(":", 1)[1].strip()
        elif line.lower().startswith("root cause:"):
            root_cause = line.split(":", 1)[1].strip()
        elif line.lower().startswith("fix implemented:"):
            fix_implemented = line.split(":", 1)[1].strip()

    # Fallback to metadata if issue key is still missing
    if not issue_key:
        issue_key = metadata.get("issue_key") or metadata.get("jira_key")

    # return {
    #     "issue_key": issue_key,
    #     "description": description,
    #     "steps_to_reproduce": steps,
    #     "root_cause": root_cause,
    #     "fix_implemented": fix_implemented,
    # }
    return {
        "issue_key": issue_key,
        "description": description,
        "root_cause": root_cause,
        "fix_implemented": fix_implemented,
    }


def query_jira_rag(
    query_text: str,
    persist_dir: str = Path(__file__).parent.parent / "db" / "chroma" / "jira",
    k: int = 10,
    similarity_threshold: float = 0.5,
    reranker_model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2",
) -> Optional[Dict[str, Any]]:
    """
    Queries the Chroma vector database, reranks the results, deduplicates them,
    filters by similarity threshold, and returns the best matching JIRA issue
    as a dict.

    Returns:
        A dict with keys:
          - 'score' (float, 0–1)
          - 'issue_key'
          - 'description'
          - 'steps_to_reproduce'
          - 'root_cause'
          - 'fix_implemented'
        Or None if no document passes the similarity_threshold.
    """
    print (f"\nQuerying JIRA RAG with query: '{query_text}'")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OpenAI API key not provided. Set api_key argument or OPENAI_API_KEY env var."
        )

    embeddings_model = OpenAIEmbeddings(api_key=api_key, model="text-embedding-3-small")

    # Load the Chroma database from the persistent directory
    try:
        jira_vector_db = Chroma(
            persist_directory=str(persist_dir), embedding_function=embeddings_model
        )
    except Exception as e:
        print(f"Error loading Chroma database from {persist_dir}: {e}")
        return None

    # 1. Retrieve an initial set of documents from the vector store
    retriever = jira_vector_db.as_retriever(search_kwargs={"k": k})
    initial_retrieved_docs = retriever.invoke(query_text)
    print(f"Initially retrieved {len(initial_retrieved_docs)} documents.")

    if not initial_retrieved_docs:
        return None

    # 2. Apply reranking to these documents
    reranked_docs_with_scores = rerank_documents(
        query_text, initial_retrieved_docs, reranker_model_name
    )
    print(f"Reranked {len(reranked_docs_with_scores)} documents.")

    # 3. De-duplicate based on metadata/content
    unique_reranked_docs = dedupe_reranked_documents(reranked_docs_with_scores)
    print(f"Deduped to {len(unique_reranked_docs)} unique documents.")

    if not unique_reranked_docs:
        return None

    # 4. Filter the reranked documents based on a similarity threshold
    filtered_docs_with_scores = [
        (doc, score)
        for doc, score in unique_reranked_docs
        if score >= similarity_threshold
    ]
    print(
        f"Filtered down to {len(filtered_docs_with_scores)} documents "
        f"above threshold {similarity_threshold}."
        f"for query: '{query_text}'"
    )

    if filtered_docs_with_scores:
        for i, (doc, score) in enumerate(filtered_docs_with_scores, start=1):
            print(f"\n--- Retrieved Document {i} (Score: {score:.4f}) ---")
            content = doc.page_content.replace("\n\n", "\n")
            print(f"{content}")

            if doc.metadata:
                print(f"Metadata: {doc.metadata}")
    else:
        print("No relevant documents found after reranking and filtering.")


    if not filtered_docs_with_scores:
        return None

    # 5. Take the top-1 best match
    best_doc, best_score = filtered_docs_with_scores[0]

    result = _parse_jira_issue_from_content(
        best_doc.page_content,
        metadata=best_doc.metadata,
    )

    # result: Dict[str, Any] = {
    #     "score": best_score,
    #     **parsed_fields,
    # }
    
    if result:
        print("\n\n**********************")
        print("Best matching issue:")
        print("**********************")
        print (json.dumps(result, indent=4, ensure_ascii=False))
        # for k, v in result.items():
        #     print(f"{k}: {v}")
    else:
        print("No relevant JIRA issue found above threshold.")
    
    return json.dumps(result, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    # --- Example Usage ---
    print("\n--- Querying the JIRA RAG system for best-matching issue ---")

    # sample_query = "What are the steps to reproduce the CLI fatal error issue?"
    sample_query = "Daily summaries mutable default argument bug inflated counts include previous entries python dataclass list default default_factory bug similar issue"

    current_dir = Path(__file__).parent
    chroma_persist_dir = current_dir.parent / "db" / "chroma" / "jira"

    best_issue = query_jira_rag(
        query_text=sample_query,
        persist_dir=str(chroma_persist_dir),
        k=10,
        similarity_threshold=0.5,
        reranker_model_name="cross-encoder/ms-marco-MiniLM-L-12-v2",
    )

    if best_issue:
        print("\n\n**********************")
        print("Best matching issue:")
        print("**********************")
        # for k, v in best_issue.items():
        #     print(f"{k}: {v}")
        print (best_issue)
    else:
        print("No relevant JIRA issue found above threshold.")
