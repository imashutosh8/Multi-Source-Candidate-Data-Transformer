import re

# Centralized Regular Expressions for extracting data fields
EMAIL_PATTERN = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
PHONE_PATTERN = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
LINK_PATTERN = r'https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z0-9-]+(?:/[^\s]*)?'

# Standard skills lookup vocabulary
SKILL_VOCABULARY = {
    "python", "py", "javascript", "js", "typescript", "ts", "java", "c++", "cpp", "c plus plus",
    "c#", "go", "golang", "ruby", "php", "swift", "kotlin", "rust", "scala", "sql", "nosql",
    "aws", "gcp", "azure", "docker", "kubernetes", "k8s", "terraform", "ansible", "git",
    "react", "angular", "vue", "node", "django", "flask", "fastapi", "pandas", "numpy",
    "pytorch", "tensorflow", "spark", "hadoop", "graphql", "rest api", "html", "css"
}
