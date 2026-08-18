# DataPilot AI — CSV / Data Q&A Agent

> **Challenge submission:** Advanced CSV / Data Q&A Agent  
> **One-line job:** *My agent takes a CSV/Excel spreadsheet and a plain-English question, then computes and explains the answer using real pandas operations and shows the evidence behind it.*

## Why this project is strong for the challenge

This is not a chatbot that guesses from a CSV description.

The agent uses a **compute-first architecture**:

**User question → LLM creates pandas plan → AST validation → Python executes on real dataframe → evidence table → LLM writes grounded answer**

That directly addresses the challenge requirement that answers must come from real computation rather than model guesses.

### Key deliverables

- CSV + Excel support
- Automatic schema/data profiling
- Natural-language questions
- LLM-generated pandas computation
- Conservative AST validation before execution
- Actual execution over the uploaded dataframe
- Evidence table shown for every answer
- Automatic chart when the evidence supports one
- Exact generated code shown for reproducibility
- 10 reproducible demo questions
- Streamlit frontend
- Free Google AI Studio API option
- Clear tradeoffs and limitations

## 1. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python | Fast to build and easy to inspect |
| Frontend | Streamlit | Strong demo UI with minimal code |
| LLM | Gemini 3.1 Flash-Lite | Fast, cost-efficient, available with a free tier |
| Data | pandas | Deterministic computation |
| Numeric ops | NumPy | Useful for generated calculations |
| Charts | Plotly | Interactive evidence visualization |
| Storage | None | Dataset is uploaded per session |

Google currently lists Gemini 3.1 Flash-Lite with a free tier on the Gemini API pricing page. Check current quotas before the demo because limits can change.

## 2. Project structure

```text
csv-data-qa-agent/
├── app.py
├── agent.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── sample_questions.md
├── data/
│   └── sample_sales.csv
└── tests/
    └── test_agent.py
```

## 3. Free API setup

### Google AI Studio

Create an API key in Google AI Studio and place it in `.env`.

Copy:

```text
.env.example
```

to:

```text
.env
```

Then:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.1-flash-lite
```

Do **not** commit `.env`.

## 4. Windows installation

Open Command Prompt or PowerShell:

```powershell
git clone YOUR_GITHUB_REPOSITORY_URL
cd csv-data-qa-agent

py -m venv .venv
.venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env` from `.env.example` and add your key.

## 5. Run

```powershell
streamlit run app.py
```

Open the local URL shown by Streamlit.

Click **Use included sample dataset**, then ask:

```text
Which region grew fastest in the last quarter?
```

You should see:

1. Natural-language answer
2. Evidence table
3. Visualization when appropriate
4. Exact pandas code
5. Computation note

## 6. How numbers are computed — anti-hallucination design

The model is **not allowed to directly provide the final numeric answer** during the planning step.

Instead, it returns a small pandas program such as:

```python
latest = df["Quarter"].max()
previous = sorted(df["Quarter"].unique())[-2]

latest_sales = (
    df[df["Quarter"] == latest]
    .groupby("Region", as_index=False)["Sales"]
    .sum()
    .rename(columns={"Sales": "LatestSales"})
)

previous_sales = (
    df[df["Quarter"] == previous]
    .groupby("Region", as_index=False)["Sales"]
    .sum()
    .rename(columns={"Sales": "PreviousSales"})
)

evidence = latest_sales.merge(previous_sales, on="Region")
evidence["GrowthPct"] = (
    (evidence["LatestSales"] - evidence["PreviousSales"])
    / evidence["PreviousSales"] * 100
)

result = evidence.sort_values("GrowthPct", ascending=False).head(1)
```

The program is validated and then executed locally against the actual dataframe.

Only after execution does the second LLM step receive the computed result and evidence table. Therefore the final response is grounded in values produced by Python.

## 7. Security / execution guardrail

Generated Python is dangerous if arbitrary code is allowed.

This project therefore uses an AST allow-list before execution.

Blocked examples include:

- imports
- filesystem access
- network access
- subprocess/OS calls
- `eval`
- `exec`
- environment access
- private/dunder attributes
- arbitrary unknown variables

The execution namespace exposes only:

```text
df
pd
np
result
evidence
note
```

### Honest limitation

This is a **challenge-demo guardrail, not a production-grade remote sandbox**. For untrusted multi-user production use, execute generated code inside an isolated container or dedicated sandbox with CPU, memory, time, filesystem, and network restrictions.

## 8. Sample dataset

`data/sample_sales.csv` contains quarterly sales data for North, South, East and West across 2025-Q1 through 2026-Q1.

Columns:

- Region
- Quarter
- Sales
- Orders
- Customers
- Profit
- Year

The dataset is intentionally small so reviewers can manually verify answers.

## 9. Sample questions

See `sample_questions.md` for 10 questions and expected answers.

Recommended live demo:

### Demo 1 — aggregation

```text
What was total sales in the latest quarter?
```

### Demo 2 — comparison + growth

```text
Which region grew fastest in the last quarter?
```

### Demo 3 — derived metric

```text
What is the average order value by region in 2026-Q1?
```

### Demo 4 — filtering + aggregation

```text
Which region had the highest profit in 2025?
```

### Demo 5 — ranking

```text
Which region had the most customers in 2026-Q1?
```

## 10. Architecture

```text
                ┌─────────────────┐
                │ Streamlit UI    │
                └────────┬────────┘
                         │
                 user question
                         │
                         ▼
                ┌─────────────────┐
                │ Gemini Planner  │
                │ question → code │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ AST Guardrail   │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ pandas / NumPy  │
                │ real execution  │
                └────────┬────────┘
                         │
                 result + evidence
                         │
                         ▼
                ┌─────────────────┐
                │ Gemini Grounder │
                │ result → answer │
                └────────┬────────┘
                         │
                         ▼
          Answer + Table + Chart + Code
```

## 11. Why not just use an LLM to answer?

Because that would fail the core requirement.

An LLM can confidently produce a plausible but incorrect number. Here, the LLM's job is primarily **translation**:

> natural language → executable analysis

Python/pandas is responsible for the arithmetic, aggregation, sorting and filtering.

This creates a clear separation:

- **LLM:** semantic understanding and code planning
- **Python:** numerical truth
- **Evidence table:** audit trail
- **LLM:** language presentation of already-computed results

## 12. Tradeoffs

### Chosen approach

**LLM-generated pandas + local execution**

Advantages:

- handles many question types without hard-coding intents
- easy to understand
- easy to demonstrate
- results are reproducible
- evidence is directly inspectable

Disadvantages:

- generated code can still fail
- AST validation is not a complete security sandbox
- very large datasets need a database/query engine
- ambiguous business language may require clarification
- LLM API availability/rate limits affect the demo

### What I would improve with more time

1. Add a proper Docker/Firecracker sandbox for generated code.
2. Add a SQL path using DuckDB for large CSV/Excel files.
3. Add automatic chart selection based on semantic result type.
4. Add a clarification step for ambiguous questions.
5. Add regression tests containing 50–100 natural-language questions.
6. Add dataset-level profiling and type normalization.
7. Add conversation memory for follow-up questions.
8. Add export of the evidence table and generated analysis.
9. Add confidence/error diagnostics when a generated computation fails.

## 13. Testing

Run:

```powershell
pytest
```

The tests verify:

- dangerous generated code is blocked
- ordinary pandas analysis executes
- CSV loading works
- evidence is returned as a dataframe

## 14. Submission checklist

Before submitting:

- [ ] Public GitHub repository
- [ ] All project files committed
- [ ] No API key committed
- [ ] README tested from a clean environment
- [ ] Sample CSV included
- [ ] 8–10 questions documented
- [ ] Sample outputs checked
- [ ] Demo video/screenshots prepared
- [ ] Streamlit app runs end-to-end
- [ ] Tradeoffs documented
- [ ] Explain the compute-first architecture during review

## 15. 60-second reviewer explanation

> "I built DataPilot AI, a CSV and Excel question-answering agent. The important design decision is that the LLM never gets to invent the final numbers. It first translates the user's question into a constrained pandas computation. I validate that generated program with an AST allow-list, execute it against the real dataframe, and expose the resulting evidence table. A second LLM call only turns those computed values into a natural-language response. The UI shows the answer, evidence, chart, and exact computation, so a reviewer can audit where every number came from."

## License

MIT
