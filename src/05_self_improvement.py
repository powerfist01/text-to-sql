"""
src/05_self_improvement.py
--------------------------
APPROACH 5: Self-Improving Text-to-SQL

Improvement over RAG:
  - Claude generates SQL, tries to run it, and if it fails,
    sends the error back to Claude to fix and retry
  - Loops up to max_attempts times before giving up
  - Each retry includes full history: question + previous SQL + error

How it works:
  1. Attempt 1 — generate SQL fresh using RAG + CoT
  2. Try running it against the database
  3. If it works → done
  4. If it fails → send Claude the error and ask it to fix it
  5. Repeat from step 2 up to max_attempts times

What changes vs 04_rag.py:
  - New execute_with_feedback() function that catches SQL errors
  - New retry_prompt() function that builds the correction prompt
  - run() is now a loop instead of a single shot
"""

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, MODEL
from db.setup import run_sql
import importlib
_rag = importlib.import_module("src.04_rag")
VectorDB = _rag.VectorDB
build_prompt = _rag.build_prompt
vectordb = _rag.vectordb

client = Anthropic(api_key=ANTHROPIC_API_KEY)

MAX_ATTEMPTS = 3


# ── 1. Execute with Feedback ──────────────────────────────────────────────────

def execute_with_feedback(sql: str) -> tuple[bool, any, str]:
    """
    Tries to run the SQL and returns structured feedback.

    Returns a tuple of three values:
      - success (bool)   → did it run without errors?
      - result           → pandas DataFrame if success, None if failed
      - message (str)    → "Query executed successfully" or the error message

    The error message is exactly what gets sent back to Claude on retry.
    """
    try:
        result = run_sql(sql)
        return True, result, "Query executed successfully."
    except Exception as e:
        return False, None, str(e)


# ── 2. Retry Prompt ───────────────────────────────────────────────────────────

def retry_prompt(original_query: str, failed_sql: str, error: str) -> str:
    """
    Builds the correction prompt sent to Claude after a failed attempt.

    We give Claude three things:
      - The original question (so it doesn't lose context)
      - The SQL it wrote that failed
      - The exact error message from SQLite

    This is very different from attempt 1 — Claude isn't starting
    fresh, it's doing targeted debugging with full context of what
    went wrong.
    """
    return f"""
The SQL query you generated failed to execute. Please analyze the error and fix it.

Original question:
<query>
{original_query}
</query>

Your previous SQL that failed:
<failed_sql>
{failed_sql}
</failed_sql>

Error message:
<error>
{error}
</error>

Common issues to check:
- Use strftime('%Y', column) for year extraction in SQLite, not YEAR()
- Use correct column names exactly as they appear in the schema
- Make sure JOINs reference the correct foreign keys

Provide your corrected SQL inside <sql> tags.
Also explain what you fixed inside <thought_process> tags.
"""


# ── 3. Generate SQL (single attempt) ─────────────────────────────────────────

def generate_sql(prompt: str) -> tuple[str, str]:
    """Sends prompt to Claude and returns (thought_process, sql)."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    thought = raw.split("<thought_process>")[1].split("</thought_process>")[0].strip()
    sql = raw.split("<sql>")[1].split("</sql>")[0].strip()
    return thought, sql


# ── 4. Main Run Function ──────────────────────────────────────────────────────

def run(query: str):
    """
    End-to-end self-improving pipeline.
    Called by main.py when --approach self_improvement is used.

    Loop structure:
      Attempt 1 → fresh RAG + CoT prompt
      Attempt 2 → retry prompt with error from attempt 1
      Attempt 3 → retry prompt with error from attempt 2
      Give up if all attempts fail
    """
    # Build vector index if not already built
    vectordb.build_index()

    # Retrieve relevant schema columns using RAG
    results = vectordb.search(query, k=10, threshold=0.3)
    retrieved_schema = "\n".join(
        f"Table: {r['metadata']['table']}, "
        f"Column: {r['metadata']['column']}, "
        f"Type: {r['metadata']['type']}"
        for r in results
    )

    print(f"\n Retrieved {len(results)} relevant schema columns.")

    # Track the last SQL and error for retry context
    last_sql = None
    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n{'─'*60}")
        print(f" Attempt {attempt} of {MAX_ATTEMPTS}")
        print(f"{'─'*60}")

        # Attempt 1: fresh prompt using RAG + CoT
        # Attempt 2+: retry prompt with previous SQL and error
        if attempt == 1:
            prompt = build_prompt(retrieved_schema, query)
        else:
            print(f" Previous error: {last_error}")
            prompt = retry_prompt(query, last_sql, last_error)

        # Ask Claude to generate (or fix) the SQL
        thought, sql = generate_sql(prompt)
        last_sql = sql

        print(f"\n Claude's Reasoning:\n{thought}")
        print(f"\n Generated SQL:\n{sql}")

        # Try running the SQL
        success, result, feedback = execute_with_feedback(sql)

        if success:
            print(f"\n✅ Success on attempt {attempt}!")
            print("\n Query Results:")
            print(result.to_string(index=False))
            return
        else:
            last_error = feedback
            print(f"\n❌ Failed: {feedback}")

    # All attempts exhausted
    print(f"\n🚫 Could not generate valid SQL after {MAX_ATTEMPTS} attempts.")
    print(f" Last SQL tried:\n{last_sql}")
    print(f" Last error:\n{last_error}")


# ── Run directly for quick testing ───────────────────────────────────────────

if __name__ == "__main__":
    # These are intentionally tricky queries to stress test self-improvement
    test_queries = [
        "For each department, show the ratio of highest to lowest salary, only where ratio is greater than 3",
        "How many employees were hired each year, ordered by year?",
        "Which department has the highest average salary for employees over 40?",
    ]

    for q in test_queries:
        print(f"\n{'='*60}")
        print(f" Query: {q}")
        print('='*60)
        run(q)