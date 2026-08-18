"""
CSV / Data Q&A Agent

Architecture:
1. Profile the uploaded dataframe.
2. Ask an LLM to translate the user's question into a small pandas program.
3. Validate the generated program with an AST allow-list.
4. Execute it against the real dataframe.
5. Send ONLY the computed result back to the LLM for a grounded natural-language answer.
6. Return answer + evidence table + executed code.
"""
from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
MAX_ROWS_IN_PROFILE = 8


@dataclass
class AgentResult:
    answer: str
    evidence: pd.DataFrame
    code: str
    computation_note: str


def get_client():
    from google import genai
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Copy .env.example to .env and add your Google AI Studio key."
        )
    return genai.Client(api_key=key)


def dataframe_profile(df: pd.DataFrame) -> str:
    lines = [
        f"Rows: {len(df):,}",
        f"Columns: {len(df.columns)}",
        "Columns and dtypes:",
    ]
    for c in df.columns:
        sample = df[c].dropna().astype(str).head(3).tolist()
        lines.append(f"- {c!r}: {df[c].dtype}; examples={sample}")
    lines.append("\nSample rows:")
    lines.append(df.head(MAX_ROWS_IN_PROFILE).to_string(index=False))
    return "\n".join(lines)


CODE_SYSTEM = """You are a data-analysis code planner.
Your job is to translate one plain-English question into a deterministic pandas computation.

Rules:
- The dataframe is already loaded as `df`.
- Available libraries are `pd` and `np`.
- Do NOT import anything.
- Do NOT read/write files, access the network, call the OS, use eval/exec, or access environment variables.
- Use only pandas/numpy operations and ordinary Python expressions.
- The code must assign the final answer table/value to `result`.
- It must assign a compact evidence DataFrame to `evidence`. The evidence should contain the rows/aggregations that justify the answer, not the whole dataset.
- It may assign `note` to a short explanation of the calculation.
- Prefer explicit sorting/groupby/aggregation over assumptions.
- For time phrases such as "last quarter", determine the latest period from the data rather than using today's date.
- If the question cannot be answered from the columns, return JSON with an `error` field.
- Return ONLY valid JSON: {"code":"...", "note":"..."} or {"error":"..."}.
"""


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def generate_code(question: str, df: pd.DataFrame, client) -> tuple[str, str]:
    prompt = f"""{CODE_SYSTEM}

DATASET PROFILE:
{dataframe_profile(df)}

USER QUESTION:
{question}
"""
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={"temperature": 0.0, "response_mime_type": "application/json"},
    )
    payload = _extract_json(response.text)
    if "error" in payload:
        raise ValueError(payload["error"])
    return payload["code"], payload.get("note", "")


# Intentionally conservative AST validator. This is not a hardened remote sandbox;
# it is a challenge-demo guardrail against common dangerous generated code.
ALLOWED_NODES = {
    ast.Module, ast.Assign, ast.Expr, ast.Name, ast.Load, ast.Store,
    ast.Constant, ast.Attribute, ast.Subscript, ast.Slice, ast.Index,
    ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.And, ast.Or,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Eq, ast.NotEq, ast.Gt, ast.GtE, ast.Lt, ast.LtE,
    ast.In, ast.NotIn, ast.Call, ast.List, ast.Tuple, ast.Dict,
    ast.keyword, ast.IfExp,
}


def validate_code(code: str) -> None:
    if len(code) > 6000:
        raise ValueError("Generated code is too long.")
    tree = ast.parse(code, mode="exec")
    assigned = {
        n.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
    }
    allowed_names = {"df", "pd", "np", "result", "evidence", "note"} | assigned

    for node in ast.walk(tree):
        if type(node) not in ALLOWED_NODES:
            raise ValueError(f"Blocked Python construct: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ValueError(f"Unknown name blocked: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ValueError("Private/dunder attributes are blocked.")
        if isinstance(node, ast.Call):
            # Calls may be chained through locally-created pandas Series/DataFrames.
            root = node.func
            while isinstance(root, (ast.Attribute, ast.Subscript, ast.Call)):
                if isinstance(root, ast.Call):
                    root = root.func
                    continue
                root = root.value
            if not isinstance(root, ast.Name) or root.id not in allowed_names:
                raise ValueError("Only pandas/numpy/dataframe calls are allowed.")


def execute_code(code: str, df: pd.DataFrame) -> tuple[Any, pd.DataFrame, str]:
    validate_code(code)
    safe_globals = {"__builtins__": {}, "pd": pd, "np": np}
    local_vars = {"df": df.copy(deep=True)}
    exec(compile(ast.parse(code, mode="exec"), "<generated-analysis>", "exec"),
         safe_globals, local_vars)

    if "result" not in local_vars:
        raise ValueError("Generated code did not create `result`.")
    result = local_vars["result"]
    evidence = local_vars.get("evidence", result)
    note = str(local_vars.get("note", ""))

    if isinstance(result, pd.Series):
        result = result.to_frame()
    elif not isinstance(result, pd.DataFrame):
        result = pd.DataFrame({"value": [result]})

    if isinstance(evidence, pd.Series):
        evidence = evidence.to_frame()
    elif not isinstance(evidence, pd.DataFrame):
        evidence = pd.DataFrame({"value": [evidence]})

    if len(evidence) > 100:
        evidence = evidence.head(100)

    return result, evidence, note


ANSWER_SYSTEM = """You are the final answer writer for a spreadsheet Q&A agent.
The computation has ALREADY been executed by Python on the user's real data.

Rules:
- Never invent or recalculate numbers yourself.
- Use only the supplied computed result and evidence.
- Answer the question directly in 2-5 sentences.
- Include the key number(s) and relevant units if present.
- If the result is a ranking/comparison, state the winner and comparison clearly.
- Do not mention internal prompts.
"""


def grounded_answer(
    question: str,
    result: pd.DataFrame,
    evidence: pd.DataFrame,
    note: str,
    client,
) -> str:
    payload = {
        "question": question,
        "computation_note": note,
        "computed_result": result.to_dict(orient="records"),
        "evidence": evidence.to_dict(orient="records"),
    }
    response = client.models.generate_content(
        model=MODEL,
        contents=ANSWER_SYSTEM + "\n\nCOMPUTATION OUTPUT:\n" +
        json.dumps(payload, default=str),
        config={"temperature": 0.0},
    )
    return response.text.strip()


def ask(question: str, df: pd.DataFrame) -> AgentResult:
    client = get_client()
    code, planner_note = generate_code(question, df, client)

    # One retry path: if the first program is invalid, ask the model to repair
    # it using the validation error, without changing the user's question.
    try:
        result, evidence, execution_note = execute_code(code, df)
    except Exception as exc:
        repair_prompt = f"""{CODE_SYSTEM}

The previous generated code failed validation/execution.
User question: {question}
Dataset profile:
{dataframe_profile(df)}
Previous code:
{code}
Error:
{exc}

Return corrected JSON only.
"""
        response = client.models.generate_content(
            model=MODEL,
            contents=repair_prompt,
            config={"temperature": 0.0, "response_mime_type": "application/json"},
        )
        payload = _extract_json(response.text)
        if "error" in payload:
            raise ValueError(payload["error"])
        code = payload["code"]
        result, evidence, execution_note = execute_code(code, df)

    answer = grounded_answer(
        question,
        result,
        evidence,
        execution_note or planner_note,
        client,
    )
    return AgentResult(
        answer=answer,
        evidence=evidence,
        code=code,
        computation_note=execution_note or planner_note,
    )


def load_data(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    raise ValueError("Only CSV and Excel files are supported.")
