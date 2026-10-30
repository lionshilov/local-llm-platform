"""Safe arithmetic: an AST walker over an allowlist of operators, functions and constants.

Nothing is ever passed to ``eval``. The expression is parsed with ``ast.parse`` and only
the node types handled below are interpreted; names, attributes, subscripts, keyword
arguments and every other construct are rejected. Integer sizes and exponents are bounded
so that ``9**9**9`` fails instantly instead of eating the CPU and memory.
"""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable

from llm_agent.tools.base import ToolError, tool

type Number = int | float

MAX_EXPRESSION_CHARS = 500
MAX_INT_BITS = 4096  # about 1,233 decimal digits


class CalculatorError(ToolError):
    pass


def _check(value: Number) -> Number:
    if isinstance(value, int) and value.bit_length() > MAX_INT_BITS:
        raise CalculatorError(f"result is too large (over {MAX_INT_BITS} bits)")
    if isinstance(value, float) and not math.isfinite(value):
        raise CalculatorError("result is not a finite number (overflow)")
    return value


def _power(base: Number, exponent: Number) -> Number:
    # |base ** exponent| needs exponent * log2|base| bits: check before computing it.
    if (
        isinstance(base, int)
        and isinstance(exponent, int)
        and abs(base) > 1
        and exponent * math.log2(abs(base)) > MAX_INT_BITS
    ):
        raise CalculatorError(f"result is too large (over {MAX_INT_BITS} bits)")
    result = base**exponent
    if isinstance(result, complex):
        raise CalculatorError("result is a complex number (fractional power of a negative)")
    return result


_BINARY: dict[type[ast.operator], Callable[[Number, Number], Number]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: _power,
}
_UNARY: dict[type[ast.unaryop], Callable[[Number], Number]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
FUNCTIONS: dict[str, Callable[..., Number]] = {
    "sqrt": math.sqrt,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "floor": math.floor,
    "ceil": math.ceil,
}
CONSTANTS: dict[str, float] = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _call(node: ast.Call) -> Number:
    if not isinstance(node.func, ast.Name):
        raise CalculatorError("only direct calls like sqrt(2) are allowed")
    function = FUNCTIONS.get(node.func.id)
    if function is None:
        raise CalculatorError(
            f"unknown function '{node.func.id}'; available: {', '.join(FUNCTIONS)}"
        )
    if node.keywords or any(isinstance(arg, ast.Starred) for arg in node.args):
        raise CalculatorError("functions take positional arguments only")
    args = [_eval(arg) for arg in node.args]
    try:
        return function(*args)
    except OverflowError as exc:
        raise CalculatorError(f"{node.func.id}(): result is too large (overflow)") from exc
    except (ValueError, TypeError) as exc:
        raise CalculatorError(f"{node.func.id}(): {exc}") from exc


def _eval(node: ast.AST) -> Number:
    match node:
        case ast.Constant(value=bool()):
            raise CalculatorError("booleans are not numbers here")
        case ast.Constant(value=int() | float() as value):
            return _check(value)
        case ast.Name(id=name):
            if name in CONSTANTS:
                return CONSTANTS[name]
            raise CalculatorError(f"unknown name '{name}'; constants: {', '.join(CONSTANTS)}")
        case ast.UnaryOp(op=op, operand=operand) if type(op) in _UNARY:
            return _UNARY[type(op)](_eval(operand))
        case ast.BinOp(op=ast.BitXor()):
            raise CalculatorError("'^' is not supported; use ** for powers")
        case ast.BinOp(left=left, op=op, right=right) if type(op) in _BINARY:
            try:
                return _check(_BINARY[type(op)](_eval(left), _eval(right)))
            except ZeroDivisionError as exc:
                raise CalculatorError("division by zero") from exc
            except OverflowError as exc:
                raise CalculatorError("result is too large (overflow)") from exc
        case ast.Call():
            return _check(_call(node))
        case ast.Attribute():
            raise CalculatorError("attribute access is not allowed")
        case _:
            raise CalculatorError(f"unsupported syntax: {type(node).__name__}")


def evaluate(expression: str) -> Number:
    """Evaluate ``expression`` using only the allowlisted arithmetic."""
    if len(expression) > MAX_EXPRESSION_CHARS:
        raise CalculatorError(f"expression is longer than {MAX_EXPRESSION_CHARS} characters")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"invalid expression: {exc.msg}") from exc
    try:
        return _eval(tree.body)
    except RecursionError as exc:
        raise CalculatorError("expression is nested too deeply") from exc


def format_number(value: Number) -> str:
    if isinstance(value, int):
        return str(value)
    # 15 significant digits hide binary noise: 0.1 + 0.2 -> "0.3", sqrt(16) -> "4".
    return f"{value:.15g}"


@tool
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression exactly. Use it for every calculation.

    Supports + - * / // % ** and parentheses; the functions sqrt, log (natural, or
    log(x, base)), log2, log10, exp, sin, cos, tan, asin, acos, atan (radians), abs,
    round, min, max, floor, ceil; and the constants pi, e, tau.

    Args:
        expression: One expression, e.g. "(1200 * 0.07) / 12" or "sqrt(2) * pi".
    """
    return format_number(evaluate(expression))
