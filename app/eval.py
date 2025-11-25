"""Model evaluation script for RAG system."""

import csv
import json
import time
import argparse
from typing import List, Dict, Any
from datetime import datetime

from app.rag_engine import get_rag_engine
from app.db import get_mongo_client
from app.utils import log_event


def load_eval_dataset(csv_path: str) -> List[Dict[str, Any]]:
    """
    Load evaluation dataset from CSV.

    Expected format:
    question,expected_doc_ids
    "What is X?","doc_1|doc_2|doc_3"

    Args:
        csv_path: Path to CSV file

    Returns:
        List of evaluation examples
    """
    examples = []

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                question = row.get("question", "").strip()
                expected_ids = row.get("expected_doc_ids", "").strip()

                if question and expected_ids:
                    examples.append(
                        {
                            "question": question,
                            "expected_doc_ids": set(expected_ids.split("|")),
                        }
                    )

        log_event(
            "eval_dataset_loaded",
            {"csv_path": csv_path, "num_examples": len(examples)},
        )

        return examples

    except Exception as e:
        log_event(
            "eval_dataset_load_failed",
            {"csv_path": csv_path, "error": str(e)},
            level="ERROR",
        )
        raise


def calculate_precision_at_k(
    retrieved_ids: List[str], expected_ids: set, k: int
) -> float:
    """
    Calculate Precision@K metric.

    Args:
        retrieved_ids: List of retrieved document IDs (ordered by relevance)
        expected_ids: Set of expected/relevant document IDs
        k: Number of top results to consider

    Returns:
        Precision@K score (0.0 to 1.0)
    """
    if not retrieved_ids or not expected_ids:
        return 0.0

    # Take top K retrieved documents
    top_k = retrieved_ids[:k]

    # Count how many are relevant
    relevant_count = sum(1 for doc_id in top_k if doc_id in expected_ids)

    # Precision@K = relevant in top K / K
    return relevant_count / k


def evaluate_retrieval(
    rag_engine,
    examples: List[Dict[str, Any]],
    k_values: List[int] = [1, 3, 5],
) -> Dict[str, Any]:
    """
    Evaluate retrieval performance on a dataset.

    Args:
        rag_engine: RAG engine instance
        examples: List of evaluation examples
        k_values: List of K values for Precision@K

    Returns:
        Evaluation metrics
    """
    log_event("evaluation_started", {"num_examples": len(examples)})

    results = []
    latencies = []

    for i, example in enumerate(examples, 1):
        question = example["question"]
        expected_ids = example["expected_doc_ids"]

        try:
            # Measure retrieval latency
            start_time = time.time()

            # Retrieve documents (max K we need)
            max_k = max(k_values)
            retrieved_docs = rag_engine.retrieve(question, top_k=max_k)

            latency_ms = (time.time() - start_time) * 1000
            latencies.append(latency_ms)

            # Extract document IDs
            retrieved_ids = [doc.get("_id", "") for doc in retrieved_docs]

            # Calculate precision at different K values
            precisions = {}
            for k in k_values:
                precision = calculate_precision_at_k(retrieved_ids, expected_ids, k)
                precisions[f"precision_at_{k}"] = precision

            result = {
                "question": question,
                "retrieved_ids": retrieved_ids[:max_k],
                "expected_ids": list(expected_ids),
                "latency_ms": round(latency_ms, 2),
                **precisions,
            }

            results.append(result)

            log_event(
                "evaluation_example_processed",
                {
                    "index": i,
                    "question_length": len(question),
                    "num_retrieved": len(retrieved_ids),
                    "latency_ms": round(latency_ms, 2),
                },
            )

        except Exception as e:
            log_event(
                "evaluation_example_failed",
                {"index": i, "question": question, "error": str(e)},
                level="ERROR",
            )

            # Add failed result
            results.append(
                {
                    "question": question,
                    "error": str(e),
                    **{f"precision_at_{k}": 0.0 for k in k_values},
                }
            )

    # Calculate aggregate metrics
    avg_precision = {}
    for k in k_values:
        key = f"precision_at_{k}"
        valid_scores = [r[key] for r in results if key in r and "error" not in r]
        avg_precision[key] = (
            sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
        )

    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

    metrics = {
        **avg_precision,
        "avg_retrieval_latency_ms": round(avg_latency, 2),
        "total_questions": len(examples),
        "successful_queries": len(latencies),
        "failed_queries": len(examples) - len(latencies),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    log_event("evaluation_completed", metrics)

    return {
        "metrics": metrics,
        "detailed_results": results,
    }


def run_evaluation(dataset_path: str, output_path: str, k_values: List[int] = None):
    """
    Run complete evaluation pipeline.

    Args:
        dataset_path: Path to evaluation CSV
        output_path: Path to save results JSON
        k_values: List of K values for metrics
    """
    k_values = k_values or [1, 3, 5]

    try:
        # Load dataset
        examples = load_eval_dataset(dataset_path)

        if not examples:
            log_event("no_eval_examples", level="WARNING")
            print("No evaluation examples found in dataset")
            return

        # Initialize RAG engine
        rag_engine = get_rag_engine()

        # Run evaluation
        results = evaluate_retrieval(rag_engine, examples, k_values)

        # Save results
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        log_event(
            "evaluation_results_saved",
            {"output_path": output_path},
        )

        # Print summary
        print("\n" + "=" * 60)
        print("EVALUATION RESULTS")
        print("=" * 60)

        metrics = results["metrics"]
        for k in k_values:
            precision = metrics[f"precision_at_{k}"]
            print(f"Precision@{k}: {precision:.4f}")

        print(f"\nAverage Retrieval Latency: {metrics['avg_retrieval_latency_ms']:.2f} ms")
        print(f"Total Questions: {metrics['total_questions']}")
        print(f"Successful Queries: {metrics['successful_queries']}")
        print(f"Failed Queries: {metrics['failed_queries']}")
        print(f"\nDetailed results saved to: {output_path}")
        print("=" * 60)

    except Exception as e:
        log_event(
            "evaluation_failed",
            {"error": str(e)},
            level="ERROR",
        )
        raise


def main():
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Evaluate RAG system performance")

    parser.add_argument(
        "--dataset",
        type=str,
        default="eval_dataset.csv",
        help="Path to evaluation dataset CSV",
    )

    parser.add_argument(
        "--output",
        type=str,
        default="eval_report.json",
        help="Path to save evaluation report JSON",
    )

    parser.add_argument(
        "--k-values",
        type=int,
        nargs="+",
        default=[1, 3, 5],
        help="K values for Precision@K metrics",
    )

    args = parser.parse_args()

    run_evaluation(
        dataset_path=args.dataset,
        output_path=args.output,
        k_values=args.k_values,
    )


if __name__ == "__main__":
    main()
