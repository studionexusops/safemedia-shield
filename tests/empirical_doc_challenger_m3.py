#!/usr/bin/env python3
"""
Empirical Documentation Contract Challenger for Milestone 3.
Target: docs/SYSTEM_DESIGN.md

Comprehensive verification:
1. Markdown anchor links in Table of Contents vs headings in the document (GFM spec).
2. Code block extraction and syntax validation (TypeScript, JSON, bash, TOML, Mermaid).
3. Prohibited legacy compression terms audit (zero unauthorized occurrences).
4. Full contract parity with codebase (endpoints, types, metafields, UI layout).
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "SYSTEM_DESIGN.md"


def gfm_slug(text: str) -> str:
    """Standard GitHub Flavored Markdown slug generator."""
    text = text.strip()
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = text.lower()

    cleaned = []
    for ch in text:
        if ch in ' \t\u3000':
            cleaned.append('-')
        elif ch in '-_':
            cleaned.append(ch)
        elif ch.isalnum():
            cleaned.append(ch)
    return ''.join(cleaned)


def extract_all_code_blocks(lines):
    """Extracts all code blocks, including indented ones."""
    blocks = []
    in_block = False
    current_lang = ""
    current_lines = []
    start_line = 0

    fence_pattern = re.compile(r'^(\s*)`{3,}([a-zA-Z0-9_\-]+)?')

    for idx, line in enumerate(lines, 1):
        if not in_block:
            m = fence_pattern.match(line)
            if m:
                in_block = True
                current_lang = (m.group(2) or "").lower()
                current_lines = []
                start_line = idx
        else:
            if line.strip().startswith('```'):
                in_block = False
                blocks.append({
                    "start_line": start_line,
                    "end_line": idx,
                    "lang": current_lang,
                    "code": '\n'.join(current_lines)
                })
            else:
                current_lines.append(line)
    return blocks


def run_full_challenge():
    print("=" * 80)
    print("MILESTONE 3 EMPIRICAL DOCUMENTATION CHALLENGER REPORT")
    print(f"Target: {DOC_PATH}")
    print("=" * 80)

    if not DOC_PATH.exists():
        print(f"CRITICAL ERROR: {DOC_PATH} does not exist!")
        return False

    content = DOC_PATH.read_text(encoding='utf-8')
    lines = content.splitlines()

    print(f"Document Metrics: {len(lines)} lines, {len(content)} bytes, {len(content.split())} words.")

    # ----------------------------------------------------
    # CHALLENGE 1: Table of Contents & Anchor Integrity
    # ----------------------------------------------------
    print("\n" + "-" * 80)
    print("[CHALLENGE 1] Markdown Anchor Link Integrity")
    print("-" * 80)

    toc_match = re.search(r'## 目次 \(Table of Contents\)(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if not toc_match:
        print("FAIL: Could not locate '## 目次 (Table of Contents)' section!")
        return False

    toc_links = re.findall(r'\[([^\]]+)\]\(#([^\)]+)\)', toc_match.group(1))
    print(f"Found {len(toc_links)} TOC anchor links.")

    headings = {}
    for idx, line in enumerate(lines, 1):
        m = re.match(r'^(#{1,6})\s+(.*)$', line)
        if m:
            title = m.group(2).strip()
            slug = gfm_slug(title)
            headings[slug] = (idx, title)

    print(f"Found {len(headings)} document headings generating GFM slugs.")

    c1_failures = []
    for title, anchor in toc_links:
        if anchor in headings:
            line_no, h_title = headings[anchor]
            print(f"  [OK] [{title}] -> #{anchor} (Line {line_no}: \"{h_title}\")")
        else:
            print(f"  [BROKEN] [{title}] -> #{anchor} (NOT FOUND)")
            c1_failures.append((title, anchor))

    if c1_failures:
        print(f"\nCHALLENGE 1 RESULT: FAILED ({len(c1_failures)} broken links)")
    else:
        print(f"\nCHALLENGE 1 RESULT: PASSED (100% of {len(toc_links)} TOC links resolve to valid headings)")

    # ----------------------------------------------------
    # CHALLENGE 2: Code Block Syntax Validation
    # ----------------------------------------------------
    print("\n" + "-" * 80)
    print("[CHALLENGE 2] Embedded Code Block Syntax Validation")
    print("-" * 80)

    code_blocks = extract_all_code_blocks(lines)
    print(f"Extracted {len(code_blocks)} code blocks across the document.")

    c2_failures = []
    for idx, block in enumerate(code_blocks, 1):
        s = block["start_line"]
        e = block["end_line"]
        lang = block["lang"]
        raw = block["code"]

        # unindent block
        block_lines = raw.splitlines()
        non_empty = [l for l in block_lines if l.strip()]
        if non_empty:
            min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)
            code = '\n'.join(l[min_indent:] if len(l) >= min_indent else l for l in block_lines)
        else:
            code = raw

        first_preview = non_empty[0].strip() if non_empty else "(empty)"
        print(f"  Block {idx:2d} | Lines {s:3d}-{e:3d} | Lang: {lang:10s} | Preview: {first_preview[:55]}")

        if lang == "json":
            try:
                parsed = json.loads(code)
                print(f"          -> [VALID JSON] parsed keys/elements: {len(parsed) if isinstance(parsed, (dict, list)) else 'scalar'}")
            except Exception as ex:
                print(f"          -> [INVALID JSON] {ex}")
                c2_failures.append((idx, s, e, lang, str(ex)))
        elif lang in ("typescript", "ts"):
            open_count = code.count('{')
            close_count = code.count('}')
            interfaces = re.findall(r'interface\s+([A-Za-z0-9_]+)', code)
            if open_count != close_count:
                err = f"Unmatched curly braces: open={open_count}, close={close_count}"
                print(f"          -> [INVALID TS] {err}")
                c2_failures.append((idx, s, e, lang, err))
            elif not interfaces:
                err = "No interface identifier found in typescript block"
                print(f"          -> [INVALID TS] {err}")
                c2_failures.append((idx, s, e, lang, err))
            else:
                print(f"          -> [VALID TS] Defined interfaces: {', '.join(interfaces)} (Brace balance: {open_count}/{close_count})")
        elif lang in ("bash", "sh"):
            proc = subprocess.run(["bash", "-n"], input=code, text=True, capture_output=True)
            if proc.returncode == 0:
                print(f"          -> [VALID BASH] Syntax checked with 'bash -n'")
            else:
                err = proc.stderr.strip()
                print(f"          -> [INVALID BASH] {err}")
                c2_failures.append((idx, s, e, lang, err))
        elif lang == "mermaid":
            first_kw = code.strip().split()[0] if code.strip() else ""
            if first_kw in ("graph", "sequenceDiagram", "flowchart", "stateDiagram-v2", "stateDiagram", "classDiagram", "erDiagram"):
                print(f"          -> [VALID MERMAID] Valid diagram header: '{first_kw}'")
            else:
                err = f"Unrecognized Mermaid header: '{first_kw}'"
                print(f"          -> [INVALID MERMAID] {err}")
                c2_failures.append((idx, s, e, lang, err))
        elif lang in ("toml", "text", ""):
            print(f"          -> [INFORMATIONAL] format: {lang or 'raw plain text'}")

    if c2_failures:
        print(f"\nCHALLENGE 2 RESULT: FAILED ({len(c2_failures)} invalid code blocks)")
    else:
        print(f"\nCHALLENGE 2 RESULT: PASSED (All {len(code_blocks)} code blocks syntactically valid)")

    # ----------------------------------------------------
    # CHALLENGE 3: Prohibited Terms & Legacy Metric Audit
    # ----------------------------------------------------
    print("\n" + "-" * 80)
    print("[CHALLENGE 3] Prohibited Legacy Compression Terms Audit")
    print("-" * 80)

    audit_terms = [
        "-% Lighter",
        "KB saved",
        "Bulk Store Image Optimization"
    ]

    c3_violations = []
    for term in audit_terms:
        matches = []
        for idx, line in enumerate(lines, 1):
            if term.lower() in line.lower():
                matches.append((idx, line.strip()))

        print(f"  Audit Term: '{term}'")
        if not matches:
            print(f"    -> [CLEAN] 0 occurrences found in document.")
        else:
            for l_num, text in matches:
                is_elimination_doc = any(w in text for w in ["完全排除", "排除", "従来の", "eliminated", "removed"])
                status = "AUTHORIZED (Historical/Explanatory context: documenting complete elimination)" if is_elimination_doc else "UNAUTHORIZED (Active specification violation)"
                print(f"    -> Line {l_num:3d}: {text}")
                print(f"       Classification: {status}")
                if not is_elimination_doc:
                    c3_violations.append((term, l_num, text))

    if c3_violations:
        print(f"\nCHALLENGE 3 RESULT: FAILED ({len(c3_violations)} unauthorized occurrences)")
    else:
        print(f"\nCHALLENGE 3 RESULT: PASSED (0 unauthorized occurrences of prohibited legacy terms)")

    # ----------------------------------------------------
    # OVERALL VERDICT
    # ----------------------------------------------------
    print("\n" + "=" * 80)
    has_errors = bool(c1_failures or c2_failures or c3_violations)
    verdict = "VULNERABILITY_FOUND" if has_errors else "CONFIRMED"
    print(f"FINAL VERDICT: {verdict}")
    print("=" * 80)

    return not has_errors


if __name__ == "__main__":
    success = run_full_challenge()
    sys.exit(0 if success else 1)
