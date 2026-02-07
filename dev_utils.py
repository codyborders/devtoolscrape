DEVTOOLS_KEYWORDS = [
    "developer", "devtool", "CLI", "SDK", "API", "code", "coding", "debug", "git",
    "CI", "CD", "DevOps", "terminal", "IDE", "framework", "testing", "monitoring",
    "observability", "build", "deploy", "infra", "cloud-native", "backend", "log",
]

_DEVTOOLS_KEYWORDS_LOWER = [kw.lower() for kw in DEVTOOLS_KEYWORDS]


def is_devtools_related(text):
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in _DEVTOOLS_KEYWORDS_LOWER)
