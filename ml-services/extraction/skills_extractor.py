"""
skills_extractor.py
────────────────────
Extracts technical skills from resume text using:
  1. A large curated skill patterns list (EntityRuler on spaCy en_core_web_md)
  2. Regex-based fallback for comma/pipe/bullet separated tokens
  3. Cross-section priority: skills found in BOTH the Skills tab AND the
     Projects tab are ranked higher (priority: "high") than those found
     in only one section (priority: "medium").

Public API:
    extract_skill(skills_text, projects_text="") → dict
"""

import re
import spacy
from spacy.pipeline import EntityRuler

# ── Load model once at module level ──────────────────────────────────────────
nlp = spacy.load("en_core_web_md")

# ── Master Skill Patterns ────────────────────────────────────────────────────
# Grouped by domain for maintainability.  Add new skills here.
SKILL_PATTERNS = [
    # ── Programming Languages ────────────────────────────────────────────────
    "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#", "Go",
    "Rust", "Ruby", "PHP", "Swift", "Kotlin", "Scala", "Perl", "R",
    "MATLAB", "Dart", "Lua", "Haskell", "Elixir", "Erlang", "Julia",
    "Objective-C", "Assembly", "Bash", "Shell", "PowerShell", "Groovy",
    "VBA", "COBOL", "Fortran", "Solidity",

    # ── Web Frontend ─────────────────────────────────────────────────────────
    "HTML", "CSS", "SCSS", "SASS", "LESS", "Tailwind CSS", "Tailwind",
    "Bootstrap", "React", "React.js", "ReactJS", "Next.js", "NextJS",
    "Angular", "AngularJS", "Vue", "Vue.js", "VueJS", "Svelte", "SvelteKit",
    "jQuery", "Redux", "MobX", "Zustand", "Webpack", "Vite", "Babel",
    "Three.js", "D3.js", "Material UI", "Chakra UI", "Ant Design",
    "Storybook", "Gatsby", "Nuxt.js", "Astro", "Remix",

    # ── Web Backend ──────────────────────────────────────────────────────────
    "Node.js", "NodeJS", "Express", "Express.js", "ExpressJS",
    "Django", "Flask", "FastAPI", "Spring", "Spring Boot", "SpringBoot",
    "ASP.NET", ".NET", "Rails", "Ruby on Rails", "Laravel", "Symfony",
    "NestJS", "Koa", "Hapi", "Gin", "Fiber", "Echo",
    "GraphQL", "REST API", "REST APIs", "RESTful", "gRPC", "WebSocket",
    "Microservices", "Serverless",

    # ── Databases ────────────────────────────────────────────────────────────
    "SQL", "MySQL", "PostgreSQL", "SQLite", "MariaDB", "Oracle",
    "MongoDB", "Mongoose", "Redis", "Cassandra", "DynamoDB",
    "Firebase", "Firestore", "CouchDB", "Neo4j", "Elasticsearch",
    "InfluxDB", "TimescaleDB", "Supabase", "PlanetScale",
    "SQLAlchemy", "Prisma", "Sequelize", "TypeORM", "Drizzle",

    # ── Cloud & DevOps ───────────────────────────────────────────────────────
    "AWS", "Amazon Web Services", "Azure", "Google Cloud", "GCP",
    "Docker", "Kubernetes", "K8s", "Terraform", "Ansible", "Jenkins",
    "GitHub Actions", "GitLab CI", "CI/CD", "CircleCI", "Travis CI",
    "Nginx", "Apache", "Heroku", "Vercel", "Netlify", "DigitalOcean",
    "Cloudflare", "AWS Lambda", "EC2", "S3", "RDS", "CloudFormation",
    "ECS", "EKS", "Fargate", "SageMaker", "Azure DevOps",
    "Cloud Functions", "App Engine", "BigQuery",

    # ── AI / ML / Data Science ───────────────────────────────────────────────
    "Machine Learning", "Deep Learning", "Neural Networks",
    "Natural Language Processing", "NLP", "Computer Vision",
    "Reinforcement Learning", "Generative AI", "GenAI", "LLM",
    "Large Language Models", "Transformers", "BERT", "GPT",
    "Convolutional Neural Networks", "CNN", "Recurrent Neural Networks", "RNN",
    "GANs", "Generative Adversarial Networks", "Diffusion Models",
    "Transfer Learning", "Fine-tuning", "Prompt Engineering",
    "RAG", "Retrieval Augmented Generation", "LangChain", "LangGraph",
    "OpenAI", "Hugging Face", "HuggingFace",

    # ── ML/Data Libraries ────────────────────────────────────────────────────
    "TensorFlow", "Keras", "PyTorch", "Scikit-learn", "Sklearn",
    "XGBoost", "LightGBM", "CatBoost", "SpaCy", "NLTK", "Gensim",
    "OpenCV", "Pandas", "NumPy", "Matplotlib", "Seaborn", "Plotly",
    "SciPy", "Statsmodels", "MLflow", "Weights & Biases", "W&B",
    "ONNX", "TensorRT", "JAX", "Flax",

    # ── Data Engineering ─────────────────────────────────────────────────────
    "Apache Spark", "Spark", "PySpark", "Hadoop", "Hive", "Kafka",
    "Apache Kafka", "Airflow", "Apache Airflow", "dbt",
    "ETL", "Data Pipeline", "Data Warehousing", "Data Modeling",
    "Data Preprocessing", "Feature Engineering", "Data Cleaning",
    "Dataset Preparation", "Model Evaluation", "Model Optimization",
    "Snowflake", "Databricks", "Apache Flink", "Apache Beam",

    # ── Mobile Development ───────────────────────────────────────────────────
    "React Native", "Flutter", "SwiftUI", "Jetpack Compose",
    "Android", "iOS", "Xamarin", "Ionic", "Capacitor",
    "Expo", "Android Studio", "Xcode",

    # ── Tools & Platforms ────────────────────────────────────────────────────
    "Git", "GitHub", "GitLab", "Bitbucket", "SVN",
    "VS Code", "Visual Studio", "IntelliJ", "PyCharm", "Eclipse",
    "Jupyter", "Jupyter Notebook", "Google Colab", "Kaggle",
    "Postman", "Swagger", "Insomnia",
    "Jira", "Confluence", "Trello", "Notion", "Slack",
    "Figma", "Adobe XD", "Sketch", "Canva",
    "Linux", "Ubuntu", "Windows", "macOS",

    # ── Testing ──────────────────────────────────────────────────────────────
    "JUnit", "Jest", "Mocha", "Chai", "Cypress", "Selenium",
    "Pytest", "Unittest", "TestNG", "Playwright", "Puppeteer",
    "TDD", "BDD", "Unit Testing", "Integration Testing",

    # ── Blockchain & Web3 ────────────────────────────────────────────────────
    "Blockchain", "Ethereum", "Solidity", "Smart Contracts",
    "Web3", "Web3.js", "Ethers.js", "Hardhat", "Truffle",
    "IPFS", "DeFi", "NFT", "Hyperledger",

    # ── Cybersecurity ────────────────────────────────────────────────────────
    "Penetration Testing", "Ethical Hacking", "OWASP",
    "Burp Suite", "Metasploit", "Nmap", "Wireshark",
    "Cryptography", "Network Security", "Firewall",

    # ── CS Fundamentals ──────────────────────────────────────────────────────
    "Data Structures", "Algorithms", "Data Structures and Algorithms",
    "Data Structures & Algorithms", "DSA",
    "Object-Oriented Programming", "OOP", "OOPS",
    "Database Management Systems", "DBMS",
    "Operating Systems", "OS",
    "Computer Networks", "Networking",
    "System Design", "Design Patterns",
    "Agile", "Scrum", "Kanban",
    "Problem Solving", "Analytical Thinking", "Critical Thinking",

    # ── Misc / Other ─────────────────────────────────────────────────────────
    "OCR", "Tesseract", "Web Scraping", "BeautifulSoup", "Scrapy",
    "Selenium", "API Development", "Streamlit", "Gradio",
    "RabbitMQ", "Celery", "Socket.IO", "WebRTC",
    "OAuth", "JWT", "SSO", "LDAP",
    "LaTeX", "Markdown", "XML", "JSON", "YAML", "CSV",
    "Power BI", "Tableau", "Looker", "Excel",
]


# ── Build EntityRuler patterns (done once at import) ─────────────────────────
def _build_ruler():
    """Creates a spaCy EntityRuler with all skill patterns."""
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    patterns = []
    for skill in SKILL_PATTERNS:
        # Each pattern matches the exact multi-word phrase
        pattern = {
            "label": "SKILL",
            "pattern": [{"LOWER": tok.lower()} for tok in skill.split()],
        }
        patterns.append(pattern)
    ruler.add_patterns(patterns)
    return ruler

_build_ruler()


# ── Normalisation helpers ────────────────────────────────────────────────────
# Canonical form map: lowered variant → proper display name
_CANONICAL = {s.lower(): s for s in SKILL_PATTERNS}


def _normalise(skill_text: str) -> str:
    """
    Normalise a raw skill token to its canonical display name.
    e.g.  "react.js" → "React.js",  "PYTHON" → "Python"
    """
    stripped = skill_text.strip().rstrip(".,;:")
    return _CANONICAL.get(stripped.lower(), stripped)


def _tokenise_line(line: str) -> list[str]:
    """
    Splits a single line by common resume delimiters:
      commas, pipes (|), bullets (•), semicolons, tabs
    Returns a list of non-empty stripped tokens.
    """
    # Split on: comma, pipe, bullet, semicolon, tab, or the unicode bullet variants
    tokens = re.split(r'[,|•;●○▪▸►◆\t]', line)
    return [t.strip() for t in tokens if t.strip()]


# ── Core extraction logic ───────────────────────────────────────────────────
def _extract_from_text(text: str) -> set[str]:
    """
    Extracts skills from a block of text using two strategies:
      1. spaCy EntityRuler — catches multi-word skills (e.g. "Machine Learning")
      2. Regex tokenisation — catches comma-separated single-word skills the
         ruler might miss if they aren't in its pattern list.
    Returns a set of normalised skill names.
    """
    if not text or not text.strip():
        return set()

    found = set()

    # ── Strategy 1: spaCy EntityRuler ────────────────────────────────────────
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "SKILL":
            found.add(_normalise(ent.text))

    # ── Strategy 2: Line-by-line tokenisation ────────────────────────────────
    # Handles "Python, C++, SQL" style lists that the NER may partially miss
    for line in text.split("\n"):
        # Skip lines that look like bullet-point descriptions (sentences)
        stripped = line.strip()
        if not stripped:
            continue

        # If a line has a "Category:" prefix, only tokenise the value part
        if ":" in stripped:
            _, _, value_part = stripped.partition(":")
            tokens = _tokenise_line(value_part)
        else:
            tokens = _tokenise_line(stripped)

        for token in tokens:
            # Only accept it if it's a known skill (avoids noise)
            if token.lower() in _CANONICAL:
                found.add(_normalise(token))

    return found


def _extract_skills_from_projects(text: str) -> set[str]:
    """
    Extracts skills specifically from the PROJECTS section.
    Projects list tech stacks in lines like:
        "ResuListic — AI Powered Platform    Python, FastAPI, PostgreSQL"
    We look for lines that are mostly comma-separated known skills.
    Also runs the full EntityRuler over the text for embedded mentions.
    """
    if not text or not text.strip():
        return set()

    found = set()

    # Run the full NER pipeline on the entire projects text
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ == "SKILL":
            found.add(_normalise(ent.text))

    # Also do line-by-line tokenisation for tech stack lines
    for line in text.split("\n"):
        tokens = _tokenise_line(line)
        for token in tokens:
            if token.lower() in _CANONICAL:
                found.add(_normalise(token))

    return found


# ── Public API ───────────────────────────────────────────────────────────────
def extract_skill(skills_text: str, projects_text: str = "") -> dict:
    """
    Extracts and prioritises skills from a resume.

    Args:
        skills_text:   Raw text from the SKILLS / TECHNICAL SKILLS section.
        projects_text: Raw text from the PROJECTS section.

    Returns:
        {
            "high":   [...],   # Skills found in BOTH sections (most relevant)
            "medium": [...],   # Skills found in only ONE section
        }
    
    Skills in "high" are the ones the candidate explicitly lists AND
    demonstrates through projects — these are the most credible.
    """
    skills_set = _extract_from_text(skills_text)
    projects_set = _extract_skills_from_projects(projects_text)

    # Skills in BOTH sections → high priority (explicitly listed + demonstrated)
    high_priority = sorted(skills_set & projects_set)

    # Skills in only one section → medium priority
    only_skills = skills_set - projects_set
    only_projects = projects_set - skills_set
    medium_priority = sorted(only_skills | only_projects)

    return {
        "high":   high_priority,
        "medium": medium_priority,
    }


# ── Quick Test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_skills = """
    Programming Languages: Python, C++, SQL
    Artificial Intelligence & Machine Learning: Machine Learning, Deep Learning, Neural Networks, Computer
    Vision, Natural Language Processing (NLP)
    Libraries & Frameworks: PyTorch, Scikit-learn, OpenCV, Pandas, NumPy
    Data & Model Development: Data Preprocessing, Feature Engineering, Dataset Preparation, Model Evaluation,
    Model Optimization
    Backend & Databases: FastAPI, SQLAlchemy, PostgreSQL
    Core Competencies: Data Structures & Algorithms, Analytical Thinking, Problem Solving
    """

    sample_projects = """
    ResuListic — AI Powered Career Intelligence Platform
    Python, FastAPI, PostgreSQL, SQLAlchemy, OCR, Machine Learning
    • Building an intelligent career recommendation and resume analysis platform.
    • Designing resume parsing pipelines using OCR and NLP concepts.

    Dynamic Programming Visualizer App
    Python, Streamlit
    • Developed an interactive educational platform for visualizing DP algorithms.

    E-Commerce Product Management System
    C++, STL
    • Designed scalable cart and inventory management modules.
    """

    result = extract_skill(sample_skills, sample_projects)

    print("HIGH PRIORITY (in Skills + Projects):")
    for s in result["high"]:
        print(f"   [*] {s}")

    print(f"\nMEDIUM PRIORITY (in one section only):")
    for s in result["medium"]:
        print(f"   [-] {s}")

    print(f"\nTotal: {len(result['high'])} high + {len(result['medium'])} medium = {len(result['high']) + len(result['medium'])} skills")