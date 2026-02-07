import re

DEVTOOLS_KEYWORDS = [
    "developer", "devtool", "CLI", "SDK", "API", "code", "coding", "debug", "git",
    "CI", "CD", "DevOps", "terminal", "IDE", "framework", "testing", "monitoring",
    "observability", "build", "deploy", "infra", "cloud-native", "backend", "log"
]

_KEYWORD_PATTERNS = [
    re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
    for kw in DEVTOOLS_KEYWORDS
]


def is_devtools_related(text: str) -> bool:
    return any(pattern.search(text) for pattern in _KEYWORD_PATTERNS)
