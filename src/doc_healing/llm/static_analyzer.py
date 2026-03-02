"""Static code analyzer using Python's built-in ast and compile modules.

Detects syntax errors, common bugs (missing args, type errors), and
provides fixes without needing any external AI model.
"""

import ast
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def analyze_python_code(code: str) -> Dict[str, Any]:
    """Analyze Python code for errors using ast/compile.
    
    Returns a dict with:
      - errors: list of detected issues
      - fixed_code: corrected code (if fixable)
      - has_issues: bool
    """
    errors = []
    fixed_code = code
    
    # Step 1: Check for syntax errors via compile
    try:
        compile(code, "<snippet>", "exec")
    except SyntaxError as e:
        errors.append({
            "type": "SyntaxError",
            "message": str(e),
            "line": e.lineno,
            "detail": f"Line {e.lineno}: {e.msg}"
        })
    
    # Step 2: AST-based analysis for runtime bugs
    try:
        tree = ast.parse(code)
        
        # Collect function definitions with their parameter counts
        func_defs = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Count params excluding 'self'
                params = [arg.arg for arg in node.args.args if arg.arg != "self"]
                defaults = len(node.args.defaults)
                min_args = len(params) - defaults
                max_args = len(params)
                func_defs[node.name] = {
                    "params": params,
                    "min_args": min_args,
                    "max_args": max_args,
                    "line": node.lineno
                }
        
        # Check function calls for wrong number of arguments
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                func_name = node.func.id
                if func_name in func_defs:
                    n_args = len(node.args)
                    info = func_defs[func_name]
                    
                    if n_args < info["min_args"]:
                        missing = info["params"][n_args:]
                        errors.append({
                            "type": "TypeError",
                            "message": f"{func_name}() missing {len(missing)} required argument(s): {', '.join(missing)}",
                            "line": node.lineno,
                            "detail": f"Line {node.lineno}: {func_name}() called with {n_args} arg(s), needs {info['min_args']}-{info['max_args']}"
                        })
                    elif n_args > info["max_args"] and not any([
                        node.args and isinstance(node.args[-1], ast.Starred)
                    ]):
                        errors.append({
                            "type": "TypeError",
                            "message": f"{func_name}() takes {info['max_args']} argument(s) but {n_args} were given",
                            "line": node.lineno,
                            "detail": f"Line {node.lineno}: Too many arguments"
                        })
            
            # Check for string + non-string concatenation with BinOp(Add)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                left_is_str = _is_string_node(node.left)
                right_is_str = _is_string_node(node.right)
                if (left_is_str and not right_is_str) or (not left_is_str and right_is_str):
                    # Only flag if one side is definitely a string and the other is a function call or variable
                    if left_is_str or right_is_str:
                        non_str = node.right if left_is_str else node.left
                        if isinstance(non_str, (ast.Call, ast.Name)):
                            errors.append({
                                "type": "TypeError",
                                "message": "Possible type error: string concatenation with non-string value",
                                "line": node.lineno,
                                "detail": f"Line {node.lineno}: Cannot concatenate str and non-str. Use str() or f-string."
                            })
    except SyntaxError:
        pass  # Already caught above
    
    # Step 3: Generate fix suggestions
    if errors:
        fixed_code = _generate_fix(code, errors, func_defs if 'func_defs' in dir() else {})
    
    return {
        "errors": errors,
        "fixed_code": fixed_code if fixed_code != code else None,
        "has_issues": len(errors) > 0,
        "analysis_method": "static"
    }


def _is_string_node(node: ast.expr) -> bool:
    """Check if an AST node is definitely a string literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.JoinedStr):  # f-string
        return True
    return False


def _generate_fix(code: str, errors: List[Dict], func_defs: Dict) -> str:
    """Attempt to auto-fix detected errors."""
    lines = code.split("\n")
    
    for error in errors:
        err_type = error["type"]
        line_no = error.get("line", 0)
        
        if err_type == "TypeError" and "missing" in error["message"]:
            # Fix missing arguments by adding placeholder values
            if line_no and line_no <= len(lines):
                line = lines[line_no - 1]
                # Find the function call and add missing args
                func_match = re.search(r'(\w+)\((.*?)\)', line)
                if func_match:
                    func_name = func_match.group(1)
                    if func_name in func_defs:
                        info = func_defs[func_name]
                        existing_args = [a.strip() for a in func_match.group(2).split(",") if a.strip()]
                        missing_params = info["params"][len(existing_args):]
                        # Add sensible defaults
                        defaults = []
                        for p in missing_params:
                            if "percent" in p.lower() or "rate" in p.lower():
                                defaults.append("10")
                            elif "price" in p.lower() or "amount" in p.lower() or "cost" in p.lower():
                                defaults.append("100")
                            elif "name" in p.lower() or "text" in p.lower() or "str" in p.lower():
                                defaults.append('"value"')
                            else:
                                defaults.append("0")
                        
                        new_args = ", ".join(existing_args + defaults)
                        new_call = f"{func_name}({new_args})"
                        lines[line_no - 1] = line.replace(func_match.group(0), new_call)
        
        elif err_type == "TypeError" and "concatenat" in error["message"]:
            # Fix string + non-string by wrapping in str()
            if line_no and line_no <= len(lines):
                line = lines[line_no - 1]
                # Replace pattern like "text" + var with f"text{var}" or "text" + str(var)
                line = re.sub(
                    r'"([^"]*?)"\s*\+\s*(\w+)',
                    r'f"\1{\2}"',
                    line
                )
                lines[line_no - 1] = line
    
    return "\n".join(lines)


def format_errors_markdown(errors: List[Dict]) -> str:
    """Format errors as a markdown list for PR comments."""
    if not errors:
        return ""
    
    lines = []
    for e in errors:
        icon = {"SyntaxError": "🔴", "TypeError": "🟡"}.get(e["type"], "⚠️")
        lines.append(f"- {icon} **{e['type']}**: {e['message']}")
    
    return "\n".join(lines)
