"""
main.py
-------
Entry point to run any Text-to-SQL approach.

Usage:
    uv run main.py --approach basic --query "Who are the 5 highest paid employees?"

Available approaches:
    basic             → src/01_basic.py
    few_shot          → src/02_few_shot.py
    cot               → src/03_chain_of_thought.py
    rag               → src/04_rag.py
    self_improvement  → src/05_self_improvement.py
"""

import argparse
import importlib

from db.setup import create_database

# Maps CLI name → module filename (without .py)
APPROACHES = {
    "basic":            "01_basic",
    "few_shot":         "02_few_shot",
    "cot":              "03_chain_of_thought",
    "rag":              "04_rag",
    "self_improvement": "05_self_improvement",
}


def main():
    parser = argparse.ArgumentParser(description="Text to SQL — run any approach")
    parser.add_argument(
        "--approach",
        choices=APPROACHES.keys(),
        default="basic",
        help="Which approach to use"
    )
    parser.add_argument(
        "--query",
        type=str,
        default="What are the names of all employees in the Engineering department?",
        help="Natural language query to convert to SQL"
    )
    args = parser.parse_args()

    # Ensure DB exists before running anything
    create_database()

    # Dynamically load the approach module by filename
    module_name = APPROACHES[args.approach]
    module = importlib.import_module(f"src.{module_name}")

    print(f"\n Approach : {args.approach}")
    print(f" Query    : {args.query}\n")

    module.run(args.query)


if __name__ == "__main__":
    main()