"""Worker task implementations for webhook, validation, and healing.

This module contains the actual task functions that are enqueued and processed
by the unified worker. These tasks use the queue abstraction layer to work
with both Redis and in-memory queue backends.
"""

import logging
import base64
from typing import Any, Dict, Optional

from doc_healing.queue.factory import get_queue_backend
from doc_healing.llm.bedrock_client import BedrockLLMClient
from doc_healing.llm.prompts import (
    build_healing_prompt, HEALING_SYSTEM_PROMPT,
    MULTILANG_FIX_SYSTEM_PROMPT, build_retry_fix_prompt,
)
from doc_healing.llm.static_analyzer import (
    analyze_python_code, analyze_code, detect_language,
    format_errors_markdown,
)
from doc_healing.llm.sandbox import execute_code

logger = logging.getLogger(__name__)


def process_github_webhook(payload: Dict[str, Any]) -> None:
    """Process a GitHub webhook event: analyze PR diffs and post healing comments."""
    logger.info("Processing GitHub webhook")
    
    import httpx
    from doc_healing.config import get_settings
    import re
    
    if not isinstance(payload, dict):
        raise ValueError("Webhook payload must be a dictionary")
    
    action = payload.get("action")
    pull_request = payload.get("pull_request")
    
    if action not in ["opened", "synchronize", "reopened"] or not pull_request:
        logger.info("GitHub webhook processed successfully")
        return
    
    pr_number = pull_request.get("number")
    repo_full_name = payload.get("repository", {}).get("full_name")
    issue_url = pull_request.get("issue_url")
    comments_url = issue_url + "/comments" if issue_url else None
    pr_title = pull_request.get("title", "Untitled")
    head_sha = pull_request.get("head", {}).get("sha")
    pr_url = pull_request.get("html_url", "")
    
    logger.info(f"Processing PR #{pr_number} '{pr_title}' for {repo_full_name}")
    
    settings = get_settings()
    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.github_token:
        headers["Authorization"] = f"token {settings.github_token}"
        logger.info("GitHub token is configured")
    else:
        logger.warning("No GITHUB_TOKEN found in settings!")
        return
    
    if not (head_sha and repo_full_name and comments_url):
        logger.warning("Missing head_sha, repo_full_name, or comments_url")
        return
    
    # Headers needed for Check Runs API
    headers["Accept"] = "application/vnd.github.v3+json"
    
    with httpx.Client(timeout=30.0) as client:
        # Step 0: Create Check Run (In Progress)
        check_run_id = None
        try:
            check_run_payload = {
                "name": "OASIS Code Analysis",
                "head_sha": head_sha,
                "status": "in_progress",
                "started_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
            }
            checks_url = f"https://api.github.com/repos/{repo_full_name}/check-runs"
            checks_resp = client.post(checks_url, json=check_run_payload, headers=headers)
            if checks_resp.status_code == 201:
                check_run_id = checks_resp.json().get("id")
                logger.info(f"Created GitHub check run {check_run_id}")
            else:
                logger.warning(f"Failed to create check run: {checks_resp.status_code} {checks_resp.text}")
        except Exception as e:
            logger.error(f"Error creating check run: {e}")
    
    DOC_EXTENSIONS = {".md", ".rst", ".txt", ".mdx"}
    SUPPORTED_LANGS = {"python", "javascript", "js", "java", "bash", "sh", "typescript", "ts",
                       "go", "ruby", "rust", "c", "cpp", "csharp", "cs", "php", "sql", "yaml", "json", "html", "css"}
    
    with httpx.Client(timeout=30.0) as client:
        # Step 1: Get changed files via GitHub PR Files API
        files_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/files"
        files_resp = client.get(files_url, headers=headers)
        
        if files_resp.status_code != 200:
            logger.error(f"Failed to fetch PR files: {files_resp.status_code}")
            return
        
        changed_files = files_resp.json()
        logger.info(f"PR #{pr_number} has {len(changed_files)} changed file(s)")
        
        # Categorize files
        doc_files = []
        code_files = []
        other_files = []
        for f in changed_files:
            fname = f.get("filename", "")
            if any(fname.endswith(ext) for ext in DOC_EXTENSIONS):
                doc_files.append(f)
            elif any(fname.endswith(ext) for ext in [".py", ".js", ".ts", ".java", ".go", ".rb", ".rs", ".c", ".cpp", ".php"]):
                code_files.append(f)
            else:
                other_files.append(f)
        
        # Step 2: Build PR summary
        file_summary_parts = []
        if doc_files:
            file_summary_parts.append(f"{len(doc_files)} documentation")
        if code_files:
            file_summary_parts.append(f"{len(code_files)} code")
        if other_files:
            file_summary_parts.append(f"{len(other_files)} other")
        file_summary_str = ", ".join(file_summary_parts) + f" file{'s' if len(changed_files) != 1 else ''} changed"
        
        summary_lines = [
            f"## OASIS — Code Analysis Report\n",
            f"**PR #{pr_number}** · {file_summary_str}\n",
            "---",
            "",
        ]
        
        all_listed_files = doc_files + code_files
        if all_listed_files:
            summary_lines.append("### Changed Files")
            summary_lines.append("| File | Type | Status | Changes |")
            summary_lines.append("|------|------|--------|---------|")
            for f in all_listed_files:
                fname = f['filename']
                fstatus = f.get('status', 'modified')
                ftype = "doc" if f in doc_files else "code"
                changes = f"+{f.get('additions', 0)} / -{f.get('deletions', 0)}"
                summary_lines.append(f"| `{fname}` | {ftype} | {fstatus} | {changes} |")
            summary_lines.append("")
        
        # Step 3: For each doc file, fetch content, extract code blocks, and heal
        all_snippets = []
        
        for doc_file in doc_files:
            fname = doc_file.get("filename", "")
            status = doc_file.get("status", "")
            
            if status == "removed":
                continue
            
            raw_url = f"https://raw.githubusercontent.com/{repo_full_name}/{head_sha}/{fname}"
            doc_resp = client.get(raw_url)
            
            if doc_resp.status_code != 200:
                logger.warning(f"Could not fetch {fname}: {doc_resp.status_code}")
                continue
            
            content = doc_resp.text.replace('\r\n', '\n')
            
            # Extract fenced code blocks — WITH or WITHOUT a language tag
            # Pattern 1: ```language\n...\n``` (tagged blocks)
            pattern_tagged = r'```(\w+)\s*\n(.*?)(?:\n```|$)'
            # Pattern 2: ```\n...\n``` (untagged blocks)
            pattern_untagged = r'```\s*\n(.*?)(?:\n```|$)'
            
            tagged_matches = re.findall(pattern_tagged, content, re.DOTALL)
            for lang, code in tagged_matches:
                code = code.strip()
                if not code or lang.lower() not in SUPPORTED_LANGS:
                    continue
                all_snippets.append({"file": fname, "lang": lang.lower(), "code": code})
            
            # For untagged blocks, auto-detect the language
            untagged_matches = re.findall(pattern_untagged, content, re.DOTALL)
            # Remove any that were already captured by the tagged regex
            tagged_code_set = {code.strip() for _, code in tagged_matches}
            for code in untagged_matches:
                code = code.strip()
                if not code or code in tagged_code_set:
                    continue
                detected_lang = detect_language(code)
                logger.info(f"Auto-detected language '{detected_lang}' for untagged block in {fname}")
                all_snippets.append({"file": fname, "lang": detected_lang, "code": code})
            
            # Also scan the diff patch for code-like lines NOT in any fenced block
            patch = doc_file.get("patch", "")
            if patch:
                added_lines = []
                for line in patch.split("\n"):
                    if line.startswith("+") and not line.startswith("+++"):
                        added_lines.append(line[1:])
                
                if added_lines:
                    # Filter out markdown and blank lines to find raw code
                    code_like_lines = []
                    for line in added_lines:
                        stripped = line.strip()
                        # Skip empty, markdown headings, markdown list items, markdown links, etc.
                        if (not stripped or stripped.startswith("#") or 
                            stripped.startswith("```") or stripped.startswith("-") or
                            stripped.startswith("*") or stripped.startswith(">") or
                            stripped.startswith("|") or stripped.startswith("!")):
                            continue
                        # Lines that look like code: contain parens, semicolons, braces, or assignment
                        if re.search(r'[();{}=]', stripped):
                            code_like_lines.append(stripped)
                    
                    if code_like_lines:
                        raw_code = "\n".join(code_like_lines)
                        detected_lang = detect_language(raw_code)
                        logger.info(f"Found {len(code_like_lines)} code-like line(s) in diff of {fname}, detected as '{detected_lang}'")
                        all_snippets.append({"file": fname, "lang": detected_lang, "code": raw_code, "from_diff": True})
        
        logger.info(f"Found {len(all_snippets)} code snippet(s) across {len(doc_files)} documentation file(s)")
        
        # Build language statistics for summary
        lang_counts = {}
        for snippet in all_snippets:
            lang = snippet["lang"]
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        if lang_counts:
            lang_stats = ", ".join(f"{count}× {lang.capitalize()}" for lang, count in sorted(lang_counts.items()))
            summary_lines.append(f"🔍 **Analyzed:** {lang_stats}")
            summary_lines.append("")
        
        # Store data needed for auto-commits
        fixes_to_commit = []
        head_branch = payload.get("pull_request", {}).get("head", {}).get("ref")
        
        # Step 4: Heal snippets
        snippet_results = []
        for idx, snippet in enumerate(all_snippets):
            code = snippet["code"]
            lang = snippet["lang"]
            fname = snippet["file"]
            
            logger.info(f"Analyzing snippet {idx} ({lang}) from {fname}")
            
            try:
                result = heal_code_snippet(
                    fname, f"snippet-{idx}", code, lang,
                    ["Please review this code snippet for bugs, missing arguments, type errors, or syntax issues."]
                )
                
                healed = result.get("healed", False)
                healed_code = result.get("healed_code", "")
                static_errors = result.get("static_errors", [])
                changes = result.get("changes", [])
                
                # Build error details
                error_detail = ""
                if static_errors:
                    error_detail = "\n\n**Detected issues:**\n"
                    for e in static_errors:
                        error_detail += f"- `{e['type']}` — {e['message']}\n"
                
                method = ""
                if changes:
                    method = "\n\n<sub>" + " · ".join(changes) + "</sub>"
                
                if healed and healed_code and healed_code.strip() != code.strip():
                    # Queue for auto-commit if we have a branch
                    if head_branch:
                        # Build descriptive info for commit msg
                        fix_desc_parts = []
                        for e in static_errors[:2]:  # First 2 errors for brevity
                            fix_desc_parts.append(e.get("type", "issue"))
                        fix_desc = ", ".join(fix_desc_parts) if fix_desc_parts else "code issues"
                        
                        fixes_to_commit.append({
                            "file": fname,
                            "old_code": code,
                            "new_code": healed_code.rstrip(),
                            "fix_description": fix_desc,
                        })
                    
                    # Build diff display
                    diff_lines = []
                    old_lines = code.strip().split("\n")
                    new_lines = healed_code.strip().split("\n")
                    for ol in old_lines:
                        if ol not in new_lines:
                            diff_lines.append(f"- {ol}")
                    for nl in new_lines:
                        if nl not in old_lines:
                            diff_lines.append(f"+ {nl}")
                    
                    if diff_lines:
                        diff_block = "\n".join(diff_lines)
                        fix_display = (
                            f"**Suggested fix:**\n```diff\n{diff_block}\n```\n\n"
                            f"<details><summary>Full corrected code</summary>\n\n"
                            f"```{lang}\n{healed_code.strip()}\n```\n</details>"
                        )
                    else:
                        fix_display = f"**Suggested fix:**\n```{lang}\n{healed_code.strip()}\n```"
                    
                    # Confidence badge
                    confidence = result.get("confidence", 0.0)
                    badge = "✅" if confidence >= 0.90 else "⚠️" if confidence >= 0.60 else "🔍"
                    conf_pct = int(confidence * 100)
                    
                    snippet_results.append(
                        f"#### `{fname}` — Issues Found {badge}\n"
                        f"**Language:** `{lang}` · **Confidence:** {conf_pct}%\n\n"
                        f"```{lang}\n{code}\n```"
                        f"{error_detail}\n\n"
                        f"{fix_display}"
                        f"{method}"
                    )
                elif static_errors:
                    snippet_results.append(
                        f"#### `{fname}` — Issues Found\n"
                        f"**Language:** `{lang}`\n\n"
                        f"```{lang}\n{code}\n```"
                        f"{error_detail}"
                    )
                else:
                    snippet_results.append(
                        f"#### `{fname}` — Snippet #{idx + 1} ✓\n"
                        f"No issues detected."
                    )
            except Exception as e:
                logger.error(f"Error healing snippet {idx}: {e}")
                snippet_results.append(
                    f"#### `{fname}` — Snippet #{idx + 1}\n"
                    f"```{lang}\n{code}\n```\n"
                    f"Could not analyze: `{str(e)[:80]}`"
                )
        
        # Step 4.5: Auto-commit all healed snippets
        if fixes_to_commit:
            logger.info(f"Applying {len(fixes_to_commit)} auto-commit fixes...")
            for fix in fixes_to_commit:
                try:
                    # 1. Get current file content and SHA
                    file_url = f"https://api.github.com/repos/{repo_full_name}/contents/{fix['file']}?ref={head_branch}"
                    file_resp = client.get(file_url, headers=headers)
                    if file_resp.status_code != 200:
                        logger.error(f"Failed to get file contents for {fix['file']}")
                        continue
                    
                    file_data = file_resp.json()
                    file_sha = file_data["sha"]
                    content_b64 = file_data["content"]
                    current_content = base64.b64decode(content_b64).decode("utf-8")
                    
                    # 2. Apply fix (simple string replacement)
                    if fix['old_code'] in current_content:
                        new_content = current_content.replace(fix['old_code'], fix['new_code'])
                        
                        # Only commit if we actually changed something
                        if new_content != current_content:
                            logger.info(f"Committing fix for {fix['file']}")
                            commit_payload = {
                                "message": f"🤖 OASIS: Fixed {fix.get('fix_description', 'code issues')} in {fix['file']}",
                                "content": base64.b64encode(new_content.encode("utf-8")).decode("utf-8"),
                                "sha": file_sha,
                                "branch": head_branch
                            }
                            commit_resp = client.put(file_url, json=commit_payload, headers=headers)
                            if commit_resp.status_code in (200, 201):
                                logger.info(f"Successfully committed fix to {fix['file']}")
                                snippet_results.append(f"✅ **Auto-committed fix** for `{fix['file']}` directly to this branch!")
                            else:
                                logger.error(f"Failed to commit fix: {commit_resp.text}")
                    else:
                        logger.warning(f"Could not find exact original code block in {fix['file']} to replace")
                except Exception as e:
                    logger.error(f"Error during auto-commit for {fix['file']}: {e}")
        
        # Step 4b: Analyze changed code files directly
        for code_file in code_files:
            fname = code_file.get("filename", "")
            status = code_file.get("status", "")
            patch = code_file.get("patch", "")
            
            if status == "removed" or not patch:
                continue
            
            # Extract only added lines from the diff
            added_lines = []
            for line in patch.split("\n"):
                if line.startswith("+") and not line.startswith("+++"):
                    added_lines.append(line[1:])  # strip the leading +
            
            if not added_lines:
                continue
            
            added_code = "\n".join(added_lines).strip()
            if len(added_code) < 10:
                continue
            
            # Detect language from extension
            ext_lang_map = {
                ".py": "python", ".js": "javascript", ".ts": "typescript",
                ".java": "java", ".go": "go", ".rb": "ruby", ".rs": "rust",
                ".c": "c", ".cpp": "cpp", ".php": "php"
            }
            lang = "python"
            for ext, l in ext_lang_map.items():
                if fname.endswith(ext):
                    lang = l
                    break
            
            logger.info(f"Analyzing code file {fname} ({lang}, {len(added_lines)} new lines)")
            
            try:
                result = heal_code_snippet(
                    fname, f"file-{fname}", added_code, lang,
                    ["Review the newly added code for bugs, logic errors, missing error handling, or potential issues."]
                )
                
                healed = result.get("healed", False)
                healed_code = result.get("healed_code", "")
                
                if healed and healed_code and healed_code.strip() != added_code.strip():
                    snippet_results.append(
                        f"#### `{fname}` — Issues Found\n\n"
                        f"**New code added:**\n```{lang}\n{added_code[:500]}\n```\n\n"
                        f"**Suggested fix:**\n```{lang}\n{healed_code.strip()[:500]}\n```"
                    )
                else:
                    snippet_results.append(
                        f"#### `{fname}` — New code looks good ✓"
                    )
            except Exception as e:
                logger.error(f"Error analyzing code file {fname}: {e}")
        
        # Step 5: Build and post comment (with duplicate detection)
        summary_lines.append("---")
        summary_lines.append("")
        if snippet_results:
            summary_lines.append("### Analysis Results")
            summary_lines.append("")
            summary_lines.extend(snippet_results)
        else:
            if doc_files or code_files:
                summary_lines.append("### Analysis Results\n")
                summary_lines.append("All code looks good — no issues found. ✓\n")
            else:
                summary_lines.append("No documentation or code files were modified in this PR.\n")
        
        # Add branded footer
        summary_lines.append("")
        summary_lines.append("---")
        summary_lines.append("<sub>🏜️ OASIS · Self-Healing Documentation Engine · Powered by Amazon Bedrock</sub>")
        
        comment_body = "\n".join(summary_lines)
        
        # Fix #2: Check for existing bot comment and update it instead of creating a duplicate
        BOT_SIGNATURE = "OASIS — Code Analysis Report"
        existing_comment_id = None
        
        existing_comments_resp = client.get(comments_url, headers=headers)
        if existing_comments_resp.status_code == 200:
            for comment in existing_comments_resp.json():
                if BOT_SIGNATURE in comment.get("body", ""):
                    existing_comment_id = comment.get("id")
                    break
        
        if existing_comment_id:
            # PATCH existing comment
            patch_url = f"https://api.github.com/repos/{repo_full_name}/issues/comments/{existing_comment_id}"
            logger.info(f"Updating existing comment {existing_comment_id}")
            post_resp = client.patch(patch_url, json={"body": comment_body}, headers=headers)
        else:
            # POST new comment
            logger.info(f"Posting new comment to {comments_url}")
            post_resp = client.post(comments_url, json={"body": comment_body}, headers=headers)
        
        logger.info(f"GitHub API response: {post_resp.status_code}")
        
        # Step 6: Update Check Run (Completed)
        if check_run_id:
            try:
                # If there are any "Issues Found" in snippet_results, checking if we auto-fixed them all
                has_unfixed_errors = any("Issues Found" in res and "Auto-committed fix" not in res for res in snippet_results)
                
                conclusion = "failure" if has_unfixed_errors else "success"
                check_run_payload = {
                    "status": "completed",
                    "conclusion": conclusion,
                    "completed_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                    "output": {
                        "title": "Analysis Completed",
                        "summary": f"{file_summary_str}. {'Found issues.' if has_unfixed_errors else 'Everything looks good.'}",
                        "text": comment_body
                    }
                }
                checks_url = f"https://api.github.com/repos/{repo_full_name}/check-runs/{check_run_id}"
                client.patch(checks_url, json=check_run_payload, headers=headers)
                logger.info(f"Updated GitHub check run {check_run_id} to {conclusion}")
            except Exception as e:
                logger.error(f"Error updating check run {check_run_id}: {e}")
    
    logger.info("GitHub webhook processed successfully")



def process_gitlab_webhook(payload: Dict[str, Any]) -> None:
    """Process a GitLab webhook event."""
    logger.info("Processing GitLab webhook")
    
    if not isinstance(payload, dict):
        raise ValueError("Webhook payload must be a dictionary")
    
    event_type = payload.get("object_kind")
    project = payload.get("project", {})
    project_name = project.get("path_with_namespace", "unknown")
    
    if not event_type:
        logger.warning("Webhook payload missing object_kind")
    
    logger.info(f"GitLab event: {event_type} for project: {project_name}")
    
    if event_type in ["push", "merge_request"]:
        commits = payload.get("commits", [])
        changed_files = []
        for commit in commits[:5]:
            added = commit.get("added", [])
            modified = commit.get("modified", [])
            for fp in added + modified:
                if fp.endswith((".md", ".rst", ".txt")):
                    changed_files.append(fp)
        
        logger.info(f"Found {len(changed_files)} documentation file(s) to validate")
        # File content would be fetched via GitLab API in production
    
    logger.info("GitLab webhook processed successfully")


def validate_code_snippet(
    file_path: str,
    snippet_id: str,
    code: str,
    language: str
) -> Dict[str, Any]:
    """Validate a code snippet from documentation.
    
    This task validates a code snippet by attempting to compile/execute it
    in an isolated environment. It returns validation results including
    any errors or warnings found.
    
    Args:
        file_path: Path to the documentation file containing the snippet
        snippet_id: Unique identifier for the code snippet
        code: The code snippet to validate
        language: Programming language of the snippet
        
    Returns:
        Dictionary containing validation results with keys:
        - valid: Boolean indicating if the code is valid
        - errors: List of error messages (if any)
        - warnings: List of warning messages (if any)
        
    Raises:
        ValueError: If required parameters are missing or invalid
    """
    logger.info(f"Validating code snippet {snippet_id} from {file_path}")
    logger.debug(f"Language: {language}, Code length: {len(code)} chars")
    
    # Validate inputs
    if not file_path or not snippet_id or not code or not language:
        raise ValueError("All parameters (file_path, snippet_id, code, language) are required")
    
    errors = []
    warnings = []
    
    # Step 1: Static analysis (all languages)
    analysis = analyze_code(code, language)
    if analysis["has_issues"]:
        for e in analysis["errors"]:
            errors.append(f"{e['type']}: {e['message']}")
    
    # Step 2: Sandbox execution (Python only, other languages skip gracefully)
    sandbox_result = execute_code(code, language)
    if not sandbox_result.get("skipped"):
        if not sandbox_result["success"]:
            err_type = sandbox_result.get("error_type", "RuntimeError")
            err_msg = sandbox_result.get("error_message", "Unknown execution error")
            error_str = f"{err_type}: {err_msg}"
            if error_str not in errors:
                errors.append(error_str)
            if sandbox_result.get("timed_out"):
                warnings.append("Code execution timed out — possible infinite loop")
        else:
            logger.info(f"Sandbox execution succeeded for {snippet_id}")
    else:
        warnings.append(f"Sandbox execution not available for {language} — validated with static analysis only")
    
    valid = len(errors) == 0
    
    # Step 3: If validation fails, enqueue healing
    if not valid:
        queue = get_queue_backend()
        try:
            queue.enqueue("healing", heal_code_snippet,
                         file_path, snippet_id, code, language, errors)
            logger.info(f"Enqueued healing task for {snippet_id}")
        except Exception as e:
            logger.warning(f"Could not enqueue healing for {snippet_id}: {e}")
    
    result = {
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "snippet_id": snippet_id,
        "file_path": file_path,
        "language": language,
        "sandbox_executed": not sandbox_result.get("skipped", True),
    }
    
    logger.info(f"Code snippet {snippet_id} validation complete: valid={valid}, errors={len(errors)}")
    return result


def validate_documentation_file(file_path: str, content: str) -> Dict[str, Any]:
    """Validate all code snippets in a documentation file."""
    import re
    import hashlib
    
    logger.info(f"Validating documentation file: {file_path}")
    
    if not file_path or not content:
        raise ValueError("Both file_path and content are required")
    
    # Extract triple-backtick code blocks: ```language\n<code>\n```
    pattern = re.compile(r"```(\w+)?\n(.*?)\n```", re.DOTALL)
    matches = pattern.findall(content)
    
    queue = get_queue_backend()
    snippets_found = len(matches)
    
    for i, (lang, code) in enumerate(matches):
        lang = lang.strip() if lang else "unknown"
        content_hash = hashlib.md5(code.encode()).hexdigest()[:8]
        snippet_id = f"snippet-{i}-{content_hash}"
        
        logger.info(f"Enqueuing validation for {snippet_id} ({lang}) from {file_path}")
        queue.enqueue("validation", validate_code_snippet, file_path, snippet_id, code, lang)
    
    result = {
        "file_path": file_path,
        "snippets_found": snippets_found,
        "status": "enqueued",
    }
    
    logger.info(f"Documentation file {file_path}: {snippets_found} snippets enqueued")
    return result


def _validate_and_retry_fix(
    original_code: str,
    ai_fix: str,
    language: str,
    max_retries: int = 2,
) -> Optional[str]:
    """Validate an AI-generated fix by re-running static analysis.
    
    If the fix still has issues, send error feedback back to Bedrock
    and retry up to max_retries times.
    
    Returns the validated fix, or None if all retries fail.
    """
    current_fix = ai_fix
    
    for attempt in range(1, max_retries + 1):
        # Re-run static analysis on the fix
        validation = analyze_code(current_fix, language)
        
        if not validation["has_issues"]:
            logger.info(f"AI fix validated successfully (attempt {attempt})")
            return current_fix
        
        # Fix still has issues — retry with error feedback
        error_feedback = "; ".join(e["message"] for e in validation["errors"])
        logger.info(
            f"AI fix still has {len(validation['errors'])} issue(s) on attempt {attempt}, "
            f"retrying with feedback: {error_feedback[:100]}"
        )
        
        try:
            retry_prompt = build_retry_fix_prompt(
                original_code=original_code,
                previous_fix=current_fix,
                language=language,
                validation_errors=error_feedback,
            )
            client = BedrockLLMClient()
            new_fix = client.generate_correction(
                prompt=retry_prompt,
                system_prompt=MULTILANG_FIX_SYSTEM_PROMPT,
            )
            
            if new_fix and new_fix.strip() and new_fix.strip() != original_code.strip():
                current_fix = new_fix.strip()
            else:
                logger.warning(f"Bedrock returned empty/identical fix on retry {attempt}")
                break
        except Exception as e:
            logger.warning(f"Bedrock retry {attempt} failed: {str(e)[:100]}")
            break
    
    # Final validation check
    final_check = analyze_code(current_fix, language)
    if not final_check["has_issues"]:
        return current_fix
    
    logger.warning(f"AI fix validation failed after {max_retries} retries")
    return None


def heal_code_snippet(
    file_path: str,
    snippet_id: str,
    code: str,
    language: str,
    errors: list
) -> Dict[str, Any]:
    """Heal a code snippet using sandbox execution + static analysis + Bedrock AI.
    
    Uses a three-layer approach:
    1. Sandbox execution (Python) — catches runtime errors the static analyzer misses
    2. Static analysis (ast/compile) for reliable bug detection
    3. Amazon Bedrock AI for complex code that needs deeper understanding
    """
    logger.info(f"Healing code snippet {snippet_id} from {file_path}")
    
    if not file_path or not snippet_id or not code or not language:
        raise ValueError("All parameters (file_path, snippet_id, code, language) are required")
    
    changes = []
    healed_code = None
    confidence = 0.0
    detected_errors = []
    
    # Step 1: Sandbox execution (catches runtime errors for Python)
    sandbox_result = execute_code(code, language)
    sandbox_errors = []
    if not sandbox_result.get("skipped") and not sandbox_result["success"]:
        err_type = sandbox_result.get("error_type", "RuntimeError")
        err_msg = sandbox_result.get("error_message", "Unknown error")
        sandbox_errors.append({
            "type": err_type,
            "message": err_msg,
            "line": None,
            "detail": f"Runtime execution error: {err_msg}",
            "source": "sandbox",
        })
        logger.info(f"Sandbox caught {err_type} in {snippet_id}: {err_msg}")
    
    # Step 2: Static analysis (works for all languages, no external dependency)
    logger.info(f"Running static analysis on {snippet_id} (language: {language})")
    analysis = analyze_code(code, language)
    
    if analysis["has_issues"]:
        detected_errors = analysis["errors"]
        method_name = analysis.get("analysis_method", "static")
        logger.info(f"Static analysis ({method_name}) found {len(detected_errors)} issue(s) in {snippet_id}")
        
        if analysis.get("fixed_code"):
            healed_code = analysis["fixed_code"]
            changes.append(f"Fixed issues via static analysis ({method_name})")
            confidence = 0.75
    
    # Merge sandbox errors into detected_errors (avoid duplicates)
    for se in sandbox_errors:
        if not any(e["type"] == se["type"] and e["message"] == se["message"] for e in detected_errors):
            detected_errors.append(se)
    
    # Step 3: Bedrock AI — always try for complex code or when static analysis isn't enough
    # The AI handles: logic errors, complex type mismatches, algorithm bugs,
    # missing edge cases, and cross-language issues that static analysis can't catch.
    use_ai = True  # Always attempt AI — it gracefully fails if unavailable
    
    if use_ai:
        try:
            # Build rich context for the LLM including all error sources
            error_context = str(errors) if errors else "No explicit errors provided."
            
            if detected_errors:
                error_context += "\n\nStatic analysis found: " + "; ".join(
                    e["message"] for e in detected_errors
                )
            
            if sandbox_errors:
                error_context += "\n\nRuntime execution errors: " + "; ".join(
                    f"{e['type']}: {e['message']}" for e in sandbox_errors
                )
            
            # If no errors found by static analysis, ask AI for deeper review
            if not detected_errors and not sandbox_errors:
                error_context += (
                    "\n\nNo obvious errors detected by static analysis. "
                    "Please review for logic errors, edge cases, performance issues, "
                    "best practice violations, or subtle bugs."
                )
            
            client = BedrockLLMClient()
            prompt = build_healing_prompt(original_code=code, error_log=error_context, language=language)
            ai_code = client.generate_correction(prompt=prompt, system_prompt=HEALING_SYSTEM_PROMPT)
            
            if ai_code and ai_code.strip() != code.strip():
                # Validate AI fix via retry loop (defects 1.1-1.3)
                validated_fix = _validate_and_retry_fix(
                    original_code=code,
                    ai_fix=ai_code.strip(),
                    language=language,
                    max_retries=2,
                )
                
                if validated_fix:
                    healed_code = validated_fix
                    changes.append("Enhanced fix using Claude 3 via Amazon Bedrock (validated)")
                    confidence = 0.95
                    logger.info(f"Bedrock AI provided validated fix for {snippet_id}")
                else:
                    # AI fix failed validation — still use it but lower confidence
                    healed_code = ai_code.strip()
                    changes.append("Fix via Claude 3 (auto-fix validation failed — review recommended)")
                    confidence = 0.60
                    logger.warning(f"Bedrock AI fix for {snippet_id} could not be validated")
        except Exception as e:
            logger.warning(f"Bedrock AI unavailable for {snippet_id}: {str(e)[:100]}")
            # Static analysis + sandbox results are still used
    
    # Build result
    healed = bool(healed_code and healed_code.strip() != code.strip())
    
    result = {
        "healed": healed,
        "healed_code": healed_code if healed else None,
        "changes": changes if healed else [],
        "confidence": confidence if healed else 0.0,
        "snippet_id": snippet_id,
        "file_path": file_path,
        "static_errors": detected_errors,
        "sandbox_executed": not sandbox_result.get("skipped", True),
    }
    
    logger.info(f"Code snippet {snippet_id} healing complete: healed={healed}, errors_found={len(detected_errors)}")
    return result


def heal_documentation_file(
    file_path: str,
    validation_results: Dict[str, Any]
) -> Dict[str, Any]:
    """Heal all invalid code snippets in a documentation file."""
    logger.info(f"Healing documentation file: {file_path}")
    
    if not file_path or not validation_results:
        raise ValueError("Both file_path and validation_results are required")
    
    queue = get_queue_backend()
    snippets_healed = 0
    snippets_failed = 0
    
    invalid_snippets = validation_results.get("invalid_snippets", [])
    for snippet in invalid_snippets:
        snippet_id = snippet.get("snippet_id", "unknown")
        code = snippet.get("code", "")
        language = snippet.get("language", "unknown")
        errors = snippet.get("errors", [])
        
        if code:
            queue.enqueue("healing", heal_code_snippet,
                         file_path, snippet_id, code, language, errors)
            snippets_healed += 1
            logger.info(f"Enqueued healing for {snippet_id}")
        else:
            snippets_failed += 1
    
    result = {
        "file_path": file_path,
        "snippets_healed": snippets_healed,
        "snippets_failed": snippets_failed,
        "pull_request_url": None,
    }
    
    logger.info(f"Documentation file healing: {snippets_healed} healed, {snippets_failed} failed")
    return result

