import re
import warnings
 
_TEXT_CMD = re.compile(r"\\(?:text|mathrm|textbf|mbox)\{[^{}]*\}")
_FRAC = re.compile(r"\\frac\{([^{}]+)\}\{([^{}]+)\}")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_ALLOWED = re.compile(r"^[\d\.\s\+\-\*/\(\)]+$")
_LEADING_NUM = re.compile(r"^\s*(-?\d+(?:\.\d+)?)")
 
 
def _normalise(line: str) -> str:
    s = _TEXT_CMD.sub(" ", line)
    s = _FRAC.sub(r"(\1)/(\2)", s)
    s = (s.replace("\\times", "*").replace("×", "*").replace("\\cdot", "*").replace("·", "*")
          .replace("\\div", "/").replace("÷", "/").replace("−", "-")
          .replace("\\[", " ").replace("\\]", " ").replace("\\(", " ").replace("\\)", " ")
          .replace("$", " ").replace("\\", " "))
    s = _THOUSANDS.sub("", s)
    out = []
    for tok in re.split(r"(\s+)", s):
        if not tok or tok.isspace():
            out.append(tok)
        elif tok.lower() in ("x", "*"):             # "9 x 2" as multiplication
            out.append("*")
        elif re.fullmatch(r"[A-Za-z][A-Za-z'’\.]*[,:;!?]?", tok):
            out.append(" ")                          # a plain word (unit, filler): drop it
        elif re.search(r"[A-Za-z]", tok):
            out.append(" | ")                        # letters glued to numbers/operators: hard break
        else:
            out.append(tok.replace(",", " | ").replace(":", " | ").replace(";", " | "))
    s = "".join(out)
    prev = None
    while prev != s:                                 # "( )" left behind by removed \text{...}
        prev = s
        s = re.sub(r"\(\s*\)", " ", s)
    return s
 
 
def _safe_eval(expr: str):
    expr = expr.strip()
    if not expr or not _ALLOWED.match(expr) or "**" in expr or "//" in expr:
        return None
    try:
        with warnings.catch_warnings():              # "2 (3)" -> harmless "'int' object is not callable" SyntaxWarning
            warnings.simplefilter("ignore")
            return float(eval(expr, {"__builtins__": {}}, {}))
    except Exception:
        return None
 
 
def _tail_expression(left: str):
    seg = left.split("|")[-1]
    m = re.search(r"[\d\.\s\+\-\*/\(\)]+$", seg)
    if not m:
        return None
    expr = m.group(0).strip()
    # Longest suffix that is a complete expression: "2  2 / 2" (from "Half of 2 is 2 / 2") -> "2 / 2".
    starts = [i for i, ch in enumerate(expr) if (ch.isdigit() or ch == "(") and (i == 0 or expr[i - 1] == " ")]
    for i in starts:
        cand = expr[i:].strip()
        if re.search(r"\d\s*[\+\-\*/]\s*[\d\(]", cand) and _safe_eval(cand) is not None:
            return cand
    return None
 
 
def _matches(value: float, shown: str) -> bool:
    target = float(shown)
    decimals = len(shown.split(".")[1]) if "." in shown else 0
    if abs(value - target) <= 1e-6 * max(1.0, abs(target)):
        return True
    return decimals > 0 and round(value, decimals) == round(target, decimals)   # "10/3 = 3.33"
 
 
def check_equations(text: str) -> list:
    results = []
    for line in text.splitlines():
        if "=" not in line:
            continue
        parts = _normalise(line).split("=")
        for left, right in zip(parts, parts[1:]):
            expr = _tail_expression(left)
            m = _LEADING_NUM.match(right.split("|")[0])
            if expr is None or m is None:
                continue
            value = _safe_eval(expr)
            if value is None:
                continue
            results.append({"line": line.strip(), "lhs": expr, "rhs": m.group(1),
                            "value": value, "ok": _matches(value, m.group(1))})
    return results
 