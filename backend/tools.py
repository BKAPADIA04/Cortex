import ast
import operator

from ddgs import DDGS
from langchain_core.tools import tool

_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
        return _OPERATORS[type(node.op)](_eval_node(node.operand))
    raise ValueError("Expression contains unsupported syntax")


@tool
def calculator(expression: str) -> str:
    """Evaluate a basic arithmetic expression (+, -, *, /, //, %, **, parentheses).

    Use this whenever the user asks for a numeric calculation instead of
    computing it yourself. Example input: "(12 + 8) * 3 / 2".
    """
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval_node(tree.body))
    except Exception as exc:
        return f"Could not evaluate '{expression}': {exc}"


@tool
def duckduckgo_search(query: str) -> str:
    """Search the web via DuckDuckGo for current or factual information.

    Use this when the user asks about recent events, facts you're unsure
    of, or anything that benefits from up-to-date web results.
    """
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=5))

    if not results:
        return "No results found."

    return "\n\n".join(
        f"{r['title']}\n{r['href']}\n{r['body']}" for r in results
    )


TOOLS = [duckduckgo_search, calculator]
