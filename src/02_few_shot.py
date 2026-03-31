"""
src/02_few_shot.py
------------------
APPROACH 2: Few-Shot Text-to-SQL

Improvement over basic:
  - We provide Claude with example question → SQL pairs
  - Claude learns the preferred SQL style from these examples
  - Handles JOINs and aggregations more consistently

What changes vs 01_basic.py:
  - build_prompt() now includes an <examples> section
  - Everything else (generate_sql, run_sql, run) is identical
"""

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, MODEL
from db.setup import get_schema_info, run_sql

client = Anthropic(api_key=ANTHROPIC_API_KEY)


# ── 1. Examples ───────────────────────────────────────────────────────────────

# These are handcrafted examples that teach Claude:
#   - Always use table aliases (e for employees, d for departments)
#   - Always JOIN employees and departments when dept info is needed
#   - Always include relevant columns (name, salary, age etc.) in SELECT
#
# The better your examples, the better Claude's output.
# These act as a style guide for Claude.

EXAMPLES = """
<example>
    <question>List all employees in the HR department.</question>
    <sql>
        SELECT e.name
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        WHERE d.name = 'HR';
    </sql>
</example>

<example>
    <question>What is the average salary of employees in the Engineering department?</question>
    <sql>
        SELECT AVG(e.salary) AS avg_salary
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        WHERE d.name = 'Engineering';
    </sql>
</example>

<example>
    <question>Who is the oldest employee and what department are they in?</question>
    <sql>
        SELECT e.name, e.age, d.name AS department
        FROM employees e
        JOIN departments d ON e.department_id = d.id
        ORDER BY e.age DESC
        LIMIT 1;
    </sql>
</example>

<example>
    <question>How many employees are in each department?</question>
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
    Builds the few-shot prompt.

    Compared to basic, this adds an <examples> block between the schema
    and the actual question. Claude reads these examples first and uses
    them to understand the expected SQL style before answering.
    """
    return f"""
You are an AI assistant that converts natural language questions into SQL queries.

Given the following database schema:
<schema>
{schema}
</schema>

Here are some examples of questions and their correct SQL queries:
<examples>
{EXAMPLES}
</examples>

Now convert this question into a SQL query, following the same style as the examples above:
<query>
{query}
</query>

Rules:
- Provide ONLY the SQL query in your response
- Wrap it inside <sql> tags like this: <sql>SELECT ...</sql>
- Use table aliases (e for employees, d for departments)
- Always include meaningful column aliases for aggregations
- Do not include any explanation or markdown
"""


# ── 3. Claude API Call ────────────────────────────────────────────────────────

def generate_sql(prompt: str) -> str:
    """
    Sends the prompt to Claude and extracts SQL from <sql> tags.
    Identical to 01_basic.py — only the prompt changes.
    """
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    sql = raw.split("<sql>")[1].split("</sql>")[0].strip()
    return sql


# ── 4. Main Run Function ──────────────────────────────────────────────────────

def run(query: str):
    """
    End-to-end pipeline for the few-shot approach.
    Called by main.py when --approach few_shot is used.
    """
    schema = get_schema_info()
    prompt = build_prompt(schema, query)

    print("Sending to Claude...")
    sql = generate_sql(prompt)

    print(f"\n Generated SQL:\n{sql}")

    print("\n Query Results:")
    result = run_sql(sql)
    print(result.to_string(index=False))


# ── Run directly for quick testing ───────────────────────────────────────────

if __name__ == "__main__":
    test_queries = [
        "Who are the 5 highest paid employees and what department are they in?",
        "What is the total salary expenditure for each department?",
        "Which department has the youngest average age?",
    ]

    for q in test_queries:
        print(f"\n{'='*60}")
        print(f" Query: {q}")
        print('='*60)
        run(q)