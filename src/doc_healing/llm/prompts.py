"""Prompts for the LLM documentation healing engine."""

def generate_healing_prompt(code: str, language: str, errors: list[str]) -> str:
    """Generate a prompt asking the LLM to heal the given code.
    
    Args:
        code: The original broken code snippet.
        language: The programming language of the snippet.
        errors: A list of errors encountered when validating the code.
        
    Returns:
        The formatted prompt string.
    """
    error_list = "\n".join([f"- {error}" for error in errors])
    
    return f"""You are an automated documentation auto-fixer. 
Your task is to fix a broken code snippet found in the project's documentation. 

The snippet is written in: {language}

Here is the broken code:
```{language}
{code}
```

When this code was validated, it produced the following errors:
{error_list}

Please provide ONLY the corrected code snippet. 
Do not include any explanations, apologies, or markdown formatting other than the backticks surrounding the code block.
The corrected code must resolve the errors while preserving the original intent of the documentation example.
"""
