"""Tests for the multi-language static analyzer."""

import pytest
from doc_healing.llm.static_analyzer import (
    analyze_python_code,
    analyze_javascript_code,
    analyze_generic_code,
    analyze_code,
    detect_language,
    format_errors_markdown,
    _check_brackets,
)


class TestAnalyzePython:
    """Python-specific analysis tests."""

    def test_detects_syntax_error(self):
        result = analyze_python_code("print('hello'")
        assert result["has_issues"]
        assert any(e["type"] == "SyntaxError" for e in result["errors"])

    def test_valid_code_no_issues(self):
        result = analyze_python_code("x = 1\nprint(x)")
        assert not result["has_issues"]

    def test_detects_missing_args(self):
        code = "def greet(name, age):\n    pass\n\ngreet()"
        result = analyze_python_code(code)
        assert result["has_issues"]
        assert any("missing" in e["message"] for e in result["errors"])


class TestAnalyzeJavaScript:
    """JavaScript-specific analysis tests."""

    def test_detects_c_functions_in_js(self):
        result = analyze_javascript_code("scanf(\"%d\")")
        assert result["has_issues"]
        assert any("scanf" in e["message"] for e in result["errors"])

    def test_detects_dollar_dollar(self):
        result = analyze_javascript_code("let x = $$;")
        assert result["has_issues"]
        assert any("$$" in e["message"] for e in result["errors"])

    def test_detects_ptf(self):
        result = analyze_javascript_code("ptf(\"hello\")")
        assert result["has_issues"]
        assert any("ptf" in e["message"] for e in result["errors"])

    def test_valid_js_no_issues(self):
        result = analyze_javascript_code("const x = 42;")
        assert not result["has_issues"]


class TestAnalyzeGeneric:
    """Generic code analysis tests."""

    def test_detects_print_with_semicolon(self):
        result = analyze_generic_code("print(hello);", language="unknown")
        assert result["has_issues"]

    def test_detects_ptf_typo(self):
        result = analyze_generic_code("ptf(scanf($$))", language="unknown")
        assert result["has_issues"]

    def test_detects_mismatched_brackets(self):
        result = analyze_generic_code("func((x)", language="unknown")
        assert result["has_issues"]
        assert any("bracket" in e["message"].lower() or "unclosed" in e["message"].lower()
                    for e in result["errors"])

    def test_detects_scanf_outside_c(self):
        result = analyze_generic_code("scanf(\"%d\", &x);", language="python")
        assert result["has_issues"]
        assert any("scanf" in e["message"] for e in result["errors"])

    def test_c_code_scanf_is_ok(self):
        """scanf should NOT be flagged in C."""
        result = analyze_generic_code("scanf(\"%d\", &x);", language="c")
        # Should not flag scanf as an error in C
        assert not any(
            e["type"] == "ReferenceError" and "scanf" in e["message"]
            for e in result["errors"]
        )


class TestCheckBrackets:
    """Bracket matching tests."""

    def test_balanced(self):
        assert _check_brackets("(a + b) * [c]") == []

    def test_unclosed_paren(self):
        errs = _check_brackets("print(hello")
        assert any("Unclosed" in e["message"] for e in errs)

    def test_mismatch(self):
        errs = _check_brackets("(a + b]")
        assert any("Mismatched" in e["message"] or "expected" in e["message"].lower()
                    for e in errs)


class TestDetectLanguage:
    """Language detection tests."""

    def test_python_def(self):
        assert detect_language("def foo():\n    pass") == "python"

    def test_python_import(self):
        assert detect_language("import os\nos.listdir('.')") == "python"

    def test_javascript_const(self):
        assert detect_language("const x = 42;") == "javascript"

    def test_c_include(self):
        assert detect_language("#include <stdio.h>\nint main() {}") == "c"

    def test_c_printf(self):
        assert detect_language('printf("hello");') == "c"


class TestAnalyzeCodeDispatcher:
    """Unified dispatcher tests."""

    def test_routes_python(self):
        result = analyze_code("print('hello'", language="python")
        assert result["has_issues"]
        assert result["analysis_method"] == "static"

    def test_routes_javascript(self):
        result = analyze_code("ptf('hello')", language="javascript")
        assert result["has_issues"]
        assert result["analysis_method"] == "static_js"

    def test_routes_generic(self):
        result = analyze_code("ptf(scanf($$))", language="ruby")
        assert result["has_issues"]
        assert result["analysis_method"] == "static_generic"

    def test_auto_detects_python(self):
        result = analyze_code("def foo():\n    pass", language=None)
        assert not result["has_issues"]

    def test_the_exact_broken_example(self):
        """The exact code from the user's broken PR must be detected."""
        result = analyze_code("print(hello);\nptf(scanf($$))")
        assert result["has_issues"]
        assert len(result["errors"]) > 0


class TestFormatErrors:
    """Markdown formatting tests."""

    def test_empty(self):
        assert format_errors_markdown([]) == ""

    def test_syntax_error_icon(self):
        md = format_errors_markdown([{"type": "SyntaxError", "message": "bad"}])
        assert "🔴" in md

    def test_reference_error_icon(self):
        md = format_errors_markdown([{"type": "ReferenceError", "message": "undef"}])
        assert "🔵" in md
