DEVTOOLS_KEYWORDS = [
    "developer", "devtool", "CLI", "SDK", "API", "code", "coding", "debug", "git", 
    "CI", "CD", "DevOps", "terminal", "IDE", "framework", "testing", "monitoring", 
    "observability", "build", "deploy", "infra", "cloud-native", "backend", "log"
]

def is_devtools_related(text):
    text = text.lower()
    return any(keyword.lower() in text for keyword in DEVTOOLS_KEYWORDS)
