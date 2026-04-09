"""Curated database of common bug patterns across languages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BugPattern:
    id: str
    name: str
    category: str
    languages: list[str]
    description: str
    example_buggy: str
    example_fixed: str
    severity: str
    cwe_id: str  # Common Weakness Enumeration


# Curated bug patterns
PATTERNS: list[BugPattern] = [
    BugPattern(
        id="OBO-001", name="Off-By-One Error", category="boundary",
        languages=["python", "javascript", "java", "c++"],
        description="Loop iterates one too many or one too few times",
        example_buggy="for i in range(len(arr) + 1): arr[i]",
        example_fixed="for i in range(len(arr)): arr[i]",
        severity="high", cwe_id="CWE-193",
    ),
    BugPattern(
        id="NPE-001", name="Null Pointer Dereference", category="null_ref",
        languages=["python", "javascript", "java"],
        description="Accessing attribute/method on None/null/undefined",
        example_buggy="result = obj.value  # obj may be None",
        example_fixed="result = obj.value if obj is not None else default",
        severity="critical", cwe_id="CWE-476",
    ),
    BugPattern(
        id="SQL-001", name="SQL Injection", category="security",
        languages=["python", "javascript", "java"],
        description="User input directly concatenated into SQL query",
        example_buggy="cursor.execute(f\"SELECT * FROM users WHERE id = {user_id}\")",
        example_fixed="cursor.execute(\"SELECT * FROM users WHERE id = ?\", (user_id,))",
        severity="critical", cwe_id="CWE-89",
    ),
    BugPattern(
        id="XSS-001", name="Cross-Site Scripting", category="security",
        languages=["javascript"],
        description="User input rendered without sanitization",
        example_buggy="element.innerHTML = userInput",
        example_fixed="element.textContent = userInput",
        severity="critical", cwe_id="CWE-79",
    ),
    BugPattern(
        id="CMD-001", name="Command Injection", category="security",
        languages=["python", "javascript"],
        description="User input passed to shell command",
        example_buggy="os.system(f'echo {user_input}')",
        example_fixed="subprocess.run(['echo', user_input], shell=False)",
        severity="critical", cwe_id="CWE-78",
    ),
    BugPattern(
        id="RC-001", name="Race Condition", category="concurrency",
        languages=["python", "javascript", "java", "go"],
        description="Shared state accessed without synchronization",
        example_buggy="counter += 1  # in multiple threads",
        example_fixed="with lock: counter += 1",
        severity="high", cwe_id="CWE-362",
    ),
    BugPattern(
        id="BEX-001", name="Bare Exception Handler", category="error_handling",
        languages=["python"],
        description="Catching all exceptions silently hides bugs",
        example_buggy="except: pass",
        example_fixed="except SpecificError as e: logger.error(e)",
        severity="medium", cwe_id="CWE-396",
    ),
    BugPattern(
        id="INT-001", name="Integer Overflow", category="boundary",
        languages=["c++", "java"],
        description="Arithmetic exceeds integer type bounds",
        example_buggy="int result = a * b;  // may overflow",
        example_fixed="long result = (long)a * b;",
        severity="high", cwe_id="CWE-190",
    ),
    BugPattern(
        id="UAF-001", name="Use After Free", category="memory",
        languages=["c++", "rust"],
        description="Accessing memory after it has been freed",
        example_buggy="free(ptr); *ptr = 42;",
        example_fixed="free(ptr); ptr = NULL;",
        severity="critical", cwe_id="CWE-416",
    ),
    BugPattern(
        id="TOCTOU-001", name="Time-of-Check to Time-of-Use", category="concurrency",
        languages=["python", "javascript", "java"],
        description="State changes between check and use",
        example_buggy="if os.path.exists(f): data = open(f).read()",
        example_fixed="try: data = open(f).read() except FileNotFoundError: ...",
        severity="medium", cwe_id="CWE-367",
    ),
    BugPattern(
        id="DIV-001", name="Division by Zero", category="boundary",
        languages=["python", "javascript", "java", "c++"],
        description="Dividing by a value that could be zero",
        example_buggy="result = total / count",
        example_fixed="result = total / count if count != 0 else 0",
        severity="high", cwe_id="CWE-369",
    ),
    BugPattern(
        id="PATH-001", name="Path Traversal", category="security",
        languages=["python", "javascript", "java"],
        description="User-controlled file path allows directory traversal",
        example_buggy="open(f'/data/{filename}')",
        example_fixed="safe = Path(filename).name; open(f'/data/{safe}')",
        severity="critical", cwe_id="CWE-22",
    ),
    BugPattern(
        id="DESER-001", name="Unsafe Deserialization", category="security",
        languages=["python", "java"],
        description="Deserializing untrusted data can execute arbitrary code",
        example_buggy="pickle.loads(user_data)",
        example_fixed="json.loads(user_data)",
        severity="critical", cwe_id="CWE-502",
    ),
    BugPattern(
        id="LEAK-001", name="Resource Leak", category="resource",
        languages=["python", "java", "c++"],
        description="File/connection opened but never closed",
        example_buggy="f = open('file.txt')\ndata = f.read()",
        example_fixed="with open('file.txt') as f:\n    data = f.read()",
        severity="medium", cwe_id="CWE-404",
    ),
    BugPattern(
        id="HARDCRED-001", name="Hardcoded Credentials", category="security",
        languages=["python", "javascript", "java"],
        description="Passwords or API keys hardcoded in source code",
        example_buggy="password = 'admin123'",
        example_fixed="password = os.environ['DB_PASSWORD']",
        severity="critical", cwe_id="CWE-798",
    ),
]


def get_patterns_for_language(language: str) -> list[BugPattern]:
    return [p for p in PATTERNS if language in p.languages]


def get_pattern_by_category(category: str) -> list[BugPattern]:
    return [p for p in PATTERNS if p.category == category]


def get_all_patterns() -> list[BugPattern]:
    return PATTERNS
