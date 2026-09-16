import ast
import operator

from mcp.server.fastmcp import FastMCP

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


mcp = FastMCP("cortex-calculator")


@mcp.tool()
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


if __name__ == "__main__":
    mcp.run(transport="stdio")
