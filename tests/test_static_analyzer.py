"""Tests for the multi-language static analyzer."""

import pytest
from unittest.mock import patch, MagicMock
from doc_healing.llm.static_analyzer import (
    analyze_python_code,
    analyze_javascript_code,
    analyze_c_code,
    analyze_generic_code,
    analyze_code,
    detect_language,
    format_errors_markdown,
    _check_brackets,
    _generate_fix,
    generate_fix_with_ai,
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


class TestAnalyzeCCode:
    """C/C++ security analysis tests."""

    @patch('doc_healing.llm.static_analyzer.generate_fix_with_ai', return_value=None)
    def test_detects_unsafe_scanf(self, _mock):
        result = analyze_c_code('#include <stdio.h>\nscanf("%s", buf);')
        assert result["has_issues"]
        assert any("scanf" in e["message"] and "Unsafe" in e["message"] for e in result["errors"])
        assert result["analysis_method"] == "static_c"

    @patch('doc_healing.llm.static_analyzer.generate_fix_with_ai', return_value=None)
    def test_detects_unsafe_gets(self, _mock):
        result = analyze_c_code('#include <stdio.h>\ngets(buf);')
        assert result["has_issues"]
        assert any("gets" in e["message"] and "buffer overflow" in e["message"].lower() for e in result["errors"])

    @patch('doc_healing.llm.static_analyzer.generate_fix_with_ai', return_value=None)
    def test_detects_printf_scanf_nesting(self, _mock):
        result = analyze_c_code('printf(scanf("%d"))')
        assert result["has_issues"]
        assert any("printf(scanf())" in e["message"] for e in result["errors"])

    @patch('doc_healing.llm.static_analyzer.generate_fix_with_ai', return_value=None)
    def test_detects_missing_stdio(self, _mock):
        result = analyze_c_code('printf("hello");')
        assert result["has_issues"]
        assert any("stdio.h" in e["message"] for e in result["errors"])

    @patch('doc_healing.llm.static_analyzer.generate_fix_with_ai', return_value=None)
    def test_no_missing_stdio_when_included(self, _mock):
        result = analyze_c_code('#include <stdio.h>\nprintf("hello");')
        assert not any("stdio.h" in e["message"] for e in result["errors"])

    def test_dispatcher_routes_c(self):
        """C code goes through analyze_c_code, not analyze_generic_code."""
        result = analyze_code('printf("hello");', language="c")
        assert result["analysis_method"] == "static_c"
        assert result["detected_language"] == "c"


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

    def test_syntax_error_format(self):
        md = format_errors_markdown([{"type": "SyntaxError", "message": "bad"}])
        assert "`SyntaxError`" in md
        assert "bad" in md

    def test_reference_error_format(self):
        md = format_errors_markdown([{"type": "ReferenceError", "message": "undef"}])
        assert "`ReferenceError`" in md
        assert "undef" in md


class TestGenerateFixPython:
    """Tests for _generate_fix SyntaxError bracket fixes."""

    def test_fixes_unclosed_paren(self):
        code = "print('hello'"
        errors = [{"type": "SyntaxError", "message": "unexpected EOF while parsing", "line": 1}]
        fixed = _generate_fix(code, errors, {})
        assert fixed.count("(") == fixed.count(")")

    def test_fixes_unclosed_bracket(self):
        code = "x = [1, 2, 3"
        errors = [{"type": "SyntaxError", "message": "unexpected EOF", "line": 1}]
        fixed = _generate_fix(code, errors, {})
        assert fixed.count("[") == fixed.count("]")


class TestGenerateFixWithAI:
    """Tests for AI-powered multi-language fix generation."""

    @patch('doc_healing.llm.bedrock_client.BedrockLLMClient')
    def test_generates_fix_for_javascript(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate_correction.return_value = "console.log('hello');"
        mock_client_cls.return_value = mock_client

        errors = [{"type": "ReferenceError", "message": "'printf' is not defined in JavaScript"}]
        result = generate_fix_with_ai("printf('hello');", "javascript", errors)
        assert result is not None
        assert "console.log" in result

    @patch('doc_healing.llm.bedrock_client.BedrockLLMClient')
    def test_generates_fix_for_c_security(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate_correction.return_value = 'char buf[100];\nfgets(buf, sizeof(buf), stdin);'
        mock_client_cls.return_value = mock_client

        errors = [{"type": "SecurityWarning", "message": "unsafe scanf usage"}]
        result = generate_fix_with_ai('char buf[100];\nscanf("%s", buf);', "c", errors)
        assert result is not None
        assert "fgets" in result

    @patch('doc_healing.llm.bedrock_client.BedrockLLMClient')
    def test_returns_none_on_failure(self, mock_client_cls):
        mock_client_cls.side_effect = Exception("Bedrock unavailable")

        errors = [{"type": "SyntaxError", "message": "bad syntax"}]
        result = generate_fix_with_ai("bad code", "rust", errors)
        assert result is None

    @patch('doc_healing.llm.bedrock_client.BedrockLLMClient')
    def test_returns_none_when_fix_same_as_original(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.generate_correction.return_value = "printf('hello');"
        mock_client_cls.return_value = mock_client

        errors = [{"type": "ReferenceError", "message": "test"}]
        result = generate_fix_with_ai("printf('hello');", "javascript", errors)
        assert result is None


class TestAnalyzersReturnFixes:
    """Verify JS and generic analyzers attempt to return fixed_code."""

    @patch('doc_healing.llm.static_analyzer.generate_fix_with_ai')
    def test_js_analyzer_returns_fixed_code(self, mock_ai_fix):
        mock_ai_fix.return_value = "console.log('hello');"
        result = analyze_javascript_code("printf('hello');")
        assert result["has_issues"]
        assert result["fixed_code"] == "console.log('hello');"

    @patch('doc_healing.llm.static_analyzer.generate_fix_with_ai')
    def test_generic_analyzer_returns_fixed_code(self, mock_ai_fix):
        mock_ai_fix.return_value = "puts 'hello'"
        result = analyze_generic_code("ptf('hello')", language="ruby")
        assert result["has_issues"]
        assert result["fixed_code"] == "puts 'hello'"

    @patch('doc_healing.llm.static_analyzer.generate_fix_with_ai')
    def test_no_fix_when_no_errors(self, mock_ai_fix):
        result = analyze_javascript_code("const x = 42;")
        assert not result["has_issues"]
        assert result["fixed_code"] is None
        mock_ai_fix.assert_not_called()
