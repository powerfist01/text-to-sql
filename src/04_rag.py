"""
src/04_rag.py
-------------
APPROACH 4: RAG (Retrieval Augmented Generation) Text-to-SQL

Improvement over chain-of-thought:
  - Instead of passing the entire schema, we only retrieve the
    schema columns that are relevant to the user's question
  - Uses VoyageAI embeddings to measure semantic similarity between
    the question and each column in the schema
  - Scales well to large databases with hundreds of tables

How it works:
  1. Each column in the schema is converted to an embedding (a vector
     of numbers representing its meaning) using VoyageAI
  2. The user's question is also converted to an embedding
  3. We find the columns whose embeddings are closest to the question
  4. Only those columns are passed to Claude in the prompt

What changes vs 03_chain_of_thought.py:
  - New VectorDB class using VoyageAI to store and search column embeddings
  - build_prompt() now uses retrieved schema instead of full schema
  - First run builds the vector index; subsequent runs reuse it from disk
"""

import json
import os
import pickle
import sqlite3

import numpy as np
import voyageai
from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, VOYAGE_API_KEY, MODEL
from db.setup import DATABASE_PATH, run_sql

client = Anthropic(api_key=ANTHROPIC_API_KEY)
voyage = voyageai.Client(api_key=VOYAGE_API_KEY)

# Path where we persist the vector index between runs
VECTOR_DB_PATH = "data/vector_db.pkl"


# ── 1. VectorDB ───────────────────────────────────────────────────────────────

class VectorDB:
    """
    A simple vector database backed by a pickle file on disk.

    Stores VoyageAI embeddings for each column in the schema so we
    can quickly find which columns are most relevant to a question.

    Structure:
        embeddings  → list of vectors, one per schema column
        metadata    → list of dicts with table/column/type info
        query_cache → dict of query → embedding (avoids re-embedding same query)
    """

    def __init__(self, db_path: str = VECTOR_DB_PATH):
        self.db_path = db_path
        self.embeddings = []
        self.metadata = []
        self.query_cache = {}
        self._load()

    def _load(self):
        """Load existing index from disk if it exists."""
        if os.path.exists(self.db_path):
            with open(self.db_path, "rb") as f:
                data = pickle.load(f)
            self.embeddings = data["embeddings"]
            self.metadata = data["metadata"]
            self.query_cache = json.loads(data["query_cache"])
            print(f"Loaded vector index ({len(self.embeddings)} entries).")

    def _save(self):
        """Persist the current index to disk."""
        with open(self.db_path, "wb") as f:
            pickle.dump(
                {
                    "embeddings": self.embeddings,
                    "metadata": self.metadata,
                    "query_cache": json.dumps(self.query_cache),
                },
                f,
            )

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """
        Convert a list of strings into embeddings using VoyageAI.

        We use the 'voyage-2' model which is fast and accurate.
        Batched in groups of 128 to stay within API limits.

        Each embedding is a list of floats (a vector) that represents
        the semantic meaning of the text.
        """
        all_embeddings = []
        for i in range(0, len(texts), 128):
            batch = texts[i : i + 128]
            result = voyage.embed(batch, model="voyage-2")
            all_embeddings.extend(result.embeddings)
        return all_embeddings

    def build_index(self):
        """
        Reads all columns from the database schema and creates an
        embedding for each one. Called once on first run.

        Each entry looks like:
            text:     "Table: employees, Column: salary, Type: REAL"
            metadata: {"table": "employees", "column": "salary", "type": "REAL"}
        """
        if self.embeddings:
            print("Vector index already built. Skipping.")
            return

        print("Building vector index from schema...")

        schema_data = []
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            for (table_name,) in tables:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                for col in columns:
                    schema_data.append({
                        "text": f"Table: {table_name}, Column: {col[1]}, Type: {col[2]}",
                        "metadata": {
                            "table": table_name,
                            "column": col[1],
                            "type": col[2],
                        },
                    })

        texts = [item["text"] for item in schema_data]
        self.embeddings = self._embed(texts)
        self.metadata = [item["metadata"] for item in schema_data]
        self._save()
        print(f"Index built with {len(self.embeddings)} schema entries.")

    def search(self, query: str, k: int = 10, threshold: float = 0.3) -> list[dict]:
        """
        Find the k most relevant schema columns for a given query.

        Uses dot product similarity — since VoyageAI returns normalized
        vectors, dot product == cosine similarity.

        Args:
            query:     The user's natural language question
            k:         Max number of columns to return
            threshold: Minimum similarity score (0 to 1)

        Returns:
            List of dicts with 'metadata' and 'similarity' keys,
            sorted by similarity descending.
        """
        # Embed the query (cache to avoid redundant API calls)
        if query not in self.query_cache:
            self.query_cache[query] = self._embed([query])[0]
            self._save()

        query_vec = self.query_cache[query]

        # Compute similarity between query and all stored embeddings
        similarities = np.dot(self.embeddings, query_vec)

        # Sort highest similarity first
        top_indices = np.argsort(similarities)[::-1]

        return [
            {"metadata": self.metadata[i], "similarity": float(similarities[i])}
            for i in top_indices
            if similarities[i] >= threshold
        ][:k]


# ── 2. Prompt Builder ─────────────────────────────────────────────────────────

# Same CoT examples as approach 3 — the only thing that changes
# is the schema section now contains retrieved columns, not all columns
EXAMPLES = """
<example>
    <question>List all employees in the HR department.</question>
    <thought_process>
        1. I need employee names, so I'll use the employees table.
        2. I need to filter by department name, which is in the departments table.
        3. I'll JOIN on department_id = id and filter WHERE d.name = 'HR'.
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
        1. Salary and hire_date are both in the employees table — no JOIN needed.
        2. Filter by year using strftime('%Y', hire_date) = '2022' for SQLite.
        3. Use AVG(salary) with a meaningful alias.
    </thought_process>
    <sql>
        SELECT AVG(salary) AS avg_salary
        FROM employees
        WHERE strftime('%Y', hire_date) = '2022';
    </sql>
</example>
"""


def build_prompt(retrieved_schema: str, query: str) -> str:
    """
    Builds the RAG prompt using only the retrieved schema columns.

    Key difference from CoT approach:
      - The <schema> block only contains columns relevant to this query
      - Everything else (examples, instructions) stays the same
    """
    return f"""
You are an AI assistant that converts natural language questions into SQL queries.

Here are the most relevant parts of the database schema for this question:
<schema>
{retrieved_schema}
</schema>

Here are some examples of questions and their SQL queries:
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
"""


# ── 3. Claude API Call ────────────────────────────────────────────────────────

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

# Initialize VectorDB once at module level (reused across calls)
vectordb = VectorDB()


def run(query: str):
    """
    End-to-end pipeline for the RAG approach.
    Called by main.py when --approach rag is used.
    """
    # Build index on first run (skipped on subsequent runs)
    vectordb.build_index()

    # Retrieve only the schema columns relevant to this query
    results = vectordb.search(query, k=10, threshold=0.3)

    # Format retrieved columns as a readable schema string
    retrieved_schema = "\n".join(
        f"Table: {r['metadata']['table']}, "
        f"Column: {r['metadata']['column']}, "
        f"Type: {r['metadata']['type']}  "
        f"(similarity: {r['similarity']:.2f})"
        for r in results
    )

    print(f"\n Retrieved schema columns ({len(results)} of total):")
    print(retrieved_schema)

    prompt = build_prompt(retrieved_schema, query)

    print("\nSending to Claude...")
    thought, sql = generate_sql(prompt)

    print(f"\n Claude's Reasoning:\n{thought}")
    print(f"\n Generated SQL:\n{sql}")

    print("\n Query Results:")
    result = run_sql(sql)
    print(result.to_string(index=False))


# ── Run directly for quick testing ───────────────────────────────────────────

if __name__ == "__main__":
    test_queries = [
        "What is the average salary of employees in each department?",
        "Which location has the highest paid employees on average?",
        "How many employees were hired after 2020 in the Engineering department?",
    ]

    for q in test_queries:
        print(f"\n{'='*60}")
        print(f" Query: {q}")
        print('='*60)
        run(q)