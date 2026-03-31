"""
src/03_chain_of_thought.py
--------------------------
APPROACH 3: Chain-of-Thought (CoT) Text-to-SQL

Improvement over few-shot:
  - Claude is asked to reason step by step before writing SQL
  - Examples now show both the thought process AND the SQL
  - Better accuracy on complex queries involving multiple conditions,
    aggregations, or multi-table joins

What changes vs 02_few_shot.py:
  - Examples include <thought_process> blocks
  - Prompt asks Claude to produce <thought_process> before <sql>
  - generate_sql() now extracts and returns both thought + SQL
  - run() displays the thought process so you can follow Claude's reasoning
"""

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, MODEL
from db.setup import get_schema_info, run_sql

client = Anthropic(api_key=ANTHROPIC_API_KEY)


# ── 1. Examples ───────────────────────────────────────────────────────────────

# Each example now has three parts:
#   <question>        → the natural language query
#   <thought_process> → step by step reasoning before writing SQL
#   <sql>             → the final query
#
# The thought process teaches Claude HOW to think about the problem,
# not just what the answer looks like.

EXAMPLES = """
<example>
    <question>List all employees in the HR department.</question>
    <thought_process>
        1. I need employee names, so I'll use the employees table.
        2. I need to filter by department name 'HR', which is in the departments table.
        3. I'll JOIN employees and departments on department_id = id.
        4. I'll filter with WHERE d.name = 'HR'.
        5. I only need to SELECT e.name.
    </thought_process>
    <sql>
        SELECT e.name
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        WHERE d.name = 'HR';
    </sql>
</example>

<example>
    <question>What is the average salary of employees hired in 2022?</question>
    <thought_process>
        1. I need salary data from the employees table only — no JOIN needed.
        2. I need to filter for employees hired in 2022.
        3. hire_date is a DATE column, so I'll use strftime('%Y', hire_date) = '2022'
           which works in SQLite (unlike YEAR() which is MySQL syntax).
        4. I'll use AVG(salary) and give it a meaningful alias.
    </thought_process>
    <sql>
        SELECT AVG(salary) AS avg_salary
        FROM employees
        WHERE strftime('%Y', hire_date) = '2022';
    </sql>
</example>

<example>
    <question>How many employees are in each department, ordered by headcount?</question>
    <thought_process>
        1. I need counts per department, so I'll GROUP BY department.
        2. Department names are in the departments table, so I need a JOIN.
        3. I'll COUNT(e.id) for headcount and alias it as employee_count.
        4. I'll ORDER BY employee_count DESC to show largest departments first.
    </thought_process>
    <sql>
        SELECT d.name AS department, COUNT(e.id) AS employee_count
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        GROUP BY d.name
        ORDER BY employee_count DESC;
    </sql>
</example>
"""


# ── 2. Prompt Builder ─────────────────────────────────────────────────────────

def build_prompt(schema: str, query: str) -> str:
    """
    Builds the chain-of-thought prompt.

    Key difference from few-shot:
      - Examples show <thought_process> before <sql>
      - Claude is explicitly instructed to think step by step first
      - This forces deliberate reasoning before committing to a query
    """
    return f"""
You are an AI assistant that converts natural language questions into SQL queries.

Given the following database schema:
<schema>
{schema}
</schema>

Here are some examples showing how to reason through a question before writing SQL:
<examples>
{EXAMPLES}
</examples>

Now convert this question into a SQL query:
<query>
{query}
</query>

Instructions:
- First, think step by step inside <thought_process> tags
- Then, provide the final SQL inside <sql> tags
- Use table aliases (e for employees, d for departments)
- For date filtering use strftime('%Y', column) for SQLite, not YEAR()
- Include meaningful column aliases for aggregations
- Do not include any explanation outside of the thought_process tags
"""


# ── 3. Claude API Call ────────────────────────────────────────────────────────

def generate_sql(prompt: str) -> tuple[str, str]:
    """
    Sends the prompt to Claude and extracts both:
      - thought_process: Claude's reasoning steps
      - sql: the final SQL query

    Returns a tuple of (thought_process, sql)
    """
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,  # slightly higher — thought process needs more tokens
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Extract thought process
    thought = raw.split("<thought_process>")[1].split("</thought_process>")[0].strip()

    # Extract SQL
    sql = raw.split("<sql>")[1].split("</sql>")[0].strip()

    return thought, sql


# ── 4. Main Run Function ──────────────────────────────────────────────────────

def run(query: str):
    """
    End-to-end pipeline for the chain-of-thought approach.
    Called by main.py when --approach cot is used.
    """
    schema = get_schema_info()
    prompt = build_prompt(schema, query)

    print("Sending to Claude...")
    thought, sql = generate_sql(prompt)

    # Show Claude's reasoning — this is the key difference you can observe
    print(f"\n Claude's Reasoning:\n{thought}")
    print(f"\n Generated SQL:\n{sql}")

    print("\n Query Results:")
    result = run_sql(sql)
    print(result.to_string(index=False))


# ── Run directly for quick testing ───────────────────────────────────────────

if __name__ == "__main__":
    # These are intentionally complex queries where CoT shines
    test_queries = [
        "What are the names and hire dates of employees in Engineering, ordered by salary?",
        "Which departments have an average salary above 120000?",
        "How many employees were hired each year, ordered by year?",
    ]

    for q in test_queries:
        print(f"\n{'='*60}")
        print(f" Query: {q}")
        print('='*60)
        run(q)