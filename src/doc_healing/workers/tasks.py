"""Worker task implementations for webhook, validation, and healing.

This module contains the actual task functions that are enqueued and processed
by the unified worker. These tasks use the queue abstraction layer to work
with both Redis and in-memory queue backends.
"""

import logging
from typing import Any, Dict, Optional

from doc_healing.queue.factory import get_queue_backend
from doc_healing.llm.bedrock_client import BedrockLLMClient
from doc_healing.llm.prompts import build_healing_prompt, HEALING_SYSTEM_PROMPT

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
        summary_lines = [
            f"🤖 **Self-Healing Documentation Engine** analyzed PR #{pr_number}\n",
            f"### 📊 PR Summary",
            f"| Category | Count |",
            f"|---|---|",
            f"| 📝 Documentation files | {len(doc_files)} |",
            f"| 💻 Code files | {len(code_files)} |",
            f"| 📁 Other files | {len(other_files)} |",
            f"| **Total changed** | **{len(changed_files)}** |",
            "",
        ]
        
        if doc_files:
            summary_lines.append("### 📝 Changed Documentation Files")
            for f in doc_files:
                status_icon = {"added": "🆕", "modified": "✏️", "removed": "🗑️"}.get(f.get("status", ""), "📄")
                summary_lines.append(f"- {status_icon} `{f['filename']}` (+{f.get('additions', 0)}/-{f.get('deletions', 0)})")
            summary_lines.append("")
        
        if code_files:
            summary_lines.append("### 💻 Changed Code Files")
            for f in code_files:
                status_icon = {"added": "🆕", "modified": "✏️", "removed": "🗑️"}.get(f.get("status", ""), "📄")
                summary_lines.append(f"- {status_icon} `{f['filename']}` (+{f.get('additions', 0)}/-{f.get('deletions', 0)})")
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
            
            # Extract code blocks with any language tag
            pattern = r'```(\w+)\s*\n(.*?)(?:\n```|$)'
            matches = re.findall(pattern, content, re.DOTALL)
            
            for lang, code in matches:
                code = code.strip()
                if not code or lang.lower() not in SUPPORTED_LANGS:
                    continue
                all_snippets.append({"file": fname, "lang": lang.lower(), "code": code})
        
        logger.info(f"Found {len(all_snippets)} code snippet(s) across {len(doc_files)} documentation file(s)")
        
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
                
                if healed and healed_code and healed_code.strip() != code.strip():
                    snippet_results.append(
                        f"### 🔧 Issue found in `{fname}` ({lang})\n\n"
                        f"**Original code:**\n```{lang}\n{code}\n```\n\n"
                        f"**✨ Suggested fix:**\n```{lang}\n{healed_code.strip()}\n```"
                    )
                else:
                    snippet_results.append(
                        f"### ✅ `{fname}` — Snippet #{idx + 1} ({lang})\n"
                        f"```{lang}\n{code}\n```\n"
                        f"No issues detected."
                    )
            except Exception as e:
                logger.error(f"Error healing snippet {idx}: {e}")
                snippet_results.append(
                    f"### ⚠️ `{fname}` — Snippet #{idx + 1} ({lang})\n"
                    f"```{lang}\n{code}\n```\n"
                    f"Could not analyze: `{str(e)[:80]}`"
                )
        
        # Step 5: Build and post comment
        if snippet_results:
            summary_lines.append("### 🔬 Code Snippet Analysis")
            summary_lines.append("")
            summary_lines.extend(snippet_results)
        else:
            if doc_files:
                summary_lines.append("### 🔬 Code Snippet Analysis\n")
                summary_lines.append("No code snippets found in the changed documentation files.\n")
            else:
                summary_lines.append("ℹ️ No documentation files were modified in this PR.\n")
        
        comment_body = "\n".join(summary_lines)
        
        logger.info(f"Posting comment to {comments_url}")
        post_resp = client.post(comments_url, json={"body": comment_body}, headers=headers)
        logger.info(f"GitHub API response: {post_resp.status_code}")
    
    logger.info("GitHub webhook processed successfully")



def process_gitlab_webhook(payload: Dict[str, Any]) -> None:
    """Process a GitLab webhook event.
    
    This task handles incoming GitLab webhook events, similar to GitHub
    webhook processing but adapted for GitLab's webhook format.
    
    Args:
        payload: The webhook payload from GitLab
        
    Raises:
        ValueError: If the payload is invalid or missing required fields
    """
    logger.info("Processing GitLab webhook")
    logger.debug(f"Webhook payload: {payload}")
    
    # Validate payload structure
    if not isinstance(payload, dict):
        raise ValueError("Webhook payload must be a dictionary")
    
    # Extract event type
    event_type = payload.get("object_kind")
    if not event_type:
        logger.warning("Webhook payload missing object_kind")
    
    # Process based on event type
    logger.info(f"Processing webhook event type: {event_type}")
    
    # Get queue backend for enqueuing validation tasks
    queue = get_queue_backend()
    
    # TODO: Implement actual webhook processing logic
    # This would typically:
    # 1. Parse the webhook payload
    # 2. Identify affected documentation files
    # 3. Enqueue validation tasks for those files
    #
    # Example:
    # for file_path, content in affected_files:
    #     queue.enqueue("validation", validate_documentation_file, file_path, content)
    
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
    
    # Get queue backend for enqueuing healing tasks if validation fails
    queue = get_queue_backend()
    
    # TODO: Implement actual validation logic
    # This would typically:
    # 1. Set up an isolated execution environment
    # 2. Attempt to compile/execute the code
    # 3. Capture any errors or warnings
    # 4. Return structured validation results
    # 5. If validation fails, enqueue healing task:
    #    queue.enqueue("healing", heal_code_snippet, file_path, snippet_id, code, language, errors)
    
    # Placeholder result
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "snippet_id": snippet_id,
        "file_path": file_path,
        "language": language,
    }
    
    logger.info(f"Code snippet {snippet_id} validation complete: valid={result['valid']}")
    return result


def validate_documentation_file(file_path: str, content: str) -> Dict[str, Any]:
    """Validate all code snippets in a documentation file.
    
    This task extracts and validates all code snippets from a documentation
    file, returning aggregated validation results.
    
    Args:
        file_path: Path to the documentation file
        content: Content of the documentation file
        
    Returns:
        Dictionary containing validation results for all snippets
        
    Raises:
        ValueError: If required parameters are missing
    """
    logger.info(f"Validating documentation file: {file_path}")
    
    # Validate inputs
    if not file_path or not content:
        raise ValueError("Both file_path and content are required")
    
    # Get queue backend for enqueuing validation and healing tasks
    queue = get_queue_backend()
    
    # TODO: Implement actual file validation logic
    # This would typically:
    # 1. Parse the documentation file
    # 2. Extract all code snippets
    # 3. Enqueue validation tasks for each snippet:
    #    for snippet in snippets:
    #        queue.enqueue("validation", validate_code_snippet, 
    #                     file_path, snippet.id, snippet.code, snippet.language)
    # 4. Aggregate results
    # 5. If any snippets are invalid, enqueue healing task:
    #    queue.enqueue("healing", heal_documentation_file, file_path, validation_results)
    
    result = {
        "file_path": file_path,
        "snippets_found": 0,
        "snippets_valid": 0,
        "snippets_invalid": 0,
        "errors": [],
    }
    
    logger.info(f"Documentation file validation complete: {file_path}")
    return result


def heal_code_snippet(
    file_path: str,
    snippet_id: str,
    code: str,
    language: str,
    errors: list
) -> Dict[str, Any]:
    """Attempt to heal/fix a code snippet that failed validation.
    
    This task uses AI/heuristics to automatically fix code snippets that
    failed validation. It returns the healed code and a description of
    the changes made.
    
    Args:
        file_path: Path to the documentation file containing the snippet
        snippet_id: Unique identifier for the code snippet
        code: The original code snippet that failed validation
        language: Programming language of the snippet
        errors: List of validation errors to fix
        
    Returns:
        Dictionary containing healing results with keys:
        - healed: Boolean indicating if healing was successful
        - healed_code: The fixed code (if successful)
        - changes: Description of changes made
        - confidence: Confidence score (0-1) in the healing
        
    Raises:
        ValueError: If required parameters are missing or invalid
    """
    logger.info(f"Healing code snippet {snippet_id} from {file_path}")
    logger.debug(f"Language: {language}, Errors: {len(errors)}")
    
    # Validate inputs
    if not file_path or not snippet_id or not code or not language:
        raise ValueError("All parameters (file_path, snippet_id, code, language) are required")
    
    if not errors:
        logger.warning("No errors provided for healing")
        return {
            "healed": False,
            "healed_code": None,
            "changes": [],
            "confidence": 0.0,
            "snippet_id": snippet_id,
            "file_path": file_path,
        }
    
    # Get queue backend (for potential re-validation after healing)
    queue = get_queue_backend()
    
    # Use Bedrock Client to heal the code
    try:
        client = BedrockLLMClient()
        prompt = build_healing_prompt(original_code=code, error_log=str(errors), language=language)
        healed_code = client.generate_correction(prompt=prompt, system_prompt=HEALING_SYSTEM_PROMPT)
        
        if healed_code and healed_code != code:
            logger.info(f"Successfully healed code snippet {snippet_id}")
            result = {
                "healed": True,
                "healed_code": healed_code,
                "changes": ["Fixed validation errors using Claude 3 via Bedrock"],
                "confidence": 0.85,
                "snippet_id": snippet_id,
                "file_path": file_path,
            }
            
            # Enqueue validation task for the healed code
            # queue.enqueue("validation", validate_code_snippet, 
            #               file_path, snippet_id, healed_code, language)
        else:
            logger.warning(f"Failed to heal code snippet {snippet_id}")
            result = {
                "healed": False,
                "healed_code": None,
                "changes": [],
                "confidence": 0.0,
                "snippet_id": snippet_id,
                "file_path": file_path,
            }
    except Exception as e:
        logger.error(f"Error during code healing: {str(e)}")
        result = {
            "healed": False,
            "healed_code": None,
            "changes": [],
            "confidence": 0.0,
            "snippet_id": snippet_id,
            "file_path": file_path,
        }
    
    logger.info(f"Code snippet {snippet_id} healing complete: healed={result['healed']}")
    return result


def heal_documentation_file(
    file_path: str,
    validation_results: Dict[str, Any]
) -> Dict[str, Any]:
    """Heal all invalid code snippets in a documentation file.
    
    This task processes validation results for a documentation file and
    attempts to heal all invalid code snippets, creating a pull request
    with the fixes.
    
    Args:
        file_path: Path to the documentation file
        validation_results: Validation results from validate_documentation_file
        
    Returns:
        Dictionary containing healing results for the file
        
    Raises:
        ValueError: If required parameters are missing
    """
    logger.info(f"Healing documentation file: {file_path}")
    
    # Validate inputs
    if not file_path or not validation_results:
        raise ValueError("Both file_path and validation_results are required")
    
    # Get queue backend for enqueuing healing tasks
    queue = get_queue_backend()
    
    # TODO: Implement actual file healing logic
    # This would typically:
    # 1. Process validation results
    # 2. Enqueue healing tasks for invalid snippets:
    #    for snippet in invalid_snippets:
    #        queue.enqueue("healing", heal_code_snippet,
    #                     file_path, snippet.id, snippet.code, 
    #                     snippet.language, snippet.errors)
    # 3. Aggregate healed code
    # 4. Create pull request with fixes
    
    result = {
        "file_path": file_path,
        "snippets_healed": 0,
        "snippets_failed": 0,
        "pull_request_url": None,
    }
    
    logger.info(f"Documentation file healing complete: {file_path}")
    return result
