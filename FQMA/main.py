import argparse
import sys

import config
from query_workflow import QueryWorkflow

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def run_query(question: str):
    print("\n" + "=" * 60)
    print(f"Question: {question}")
    print(f"Dataset: {config.CURRENT_DATASET}")
    print("=" * 60 + "\n")

    workflow = QueryWorkflow()
    result = workflow.run(question, thinking_callback=print)

    if not result.get("success"):
        print(f"\nQuery failed: {result.get('error')}")
        return result

    print("\n=== Subqueries ===")
    print(result.get("subqueries", []))
    print("\n=== Tables ===")
    print(result.get("tables", ""))
    print("\n=== Explanation ===\n")
    print(result.get("explanation", ""))
    return result


def interactive_mode():
    print("\n" + "=" * 60)
    print("FQMA Interactive Query Mode")
    print(f"Dataset: {config.CURRENT_DATASET} | Model: {config.MODEL_TYPE}")
    print("=" * 60)
    print("Enter a natural language question and press Enter to run it.")
    print("Enter exit or press Enter on an empty line to quit.\n")

    while True:
        try:
            question = input("Question> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting interactive mode.")
            break

        if not question or question.lower() in {"exit", "quit", "q"}:
            print("Exiting interactive mode.")
            break

        run_query(question)


def get_default_question() -> str:
    if config.CURRENT_DATASET == "GMQA":
        return "Which microbiota increase after using the drug Metformin?"
    return "Find all authors who published papers at the Benguela conference and return their surnames."


def main():
    parser = argparse.ArgumentParser(
        description="FQMA query system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --interactive
  python main.py --question "Find all authors who published papers at the Benguela conference and return their surnames."
  python main.py
        """.strip(),
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run the interactive CLI mode.",
    )
    parser.add_argument(
        "--question",
        "-q",
        type=str,
        default=None,
        help="Run a single natural-language question and exit.",
    )

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
    elif args.question:
        run_query(args.question)
    else:
        run_query(get_default_question())


if __name__ == "__main__":
    main()
