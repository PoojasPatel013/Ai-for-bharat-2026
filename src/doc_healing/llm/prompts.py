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
    return f"""Please fix the following {language} code snippet.

Original Code:
```{language}
{original_code}
```

Execution Error:
```
{error_log}
```

Corrected Code:
"""
