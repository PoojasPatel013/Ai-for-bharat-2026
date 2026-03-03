# Bugfix Requirements Document

## Introduction

The OASIS bot has two critical issues affecting fix generation quality and multi-language support:

1. **Multi-Language Fix Generation Gap**: The bot fails to provide fix suggestions for non-Python languages (C, C++, JavaScript, Rust, Ruby, C#, etc.) in PR comments, even though it successfully detects errors in these languages. The `_generate_fix()` function only handles Python-specific errors, leaving other languages without automated fixes.

2. **Unreliable C/C++ Security Fixes**: When Claude 3 Haiku (Amazon Bedrock Edition) generates fixes for C/C++ security vulnerabilities (unsafe functions like scanf, gets, strcpy), it sometimes produces incorrect code snippets that fail static analysis validation. There is no validation loop to verify that generated fixes actually resolve the detected vulnerabilities before presenting them to users.

These issues limit the bot's usefulness for multi-language codebases and can lead to users applying incorrect security fixes. The bot also doesn't display which language was detected, reducing transparency in the analysis process.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN analyzing C/C++ code with security vulnerabilities (e.g., unsafe scanf, gets, strcpy usage) THEN the system detects the error but Claude 3 Haiku (Amazon Bedrock Edition) sometimes generates incorrect fix suggestions that still fail static analysis

1.2 WHEN Claude 3 Haiku (Amazon Bedrock Edition) generates a fix for C/C++ code THEN the system directly presents the fix to users without validating it through the static analyzer

1.3 WHEN a generated fix is incorrect or introduces new issues THEN the system has no retry mechanism to regenerate a better fix

1.4 WHEN analyzing Rust, Ruby, C#, or other non-Python/non-JavaScript languages with syntax errors THEN the system detects the error but returns `fixed_code: None` instead of generating a fix suggestion

1.5 WHEN analyzing JavaScript code with syntax errors THEN the system detects the error but returns `fixed_code: None` instead of generating a fix suggestion

1.6 WHEN analyzing any non-Python code with errors THEN the system does not invoke Claude 3 Haiku (Amazon Bedrock Edition) to generate fix suggestions collaboratively with static analysis

1.7 WHEN displaying PR comment results THEN the system does not show which language was detected for each code snippet

1.8 WHEN the `_generate_fix()` function is called with non-Python errors THEN the system only processes Python-specific error types (SyntaxError, NameError, TypeError) and ignores other language errors

### Expected Behavior (Correct)

2.1 WHEN Claude 3 Haiku (Amazon Bedrock Edition) generates a fix for C/C++ security vulnerabilities THEN the system SHALL pass the fixed code back through the static analyzer to validate it resolves the vulnerability

2.2 WHEN a generated fix still fails static analysis validation THEN the system SHALL send the error feedback back to Claude 3 Haiku (Amazon Bedrock Edition) with a retry request (up to 2-3 retries)

2.3 WHEN Claude 3 Haiku (Amazon Bedrock Edition) fails to generate a correct fix after maximum retries THEN the system SHALL report that auto-fix is unavailable and provide the static analysis error details to the user

2.4 WHEN generating C/C++ security fixes THEN the system SHALL use Claude 3 Haiku (Amazon Bedrock Edition) with a structured prompt containing strict rules for replacing unsafe functions (scanf→fgets/scanf_s, gets→fgets, strcpy→strncpy) while preserving indentation and business logic

2.5 WHEN analyzing Rust, Ruby, C#, or other non-Python languages with syntax errors THEN the system SHALL generate fix suggestions by invoking Claude 3 Haiku (Amazon Bedrock Edition) with language-specific context

2.6 WHEN analyzing JavaScript code with syntax errors THEN the system SHALL generate fix suggestions by invoking Claude 3 Haiku (Amazon Bedrock Edition) collaboratively with static analysis

2.7 WHEN analyzing any non-Python code with detected errors THEN the system SHALL invoke Claude 3 Haiku (Amazon Bedrock Edition) collaboratively with static analysis to provide intelligent fix suggestions

2.8 WHEN displaying PR comment results THEN the system SHALL show the detected language for each code snippet (e.g., "Language: C", "Language: JavaScript", "Language: Rust")

2.9 WHEN the fix generation logic processes errors from any supported language THEN the system SHALL either generate language-appropriate fixes using Claude 3 Haiku (Amazon Bedrock Edition) or delegate to the validation loop for verification

### Unchanged Behavior (Regression Prevention)

3.1 WHEN analyzing Python code with syntax errors THEN the system SHALL CONTINUE TO generate fix suggestions using the existing `_generate_fix()` function

3.2 WHEN language detection identifies Python, JavaScript, C, C++, Rust, Ruby, or C# code THEN the system SHALL CONTINUE TO correctly detect the language using existing patterns

3.3 WHEN static analysis detects errors in any language THEN the system SHALL CONTINUE TO identify and report those errors accurately

3.4 WHEN Claude 3 Haiku (Amazon Bedrock Edition) is unavailable or fails THEN the system SHALL CONTINUE TO fall back gracefully and still report static analysis results

3.5 WHEN displaying PR comments for code with no issues THEN the system SHALL CONTINUE TO show "No issues detected" or "All code looks good"

3.6 WHEN analyzing Python code that can be auto-fixed THEN the system SHALL CONTINUE TO display the fixed code in PR comments

3.7 WHEN the static analyzer successfully identifies vulnerabilities THEN the system SHALL CONTINUE TO report them with accurate line numbers and descriptions

3.8 WHEN processing PR webhooks THEN the system SHALL CONTINUE TO extract code snippets from markdown files and analyze them
