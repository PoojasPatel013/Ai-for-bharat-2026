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
        
        elif err_type == "SyntaxError":
            # Attempt simple bracket/paren fixes
            if "EOF" in error["message"] or "unexpected" in error["message"].lower():
                # Count unmatched brackets
                full = "\n".join(lines)
                open_parens = full.count("(") - full.count(")")
                open_brackets = full.count("[") - full.count("]")
                open_braces = full.count("{") - full.count("}")
                suffix = ")" * max(0, open_parens) + "]" * max(0, open_brackets) + "}" * max(0, open_braces)
                if suffix:
                    lines[-1] = lines[-1] + suffix
    
    return "\n".join(lines)


def generate_fix_with_ai(code: str, language: str, errors: List[Dict]) -> Optional[str]:
    """Generate a fix for any language using Claude 3 Haiku via Bedrock.
    
    Uses specialized prompts for C/C++ security issues and a general
    multi-language prompt for everything else.
    
    Returns the fixed code string, or None if AI is unavailable.
    """
    try:
        from doc_healing.llm.bedrock_client import BedrockLLMClient
        from doc_healing.llm.prompts import (
            C_SECURITY_SYSTEM_PROMPT,
            MULTILANG_FIX_SYSTEM_PROMPT,
            build_c_security_fix_prompt,
            build_multilang_fix_prompt,
        )
        
        error_text = "; ".join(e["message"] for e in errors)
        lang = language.lower()
        
        # Use specialized C/C++ security prompt when unsafe functions are detected
        unsafe_keywords = ["scanf", "gets", "strcpy", "sprintf", "unsafe"]
        is_c_security = lang in ("c", "cpp", "c++") and any(
            kw in error_text.lower() for kw in unsafe_keywords
        )
        
        if is_c_security:
            system_prompt = C_SECURITY_SYSTEM_PROMPT
            prompt = build_c_security_fix_prompt(code, error_text)
        else:
            system_prompt = MULTILANG_FIX_SYSTEM_PROMPT
            prompt = build_multilang_fix_prompt(code, language, error_text)
        
        client = BedrockLLMClient()
        fix = client.generate_correction(prompt=prompt, system_prompt=system_prompt)
        
        if fix and fix.strip() and fix.strip() != code.strip():
            logger.info(f"AI generated fix for {language} code ({len(errors)} error(s))")
            return fix.strip()
        
        return None
    except Exception as e:
        logger.warning(f"AI fix generation unavailable for {language}: {str(e)[:100]}")
        return None


def analyze_javascript_code(code: str) -> Dict[str, Any]:
    """Analyze JavaScript/TypeScript code for common errors using heuristics.
    
    Checks for:
      - Mismatched brackets/parens/braces
      - C-style functions that don't exist in JS (scanf, printf, ptf)
      - Obvious syntax patterns ($$, unclosed strings)
    """
    errors = []
    
    # Check mismatched brackets
    bracket_errors = _check_brackets(code)
    errors.extend(bracket_errors)
    
    # Check for C-only functions used in JS context
    c_only_funcs = {
        "scanf": "Use prompt() or readline for user input",
        "printf": "Use console.log() for output",
        "ptf": "Use console.log() for output",
        "gets": "Use prompt() or readline for input",
        "puts": "Use console.log() for output",
        "fprintf": "Use console.log() or fs.writeFileSync()",
        "fscanf": "Use fs.readFileSync() for file input",
    }
    # Java functions that don't exist in JS
    java_funcs = {
        "System.out.println": "Use console.log() instead",
        "System.out.print": "Use process.stdout.write() instead",
    }
    # C++ functions that don't exist in JS
    cpp_funcs = {
        "cout": "Use console.log() instead",
        "cin": "Use prompt() or readline instead",
        "endl": "Use '\\n' instead",
    }
    for line_no, line in enumerate(code.split("\n"), 1):
        stripped = line.strip()
        for func, suggestion in c_only_funcs.items():
            if re.search(rf'\b{func}\s*\(', stripped):
                errors.append({
                    "type": "ReferenceError",
                    "message": f"'{func}' is not defined in JavaScript (C/C++ function). {suggestion}",
                    "line": line_no,
                    "detail": f"Line {line_no}: '{func}' does not exist in JS. {suggestion}"
                })
        for func, suggestion in java_funcs.items():
            if func in stripped:
                errors.append({
                    "type": "ReferenceError",
                    "message": f"'{func}' is a Java method, not valid in JavaScript. {suggestion}",
                    "line": line_no,
                    "detail": f"Line {line_no}: {suggestion}"
                })
        for func, suggestion in cpp_funcs.items():
            if re.search(rf'\b{func}\b', stripped) and not stripped.startswith("//"):
                errors.append({
                    "type": "ReferenceError",
                    "message": f"'{func}' is a C++ construct, not valid in JavaScript. {suggestion}",
                    "line": line_no,
                    "detail": f"Line {line_no}: {suggestion}"
                })
        
        # Check for $$ which is not valid in most contexts
        if "$$" in stripped and not stripped.startswith("//") and not stripped.startswith("/*"):
            errors.append({
                "type": "SyntaxError",
                "message": "'$$' is not a valid expression",
                "line": line_no,
                "detail": f"Line {line_no}: '$$' is not valid JavaScript syntax"
            })
    
    # Attempt AI fix generation for detected errors
    fixed_code = None
    if errors:
        fixed_code = generate_fix_with_ai(code, "javascript", errors)
    
    return {
        "errors": errors,
        "fixed_code": fixed_code,
        "has_issues": len(errors) > 0,
        "analysis_method": "static_js"
    }


def analyze_c_code(code: str) -> Dict[str, Any]:
    """Analyze C/C++ code for security vulnerabilities and common bugs.
    
    Detects:
      - Unsafe functions: scanf, gets, strcpy, sprintf (buffer overflow risks)
      - Format string vulnerabilities
      - Missing #include for used functions
      - Mismatched brackets
      - Nested function calls that make no sense (e.g., printf(scanf()))
    """
    errors = []
    
    # Check mismatched brackets
    bracket_errors = _check_brackets(code)
    errors.extend(bracket_errors)
    
    # Unsafe function mapping: function -> (severity, safe_alternative, reason)
    unsafe_functions = {
        "gets": ("critical", "fgets(buf, sizeof(buf), stdin)",
                 "gets() has no bounds checking — buffer overflow vulnerability (CWE-120)"),
        "scanf": ("warning", "fgets() + sscanf() or scanf_s()",
                  "scanf() with %s has no bounds checking — use width specifiers or fgets()"),
        "strcpy": ("warning", "strncpy(dst, src, sizeof(dst)-1)",
                   "strcpy() has no bounds checking — use strncpy() with explicit size"),
        "sprintf": ("warning", "snprintf(buf, sizeof(buf), ...)",
                    "sprintf() has no bounds checking — use snprintf()"),
        "strcat": ("warning", "strncat(dst, src, sizeof(dst)-strlen(dst)-1)",
                   "strcat() has no bounds checking — use strncat()"),
    }
    
    lines = code.split("\n")
    has_include_stdio = bool(re.search(r'#include\s*<stdio\.h>', code))
    has_include_string = bool(re.search(r'#include\s*<string\.h>', code))
    uses_printf = bool(re.search(r'\bprintf\s*\(', code))
    uses_scanf = bool(re.search(r'\bscanf\s*\(', code))
    uses_strcpy = bool(re.search(r'\bstrcpy\s*\(', code))
    
    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue
        
        # Check unsafe functions
        for func, (severity, safe_alt, reason) in unsafe_functions.items():
            if re.search(rf'\b{func}\s*\(', stripped):
                err_type = "SecurityWarning" if severity == "warning" else "SecurityError"
                errors.append({
                    "type": err_type,
                    "message": f"Unsafe function '{func}()': {reason}. Use {safe_alt}",
                    "line": line_no,
                    "detail": f"Line {line_no}: Replace {func}() with {safe_alt}"
                })
        
        # Nested nonsense: printf(scanf()) makes no sense
        if re.search(r'\bprintf\s*\(\s*scanf\s*\(', stripped):
            errors.append({
                "type": "SyntaxError",
                "message": "printf(scanf()) is invalid — scanf returns int (count of items read), not a string",
                "line": line_no,
                "detail": f"Line {line_no}: scanf() returns an int, cannot be used as printf() argument directly"
            })
        
        # Format string without arguments: printf(var) instead of printf("%s", var)
        printf_match = re.search(r'\bprintf\s*\(\s*(\w+)\s*\)', stripped)
        if printf_match and not printf_match.group(1).startswith('"'):
            var = printf_match.group(1)
            if var not in ("NULL", "stdin", "stdout", "stderr"):
                errors.append({
                    "type": "SecurityWarning",
                    "message": f"Format string vulnerability: printf({var}) — use printf(\"%s\", {var}) instead",
                    "line": line_no,
                    "detail": f"Line {line_no}: Direct variable in printf() is a format string attack vector"
                })
    
    # Missing includes
    if (uses_printf or uses_scanf) and not has_include_stdio:
        errors.append({
            "type": "Warning",
            "message": "Missing '#include <stdio.h>' — required for printf/scanf",
            "line": 1,
            "detail": "Add #include <stdio.h> at the top of the file"
        })
    if uses_strcpy and not has_include_string:
        errors.append({
            "type": "Warning",
            "message": "Missing '#include <string.h>' — required for strcpy/strncpy",
            "line": 1,
            "detail": "Add #include <string.h> at the top of the file"
        })
    
    # Attempt AI fix generation for detected errors
    fixed_code = None
    if errors:
        fixed_code = generate_fix_with_ai(code, "c", errors)
    
    return {
        "errors": errors,
        "fixed_code": fixed_code,
        "has_issues": len(errors) > 0,
        "analysis_method": "static_c"
    }


def analyze_generic_code(code: str, language: str = "unknown") -> Dict[str, Any]:
    """Analyze code of any language using generic heuristics.
    
    Detects:
      - Mismatched brackets/parens/braces
      - Mixed-language patterns (Python print with C semicolons)
      - Undefined or nonsensical function names
      - Completely malformed lines
    """
    errors = []
    
    # Check mismatched brackets
    bracket_errors = _check_brackets(code)
    errors.extend(bracket_errors)
    
    # Detect mixed-language patterns
    lines = code.split("\n")
    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue
        
        # Python print() with C-style semicolons
        if re.search(r'\bprint\s*\(.*\)\s*;', stripped):
            errors.append({
                "type": "SyntaxWarning",
                "message": "Mixed-language pattern: Python-style print() with C/JS-style semicolon",
                "line": line_no,
                "detail": f"Line {line_no}: 'print(...);\' — remove semicolon for Python or use console.log() for JS"
            })
        
        # C-style functions that are obviously wrong in most languages
        nonsense_funcs = {"ptf", "prnt", "prinf", "sacanf"}
        for func in nonsense_funcs:
            if re.search(rf'\b{func}\s*\(', stripped):
                errors.append({
                    "type": "ReferenceError",
                    "message": f"'{func}' is not a recognized function — did you mean 'print' or 'printf'?",
                    "line": line_no,
                    "detail": f"Line {line_no}: Possible typo in function name '{func}'"
                })
        
        # scanf/printf used outside C/C++
        if language not in ("c", "cpp", "c++"):
            c_func_replacements = {
                "scanf": {"python": "input()", "javascript": "prompt()", "java": "Scanner.nextLine()"},
                "printf": {"python": "print()", "javascript": "console.log()", "java": "System.out.println()"},
            }
            for func, replacements in c_func_replacements.items():
                if re.search(rf'\b{func}\s*\(', stripped):
                    suggestion = replacements.get(language, "the equivalent function in " + language)
                    errors.append({
                        "type": "ReferenceError",
                        "message": f"'{func}' is a C/C++ function, not valid in {language}. Use {suggestion} instead",
                        "line": line_no,
                        "detail": f"Line {line_no}: '{func}' is not available in {language}. Use {suggestion}"
                    })
        
        # Python-specific misuses in non-Python code
        if language not in ("python", "py"):
            if re.search(r'\bprint\s*\(', stripped) and language in ("c", "cpp", "c++"):
                errors.append({
                    "type": "ReferenceError",
                    "message": f"'print()' is a Python function, not valid in {language}. Use printf() instead",
                    "line": line_no,
                    "detail": f"Line {line_no}: 'print()' does not exist in {language}"
                })
        
        # Java-specific misuses
        if language not in ("java",):
            if "System.out.println" in stripped or "System.out.print" in stripped:
                py_or_js = "print()" if language in ("python", "py") else "console.log()"
                errors.append({
                    "type": "ReferenceError",
                    "message": f"'System.out.println' is Java-only, not valid in {language}. Use {py_or_js} instead",
                    "line": line_no,
                    "detail": f"Line {line_no}: Java method used in {language} context"
                })
        
        # $$ in non-shell/non-perl contexts
        if "$$" in stripped and language not in ("bash", "sh", "perl", "shell"):
            errors.append({
                "type": "SyntaxError",
                "message": "'$$' is not valid syntax in " + language,
                "line": line_no,
                "detail": f"Line {line_no}: Unexpected '$$'"
            })
    
    # Try Python compile as a bonus check — catches syntax errors if the code
    # happens to look like Python
    if not errors:
        try:
            compile(code, "<snippet>", "exec")
        except SyntaxError as e:
            errors.append({
                "type": "SyntaxError",
                "message": str(e),
                "line": e.lineno,
                "detail": f"Line {e.lineno}: {e.msg}"
            })
    
    # Attempt AI fix generation for detected errors
    fixed_code = None
    if errors:
        fixed_code = generate_fix_with_ai(code, language, errors)
    
    return {
        "errors": errors,
        "fixed_code": fixed_code,
        "has_issues": len(errors) > 0,
        "analysis_method": "static_generic"
    }


def _check_brackets(code: str) -> List[Dict]:
    """Check for mismatched brackets, parentheses, and braces."""
    errors = []
    stack = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {v: k for k, v in pairs.items()}
    in_string = False
    string_char = None
    
    for line_no, line in enumerate(code.split("\n"), 1):
        for i, ch in enumerate(line):
            # Skip characters inside strings
            if ch in ('"', "'") and (i == 0 or line[i-1] != "\\"):
                if in_string and ch == string_char:
                    in_string = False
                elif not in_string:
                    in_string = True
                    string_char = ch
                continue
            
            if in_string:
                continue
            
            if ch in pairs:
                stack.append((ch, line_no))
            elif ch in closing:
                if not stack:
                    errors.append({
                        "type": "SyntaxError",
                        "message": f"Unmatched closing '{ch}'",
                        "line": line_no,
                        "detail": f"Line {line_no}: Found closing '{ch}' without matching opening '{closing[ch]}'"
                    })
                else:
                    top, _ = stack[-1]
                    if pairs.get(top) == ch:
                        stack.pop()
                    else:
                        errors.append({
                            "type": "SyntaxError",
                            "message": f"Mismatched bracket: expected '{pairs[top]}' but found '{ch}'",
                            "line": line_no,
                            "detail": f"Line {line_no}: Expected '{pairs[top]}' to close '{top}' but got '{ch}'"
                        })
    
    for bracket, line_no in stack:
        errors.append({
            "type": "SyntaxError",
            "message": f"Unclosed '{bracket}'",
            "line": line_no,
            "detail": f"Line {line_no}: '{bracket}' is never closed"
        })
    
    return errors


def detect_language(code: str) -> str:
    """Attempt to auto-detect the programming language of a code snippet."""
    code_lower = code.lower()
    
    # Python indicators
    if re.search(r'\bdef \w+\s*\(', code) or re.search(r'\bimport \w+', code):
        return "python"
    if re.search(r'\bprint\s*\(', code) and ";" not in code:
        return "python"
    
    # JavaScript indicators
    if re.search(r'\b(const|let|var)\s+\w+', code) or re.search(r'\bconsole\.\w+', code):
        return "javascript"
    if re.search(r'\bfunction\s+\w+', code) or "=>" in code:
        return "javascript"
    
    # C/C++ indicators — check BEFORE fallback
    if re.search(r'#include\s*<', code) or re.search(r'\bint\s+main\s*\(', code):
        return "c"
    # If both printf AND scanf are present, almost certainly C
    if re.search(r'\bprintf\s*\(', code) and re.search(r'\bscanf\s*\(', code):
        return "c"
    # If printf/scanf with semicolons, likely C
    if re.search(r'\b(printf|scanf)\s*\(', code) and ";" in code:
        return "c"
    # If printf/scanf without semicolons but nested (e.g., printf(scanf())), still C
    if re.search(r'\b(printf|scanf)\s*\(.*\b(printf|scanf)\s*\(', code):
        return "c"
    # Single printf/scanf usage is still a strong C indicator
    if re.search(r'\b(printf|scanf)\s*\(', code):
        return "c"
    
    # Java
    if re.search(r'\bpublic\s+(static\s+)?class\s+', code):
        return "java"
    if "System.out.println" in code or "System.out.print" in code:
        return "java"
    
    # Bash
    if code.startswith("#!/bin/") or re.search(r'\becho\s+', code):
        return "bash"
    
    # Fallback: try Python compile
    try:
        compile(code, "<detect>", "exec")
        return "python"
    except SyntaxError:
        pass
    
    return "unknown"


def analyze_code(code: str, language: str = None) -> Dict[str, Any]:
    """Unified dispatcher — analyze code in any language.
    
    Auto-detects language if not provided, routes to the best available
    analyzer, and returns a consistent result dict.
    """
    if not language or language == "unknown":
        language = detect_language(code)
    
    lang = language.lower()
    
    if lang in ("python", "py"):
        result = analyze_python_code(code)
    elif lang in ("javascript", "js", "typescript", "ts"):
        result = analyze_javascript_code(code)
    elif lang in ("c", "cpp", "c++"):
        result = analyze_c_code(code)
    else:
        result = analyze_generic_code(code, language=lang)
    
    # Attach detected language to result for PR comment display
    result["detected_language"] = lang
    return result


def format_errors_markdown(errors: List[Dict]) -> str:
    """Format errors as a markdown list for PR comments."""
    if not errors:
        return ""
    
    lines = []
    for e in errors:
        lines.append(f"- `{e['type']}` — {e['message']}")
    
    return "\n".join(lines)
