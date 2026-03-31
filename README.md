# 🧠 Text-to-SQL with Claude

> Convert natural language questions into SQL queries using Claude AI — built with progressive prompting techniques from basic to self-improving.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)
![Anthropic](https://img.shields.io/badge/Claude-Sonnet_4.5-D97757?style=flat)
![VoyageAI](https://img.shields.io/badge/VoyageAI-Embeddings-6C63FF?style=flat)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

---

## Overview

**Text-to-SQL** is a project that demonstrates how to build a natural language database interface using Claude AI. Instead of writing SQL manually, you ask questions in plain English and the system generates and executes the SQL for you.

This project is structured as a **learning progression** — five approaches, each building on the last, from a simple one-shot prompt to a fully self-correcting pipeline.

```bash
uv run main.py --approach self_improvement --query "Which departments have the highest salary ratio?"
```

```
 Attempt 1 of 3
 Claude's Reasoning:
   1. I need MAX and MIN salary per department...
   2. I'll use HAVING to filter ratios above 3...

 Generated SQL:
   SELECT d.name, MAX(e.salary) / MIN(e.salary) AS salary_ratio
   FROM employees e
   JOIN departments d ON e.department_id = d.id
   GROUP BY d.name
   HAVING MAX(e.salary) / MIN(e.salary) > 3;

✅ Success on attempt 1!

 department        salary_ratio
 Engineering       3.11
 Finance           4.47
 HR                4.54
 ...
```

---

## Features

- **5 prompting approaches** — from basic to self-improving, all runnable from a single CLI
- **Pluggable architecture** — every approach is self-contained and independently runnable
- **RAG-powered schema retrieval** — only relevant schema columns are sent to Claude, scales to large databases
- **Self-correcting pipeline** — Claude sees its own errors and fixes them automatically
- **Chain-of-thought reasoning** — Claude explains its thinking before writing SQL
- **Persistent vector index** — embeddings are built once and reused across runs

---

## The 5 Approaches

| # | Approach | Key Technique | Best For |
|---|---|---|---|
| 01 | **Basic** | Schema + question → SQL | Simple queries, quick prototyping |
| 02 | **Few-Shot** | Add examples to guide style | Consistent output formatting |
| 03 | **Chain of Thought** | Step-by-step reasoning | Complex multi-table queries |
| 04 | **RAG** | Semantic schema retrieval | Large databases with many tables |
| 05 | **Self Improvement** | Automatic retry on failure | Production reliability |

Each approach builds on the previous one — RAG uses CoT, Self Improvement uses RAG.

---

## Project Structure

```
text-to-sql/
├── .env                         ← API keys (not committed)
├── config.py                    ← Central environment config
├── main.py                      ← Single CLI entry point
├── pyproject.toml               ← Project dependencies (uv)
│
├── db/
│   └── setup.py                 ← Database creation + shared utilities
│                                   (get_schema_info, run_sql)
│
├── src/
│   ├── 01_basic.py              ← Approach 1: Basic prompt
│   ├── 02_few_shot.py           ← Approach 2: Few-shot examples
│   ├── 03_chain_of_thought.py   ← Approach 3: CoT reasoning
│   ├── 04_rag.py                ← Approach 4: RAG retrieval
│   └── 05_self_improvement.py  ← Approach 5: Self-correcting loop
│
└── data/
    ├── data.db                  ← SQLite database (auto-created)
    └── vector_db.pkl            ← VoyageAI vector index (auto-created)
```

---

## Quickstart

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Anthropic API key — [console.anthropic.com](https://console.anthropic.com)
- VoyageAI API key — [dash.voyageai.com](https://dash.voyageai.com) (free tier available)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/text-to-sql.git
cd text-to-sql

# Install dependencies
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys
```

### Environment Variables

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
VOYAGE_API_KEY=pa-xxxxxxxx
```

### Set up the database

```bash
uv run db/setup.py
```

This creates `data/data.db` with:
- **10 departments** across US cities
- **200 employees** with names, ages, salaries, and hire dates

---

## Usage

### Run any approach via CLI

```bash
uv run main.py --approach <approach> --query "<your question>"
```

### Examples

```bash
# Basic
uv run main.py --approach basic \
  --query "Who are the 5 highest paid employees?"

# Few-Shot
uv run main.py --approach few_shot \
  --query "What is the total salary expenditure per department?"

# Chain of Thought
uv run main.py --approach cot \
  --query "Which departments have an average salary above 120000?"

# RAG
uv run main.py --approach rag \
  --query "Which city location has the highest average employee salary?"

# Self Improvement
uv run main.py --approach self_improvement \
  --query "Show salary ratio per department where ratio exceeds 3"
```

### Run an approach directly

Each file is independently runnable with its own test queries:

```bash
uv run src/03_chain_of_thought.py
uv run src/04_rag.py
```

---

## How It Works

### Database Layer (`db/setup.py`)

The shared foundation. Two utilities used by every approach:

- `get_schema_info()` — reads and formats the database schema for Claude
- `run_sql()` — executes generated SQL and returns a pandas DataFrame

### Approach 1 — Basic

The simplest possible pipeline. Give Claude the full schema and the question, ask it to return SQL wrapped in `<sql>` tags.

```
Schema + Question → Claude → <sql>...</sql> → Run → Results
```

### Approach 2 — Few-Shot

Add handcrafted examples of question → SQL pairs to the prompt. Claude learns preferred SQL style — table aliases, JOIN patterns, aggregation formatting.

### Approach 3 — Chain of Thought

Ask Claude to reason step by step inside `<thought_process>` tags before writing SQL. Forces deliberate reasoning, significantly improves accuracy on complex queries.

### Approach 4 — RAG

Uses VoyageAI embeddings to find which schema columns are semantically relevant to the question. Only those columns are sent to Claude — keeping prompts small and focused regardless of database size.

```
Question → VoyageAI embedding → similarity search → top columns → Claude
```

The vector index is built once and saved to `data/vector_db.pkl` for reuse.

### Approach 5 — Self Improvement

Wraps a retry loop around RAG + CoT. If the SQL fails, the error is sent back to Claude with the original question and failed SQL. Claude debugs and corrects itself, up to `MAX_ATTEMPTS` times.

```
Generate SQL → Run → ✅ Done
                  → ❌ Send error back to Claude → Generate fixed SQL → Run → ...
```

---

## Tech Stack

| Tool | Purpose |
|---|---|
| [Claude (claude-sonnet-4-5)](https://anthropic.com) | SQL generation and reasoning |
| [VoyageAI](https://voyageai.com) | Text embeddings for RAG |
| [SQLite](https://sqlite.org) | Lightweight local database |
| [pandas](https://pandas.pydata.org) | Query result formatting |
| [NumPy](https://numpy.org) | Vector similarity computation |
| [uv](https://docs.astral.sh/uv/) | Python package management |

---

## Acknowledgements

This project is based on the [Text to SQL with Claude](https://platform.claude.com/cookbook/capabilities-text-to-sql-guide) cookbook by [Mahesh Murag](https://github.com/maheshmurag) at Anthropic.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
