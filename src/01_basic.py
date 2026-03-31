"""
src/01_basic.py
---------------
APPROACH 1: Basic Text-to-SQL

The simplest approach:
  1. Fetch the DB schema
  2. Build a prompt with the schema + user's question
  3. Send to Claude
  4. Extract SQL from <sql> tags in the response
  5. Run the SQL and display results

No examples, no reasoning — just schema + question → SQL.
"""

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, MODEL
from db.setup import get_schema_info, run_sql

client = Anthropic(api_key=ANTHROPIC_API_KEY)


# ── 1. Prompt Builder ─────────────────────────────────────────────────────────

def build_prompt(schema: str, query: str) -> str:
    """
    Builds the prompt we send to Claude.

    We give Claude:
      - A clear role: "you convert natural language to SQL"
      - The database schema inside <schema> tags
      - The user's question inside <query> tags
      - An instruction to respond ONLY with SQL inside <sql> tags

    Why XML-style tags?
      They give Claude clear boundaries for each piece of information,
      and make it easy for us to parse the response reliably.
    """
    return f"""
You are an AI assistant that converts natural language questions into SQL queries.

Given the following database schema:
<schema>
{schema}
</schema>

Convert this question into a SQL query:
<query>
{query}
</query>

Rules:
- Provide ONLY the SQL query in your response
- Wrap it inside <sql> tags like this: <sql>SELECT ...</sql>
- Do not include any explanation or markdown
"""


# ── 2. Claude API Call ────────────────────────────────────────────────────────

def generate_sql(prompt: str) -> str:
    """
    Sends the prompt to Claude and extracts the SQL from the response.

    temperature=0 means deterministic output — we want consistent,
    precise SQL rather than creative variation.
    """
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Extract SQL from between <sql> and </sql> tags
    sql = raw.split("<sql>")[1].split("</sql>")[0].strip()
    return sql


# ── 3. Main Run Function ──────────────────────────────────────────────────────

def run(query: str):
    """
    End-to-end pipeline for the basic approach.
    Called by main.py when --approach basic is used.
    """
    # Step 1: Get schema from the database
    schema = get_schema_info()

    # Step 2: Build the prompt
    prompt = build_prompt(schema, query)

    # Step 3: Ask Claude to generate SQL
    print("Sending to Claude...")
    sql = generate_sql(prompt)

    # Step 4: Show the generated SQL
    print(f"\n Generated SQL:\n{sql}")

    # Step 5: Run it against the database
    print("\n Query Results:")
    result = run_sql(sql)
    print(result.to_string(index=False))


# ── Run directly for quick testing ───────────────────────────────────────────

if __name__ == "__main__":
    test_queries = [
        "What are the names of all employees in the Engineering department?",
        "Who are the 5 highest paid employees?",
        "What is the average salary across all departments?",
    ]

    for q in test_queries:
        print(f"\n{'='*60}")
        print(f" Query: {q}")
        print('='*60)
        run(q)