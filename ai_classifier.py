from dotenv import load_dotenv
import openai
import os
from typing import Dict, Optional

# Load environment variables from .env file
load_dotenv()

# Initialize LLM Observability before creating OpenAI client
from ddtrace.llmobs import LLMObs

LLMObs.enable(
    ml_app="devtoolscrape",
    api_key=os.getenv('DATADOG_API_KEY'),
    site="datadoghq.com",
    agentless_enabled=True,
)

# Set up OpenAI client
client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def has_devtools_keywords(text: str, name: str = "") -> bool:
    """Quick keyword pre-filter to avoid unnecessary API calls"""
    DEVTOOLS_KEYWORDS = [
        "developer", "devtool", "CLI", "SDK", "API", "code", "coding", "debug", "git", 
        "CI", "CD", "DevOps", "terminal", "IDE", "framework", "testing", "monitoring", 
        "observability", "build", "deploy", "infra", "cloud-native", "backend", "log",
        "linter", "formatter", "package manager", "container", "kubernetes", "docker", "microservice", "serverless", "database",
        "query", "schema", "migration", "deployment", "orchestration", "automation"
    ]
    
    combined_text = f"{name} {text}".lower()
    return any(keyword.lower() in combined_text for keyword in DEVTOOLS_KEYWORDS)

def is_devtools_related_ai(text: str, name: str = "") -> bool:
    """
    Use OpenAI to classify if content is devtools-related.
    Returns True if it's devtools, False otherwise.
    """
    # Quick keyword pre-filter to avoid unnecessary API calls
    if not has_devtools_keywords(text, name):
        return False
    
    if not os.getenv('OPENAI_API_KEY'):
        print("Warning: OPENAI_API_KEY not set. Falling back to keyword matching.")
        return is_devtools_related_fallback(text)
    
    prompt = f"""
    You are a classifier that determines if software/tools are developer tools (devtools).

    Devtools include:
    - Development tools (IDEs, text editors, debuggers)
    - Build tools, package managers, CI/CD tools
    - Testing frameworks, monitoring tools
    - API tools, SDKs, libraries
    - DevOps tools, infrastructure tools
    - Code analysis, linting, formatting tools
    - Database tools, deployment tools
    - Terminal tools, CLI applications
    - Developer productivity tools

    NOT devtools:
    - End-user applications (games, social media, productivity apps)
    - Business software, marketing tools
    - Consumer apps, entertainment apps
    - E-commerce, finance apps (unless specifically for developers)

    Examples:
    Name: VSCode
    Description: A code editor for developers.
    Answer: yes

    Name: Slack
    Description: A team chat and collaboration app.
    Answer: no

    Name: GitHub Actions
    Description: A CI/CD automation tool for code repositories.
    Answer: yes

    Name: QuickBooks
    Description: Accounting software for small businesses.
    Answer: no

    Content to classify:
    Name: {name}
    Description: {text}

    Answer with ONLY "yes" or "no".
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that classifies software as devtools or not. Respond with only 'yes' or 'no'."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=10,
            temperature=0.0
        )
        
        answer = response.choices[0].message.content.strip().lower()
        if answer not in ['yes', 'no']:
            print(f"Unexpected classifier output: {answer!r}")
            return is_devtools_related_fallback(text)
        return answer == 'yes'
        
    except Exception as e:
        print(f"OpenAI API error: {e}. Falling back to keyword matching.")
        return is_devtools_related_fallback(text)

def is_devtools_related_fallback(text: str) -> bool:
    """Fallback keyword-based classifier when AI is unavailable"""
    DEVTOOLS_KEYWORDS = [
        "developer", "devtool", "CLI", "SDK", "API", "code", "coding", "debug", "git", 
        "CI", "CD", "DevOps", "terminal", "IDE", "framework", "testing", "monitoring", 
        "observability", "build", "deploy", "infra", "cloud-native", "backend", "log",
        "linter", "formatter", "package manager", "dependency", "compiler", "interpreter",
        "container", "kubernetes", "docker", "microservice", "serverless", "database",
        "query", "schema", "migration", "deployment", "orchestration", "automation"
    ]
    
    text = text.lower()
    return any(keyword.lower() in text for keyword in DEVTOOLS_KEYWORDS)

def get_devtools_category(text: str, name: str = "") -> Optional[str]:
    """
    Get a more specific category for the devtool.
    Returns category like 'IDE', 'CLI Tool', 'Testing', etc.
    """
    if not os.getenv('OPENAI_API_KEY'):
        return None
    
    prompt = f"""
    Classify this devtool into one of these categories:
    - IDE/Editor: Integrated development environments, code editors
    - CLI Tool: Command line tools, terminal applications
    - Testing: Testing frameworks, test runners, mocking tools
    - Build/Deploy: Build tools, deployment tools, CI/CD
    - Monitoring/Observability: Logging, metrics, tracing, alerting
    - Database: Database tools, ORMs, query builders
    - API/SDK: API tools, SDKs, client libraries
    - DevOps: Infrastructure, containerization, orchestration
    - Code Quality: Linters, formatters, static analysis
    - Package Manager: Dependency management, package managers
    - Other: Anything else

    Examples:
    Name: VSCode
    Description: A code editor for developers.
    Category: IDE/Editor

    Name: GitHub Actions
    Description: A CI/CD automation tool for code repositories.
    Category: Build/Deploy

    Name: Postman
    Description: API development and testing tool.
    Category: API/SDK

    Name: Datadog
    Description: Cloud monitoring and observability platform.
    Category: Monitoring/Observability

    Name: Slack
    Description: A team chat and collaboration app.
    Category: Other

    Name: QuickBooks
    Description: Accounting software for small businesses.
    Category: Other

    Name: {name}
    Description: {text}

    Respond with ONLY the category name.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that categorizes devtools. Respond with only the category name."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=20,
            temperature=0.0
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None 