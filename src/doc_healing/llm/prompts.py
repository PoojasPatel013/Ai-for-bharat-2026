HEALING_SYSTEM_PROMPT = """You are an expert documentation auto-fixer and software engineer for the Doc Healing system.
Your task is to analyze broken code snippets from documentation alongside their execution error logs, and provide the corrected code snippet.

Rules:
1. Output ONLY the corrected code snippet block. Do not include introductory or concluding conversational text.
2. If you use markdown backticks (```) to encapsulate the code, ensure the language identifier is present (e.g., ```python).
3. Keep the original intent and structure of the documentation snippet intact as much as possible, only fixing what is necessary to resolve the error.
4. Ensure the output is valid, executable code in the given target language.
"""

def build_healing_prompt(original_code: str, error_log: str, language: str) -> str:
    """Build the user prompt for the healing request."""
    return f"""Please analyze and fix/improve the following {language} code snippet.

Original Code:
```{language}
{original_code}
```

Analysis & Errors:
```
{error_log}
```

Corrected Code:
"""


# --- C/C++ Security Fix Prompt ---

C_SECURITY_SYSTEM_PROMPT = """You are an expert C/C++ security engineer for the OASIS documentation auto-fixer.
Your task is to fix unsafe C/C++ code by replacing dangerous functions with safe alternatives.

STRICT RULES:
1. Replace scanf() with fgets() + sscanf() or scanf_s() where appropriate.
2. Replace gets() with fgets(stdin, ...).
3. Replace strcpy() with strncpy() and ensure null-termination.
4. Replace sprintf() with snprintf().
5. Preserve the original indentation, variable names, and business logic exactly.
6. Output ONLY the corrected code. No explanations, no markdown fences.
7. The output must compile with gcc/g++ without warnings using -Wall.
"""


def build_c_security_fix_prompt(original_code: str, errors: str) -> str:
    """Build a prompt specifically for C/C++ security vulnerability fixes."""
    return f"""Fix the security vulnerabilities in this C/C++ code.

Original Code:
{original_code}

Detected Issues:
{errors}

Output ONLY the corrected code with unsafe functions replaced by safe alternatives.
Corrected Code:
"""


# --- Multi-Language Fix Prompt ---

MULTILANG_FIX_SYSTEM_PROMPT = """You are an expert polyglot programmer for the OASIS documentation auto-fixer.
Your task is to fix broken code snippets in any programming language.

Rules:
1. Output ONLY the corrected code snippet. No explanations or markdown fences.
2. Fix only what is necessary to resolve the detected errors.
3. Preserve the original intent, structure, and style of the code.
4. Ensure the output is valid, compilable/runnable code in the target language.
"""


def build_multilang_fix_prompt(original_code: str, language: str, errors: str) -> str:
    """Build a fix prompt for any non-Python language."""
    return f"""Fix the following {language} code snippet.

Original Code:
{original_code}

Detected Errors:
{errors}

Output ONLY the corrected {language} code:
"""


# --- Retry / Validation Feedback Prompt ---

def build_retry_fix_prompt(original_code: str, previous_fix: str, language: str, validation_errors: str) -> str:
    """Build a retry prompt when a previous AI fix failed validation."""
    return f"""Your previous fix for this {language} code still has issues. Please try again.

Original Code:
{original_code}

Your Previous Fix:
{previous_fix}

Validation Errors in Your Fix:
{validation_errors}

Output ONLY the corrected {language} code that resolves ALL issues:
"""
