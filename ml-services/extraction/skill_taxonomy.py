"""
skill_taxonomy.py — 3-Level Hierarchical Skill Taxonomy Engine.

Level 1: Domains (9 Core Domains)
Level 2: Resume Skills (Canonical Umbrella / Commonly Listed Resume Skills: 64 skills)
Level 3: Subtopics (Granular technical concepts, algorithms, tools: >500 subtopics)
"""

from typing import Dict, List, Optional, Tuple

__all__ = [
    "SKILL_TAXONOMY",
    "SKILL_ALIASES",
    "get_subtopics",
    "get_domain",
    "get_all_skills_flat",
    "get_canonical_skill",
    "get_parent_skill",
]

# ── Level 1 & Level 2 & Level 3: Master Skill Taxonomy ────────────────────────

SKILL_TAXONOMY: Dict[str, Dict[str, List[str]]] = {
    # ── 1. Core CS & Foundations ──────────────────────────────────────────────
    "Core CS & Foundations": {
        "DSA": [
            "Array", "String", "Linked List", "Stack", "Queue", "Tree",
            "Binary Search Tree", "Graph", "Heap", "Hash Table",
            "Dynamic Programming", "Recursion", "Backtracking", "Binary Search",
            "Greedy", "Sorting", "Bit Manipulation", "Two Pointers",
            "Divide and Conquer", "Depth-First Search", "Breadth-First Search"
        ],
        "OOP": [
            "Inheritance", "Polymorphism", "Encapsulation", "Abstraction",
            "SOLID Principles", "Design Patterns", "Classes and Objects",
            "Composition", "Interfaces", "Abstract Classes"
        ],
        "System Design": [
            "High-Level Design", "Low-Level Design", "Microservices",
            "Load Balancing", "Caching", "Sharding", "CAP Theorem",
            "Message Queues", "Rate Limiting", "Consistent Hashing",
            "Database Partitioning", "API Gateway"
        ],
        "Operating Systems": [
            "Processes and Threads", "Concurrency", "Deadlock", "CPU Scheduling",
            "Virtual Memory", "Paging", "File Systems", "Inter-Process Communication",
            "Synchronization", "Semaphores"
        ],
        "Computer Networks": [
            "OSI Model", "TCP/IP", "HTTP/HTTPS", "DNS", "WebSockets",
            "Routing Protocols", "Subnetting", "Sockets", "TLS/SSL", "Load Balancers"
        ],
        "DBMS": [
            "Relational Model", "SQL Queries", "Indexing", "B-Trees",
            "ACID Properties", "Transactions", "Normalization", "Denormalization",
            "Query Optimization", "Concurrency Control"
        ],
    },

    # ── 2. Programming Languages ─────────────────────────────────────────────
    "Programming Languages": {
        "Python": [
            "PEP 8", "Generators", "Decorators", "GIL", "Asyncio", "Typing",
            "List Comprehensions", "Context Managers", "Metaclasses", "Multiprocessing"
        ],
        "Java": [
            "JVM", "Garbage Collection", "Multithreading", "Spring Integration",
            "Generics", "Streams API", "Collections Framework", "Concurrency Utilities",
            "Java Memory Model"
        ],
        "C++": [
            "Pointers and References", "Memory Management", "RAII", "STL",
            "Templates", "Smart Pointers", "Move Semantics", "Lambda Expressions",
            "Virtual Functions"
        ],
        "C": [
            "Pointers", "Dynamic Memory Allocation", "Structs", "Macros and Preprocessor",
            "File I/O", "Bitwise Operators", "Memory Layout", "Header Files"
        ],
        "JavaScript": [
            "ES6+", "Event Loop", "Closures", "Promises", "Async/Await",
            "Prototypes", "DOM Manipulation", "Scope and Hoisting", "V8 Engine"
        ],
        "TypeScript": [
            "Interfaces", "Type Aliases", "Generics", "Union and Intersection Types",
            "Type Narrowing", "Decorators", "Utility Types", "TSConfig"
        ],
        "Go": [
            "Goroutines", "Channels", "Interfaces", "Pointers", "Select Statements",
            "Error Handling", "Defer", "Go Modules", "Garbage Collector"
        ],
        "Rust": [
            "Ownership", "Borrowing and Lifetimes", "Traits", "Pattern Matching",
            "Cargo", "Error Handling", "Smart Pointers", "Concurrency"
        ],
        "C#": [
            "CLR", "LINQ", "Async/Await", "Delegates and Events", "Generics",
            "Dependency Injection", ".NET Core", "Garbage Collection"
        ],
        "SQL": [
            "SELECT Queries", "JOINs", "Aggregations", "Subqueries",
            "Window Functions", "CTEs", "Indexes", "Stored Procedures", "Triggers", "Views"
        ],
    },

    # ── 3. Frontend Web Development ──────────────────────────────────────────
    "Frontend Web Development": {
        "React": [
            "JSX", "Hooks", "Virtual DOM", "Component Lifecycle", "State Management",
            "Context API", "Server Components", "Suspense", "Performance Optimization"
        ],
        "Next.js": [
            "Server-Side Rendering (SSR)", "Static Site Generation (SSG)",
            "Incremental Static Regeneration (ISR)", "App Router", "API Routes",
            "Hydration", "Middleware"
        ],
        "Vue": [
            "Reactivity System", "Vue 3 Composition API", "Directives", "Vuex / Pinia",
            "Vue Router", "Scoped Slots", "Single File Components"
        ],
        "Angular": [
            "Components", "Directives", "Services and DI", "RxJS", "Routing",
            "NgRx", "Forms and Validation", "Zone.js"
        ],
        "HTML/CSS": [
            "Semantic HTML", "Flexbox", "CSS Grid", "Responsive Design",
            "Media Queries", "Transitions and Animations", "Box Model", "Accessibility (a11y)"
        ],
        "Tailwind CSS": [
            "Utility-First Workflow", "JIT Engine", "Responsive Modifiers",
            "Custom Plugins", "Typography Plugin", "Dark Mode", "Theme Configuration"
        ],
        "Redux": [
            "Store", "Actions and Action Creators", "Reducers", "Immutability",
            "Redux Toolkit (RTK)", "Redux Thunk", "Selectors", "Middleware"
        ],
    },

    # ── 4. Backend Web Development ───────────────────────────────────────────
    "Backend Web Development": {
        "FastAPI": [
            "Pydantic Models", "Dependency Injection", "Asynchronous Endpoints",
            "OpenAPI Docs", "Background Tasks", "Middleware", "OAuth2 & JWT", "WebSockets"
        ],
        "Django": [
            "Django ORM", "MVT Pattern", "Django REST Framework (DRF)",
            "Authentication & Permissions", "Middleware", "Migrations", "Admin Panel", "Signals"
        ],
        "Flask": [
            "Blueprints", "Application Context", "Request Handling", "Jinja2 Templates",
            "Extensions", "Werkzeug WSGI", "Flask-SQLAlchemy", "Error Handling"
        ],
        "Node.js": [
            "Event Loop", "Buffer & Streams", "Cluster & Worker Threads",
            "File System (fs)", "NPM Ecosystem", "EventEmitter", "Non-blocking I/O", "Module System"
        ],
        "Express": [
            "Routing", "Middleware Chain", "Error Handling", "RESTful Routing",
            "Template Engines", "CORS", "Body Parsing", "Security Best Practices"
        ],
        "Spring Boot": [
            "IoC and DI", "Spring MVC", "Spring Data JPA", "Spring Security",
            "Actuator", "Bean Lifecycle", "Auto-Configuration", "Microservices Support"
        ],
        "GraphQL": [
            "Schemas and Types", "Queries and Mutations", "Resolvers",
            "Subscriptions", "Apollo Server", "DataLoader", "GraphiQL", "Schema Stitching"
        ],
        "REST APIs": [
            "HTTP Verbs", "Status Codes", "Resource Naming", "Statelessness",
            "Idempotency", "Pagination", "Versioning", "HATEOAS"
        ],
    },

    # ── 5. Databases & Storage ───────────────────────────────────────────────
    "Databases & Storage": {
        "PostgreSQL": [
            "ACID Compliance", "Indexing (B-Tree, GIN, GiST)", "EXPLAIN ANALYZE",
            "Partitioning", "JSONB", "Connection Pooling", "MVCC", "Replication"
        ],
        "MySQL": [
            "InnoDB Engine", "Replication", "Query Optimization", "Table Locking",
            "Triggers", "Stored Procedures", "Foreign Keys", "Binary Logging"
        ],
        "MongoDB": [
            "Document Schema", "Aggregation Pipeline", "Indexing", "Replica Sets",
            "Sharding", "BSON Types", "GridFS", "Change Streams"
        ],
        "Redis": [
            "Key-Value Store", "In-Memory Data Structures", "Pub/Sub",
            "Eviction Policies", "Persistence (RDB/AOF)", "Redis Clustering",
            "Caching Patterns", "Transactions"
        ],
        "Elasticsearch": [
            "Inverted Index", "Full-Text Search", "Analyzers and Tokenizers",
            "Aggregations", "Mapping Types", "Cluster & Shards", "Lucene Engine", "Kibana"
        ],
        "Cassandra": [
            "Wide-Column Store", "LSM Trees", "Partition Key & Clustering Key",
            "Consistency Levels", "Gossip Protocol", "CQL", "Peer-to-Peer Architecture"
        ],
    },

    # ── 6. Cloud & DevOps ────────────────────────────────────────────────────
    "Cloud & DevOps": {
        "Docker": [
            "Containerization", "Dockerfile Best Practices", "Multi-Stage Builds",
            "Docker Compose", "Docker Volumes", "Docker Networking",
            "Image Optimization", "Container Lifecycle"
        ],
        "Kubernetes": [
            "Pods", "Deployments", "Services", "Ingress", "ConfigMaps & Secrets",
            "StatefulSets", "Helm Charts", "HPA (Horizontal Pod Autoscaler)", "RBAC"
        ],
        "AWS": [
            "EC2", "S3", "Lambda", "IAM", "VPC", "ECS/EKS", "RDS",
            "CloudFront", "DynamoDB", "SQS/SNS"
        ],
        "Azure": [
            "Azure VMs", "Blob Storage", "Azure Functions", "Azure Entra ID (Azure AD)",
            "Virtual Networks (VNet)", "AKS", "App Service", "Azure DevOps"
        ],
        "GCP": [
            "Compute Engine", "Cloud Storage (GCS)", "Cloud Functions", "Cloud Run",
            "GKE", "BigQuery", "IAM", "VPC Network"
        ],
        "CI/CD": [
            "Automated Testing", "Pipeline Configuration", "Deployment Strategies (Blue/Green, Canary)",
            "Artifact Management", "Release Automation", "Build Triggers", "Environment Secrets"
        ],
        "Terraform": [
            "HCL Syntax", "State Management", "Providers & Resources", "Terraform Modules",
            "Variables & Outputs", "Terraform Plan/Apply", "Remote Backends", "Drift Detection"
        ],
        "Linux": [
            "Shell Scripting", "Process Management", "File Permissions", "Systemd Services",
            "Networking Tools (curl, netstat, iptables)", "Memory & CPU Monitoring",
            "Package Managers", "Cron Jobs"
        ],
    },

    # ── 7. AI, ML & Data Science ─────────────────────────────────────────────
    "AI, ML & Data Science": {
        "Machine Learning": [
            "Supervised Learning", "Unsupervised Learning", "Regression", "Classification",
            "Decision Trees & Random Forests", "Support Vector Machines (SVM)",
            "Cross-Validation", "Hyperparameter Tuning", "Bias-Variance Tradeoff", "Feature Engineering"
        ],
        "Deep Learning": [
            "Feedforward Networks", "Backpropagation", "Gradient Descent & Optimizers",
            "Activation Functions", "Regularization (Dropout, L1/L2)", "Batch Normalization",
            "Loss Functions", "Model Architecture"
        ],
        "Natural Language Processing": [
            "Tokenization", "Stemming and Lemmatization", "TF-IDF", "Word Embeddings (Word2Vec, GloVe)",
            "Named Entity Recognition (NER)", "Transformers", "BERT", "Text Classification", "Sentiment Analysis"
        ],
        "Computer Vision": [
            "Image Processing", "Convolutional Neural Networks (CNN)", "Object Detection (YOLO, Faster R-CNN)",
            "Image Segmentation", "OpenCV", "Data Augmentation", "Transfer Learning", "Feature Extraction"
        ],
        "Large Language Models": [
            "Prompt Engineering", "Fine-Tuning (LoRA, QLoRA)", "Retrieval Augmented Generation (RAG)",
            "Vector Databases", "Embeddings", "In-Context Learning", "Attention Mechanism", "Context Window Management"
        ],
        "PyTorch": [
            "Tensors", "Autograd", "nn.Module", "DataLoaders", "Loss Functions & Optimizers",
            "GPU Acceleration (CUDA)", "Model Checkpointing", "TorchScript"
        ],
        "TensorFlow": [
            "Tensors & Computation Graphs", "Keras API", "Data Pipelines (tf.data)",
            "Callbacks", "Model Export & Serving", "TensorBoard", "Distributed Training"
        ],
        "Pandas": [
            "DataFrames and Series", "Data Cleaning and Missing Values", "GroupBy and Aggregations",
            "Merging and Joining", "Reshaping and Pivoting", "Time Series Analysis",
            "Data Filtering", "Performance Vectorization"
        ],
        "Data Science": [
            "Exploratory Data Analysis (EDA)", "Statistical Testing", "Hypothesis Testing",
            "Data Visualization", "Data Preprocessing", "Feature Selection",
            "Correlation Analysis", "Dimensionality Reduction (PCA)"
        ],
    },

    # ── 8. Mobile Development ────────────────────────────────────────────────
    "Mobile Development": {
        "React Native": [
            "Native Components", "JSX & Styling", "React Navigation", "Bridge Architecture",
            "Native Modules", "AsyncStorage", "Hermes Engine", "Expo"
        ],
        "Flutter": [
            "Dart Language", "Widgets (Stateless & Stateful)", "State Management (Provider, Bloc, Riverpod)",
            "Flutter Engine", "Navigation & Routing", "Animations", "Platform Channels"
        ],
        "Android": [
            "Activities & Fragments", "Android Jetpack", "Jetpack Compose", "Coroutines & Flow",
            "ViewModel & LiveData", "Room Database", "Intent & Manifest", "Gradle Build System"
        ],
        "iOS": [
            "Swift Language", "SwiftUI", "UIKit", "View Controllers", "Auto Layout",
            "Combine Framework", "Core Data", "Memory Management (ARC)"
        ],
    },

    # ── 9. Software Engineering & Practices ───────────────────────────────────
    "Software Engineering & Practices": {
        "Git": [
            "Branching & Merging", "Rebase", "Commit History", "Merge Conflicts",
            "Git Flow", "Cherry-pick", "Stashing", "Submodules", "Pull Requests"
        ],
        "Unit Testing": [
            "Test Case Design", "Assertions", "Mocks and Stubs", "Test Fixtures",
            "Parametrized Tests", "Code Coverage", "TDD (Test-Driven Development)", "Edge Case Testing"
        ],
        "Agile & Scrum": [
            "Sprint Planning", "Daily Standup", "Retrospectives", "User Stories",
            "Backlog Grooming", "Velocity & Burndown", "Kanban Boards", "Estimation"
        ],
        "CI/CD Practices": [
            "Continuous Integration", "Continuous Delivery", "Continuous Deployment",
            "Smoke Testing", "Rollback Procedures", "Feature Flags", "Staging Environments"
        ],
        "Design Patterns": [
            "Creational Patterns (Singleton, Factory, Builder)", "Structural Patterns (Adapter, Decorator, Facade)",
            "Behavioral Patterns (Observer, Strategy, Command)", "MVC & MVVM",
            "Repository Pattern", "Dependency Inversion"
        ],
        "Clean Code & Architecture": [
            "SOLID Principles", "DRY & KISS", "Code Refactoring", "Separation of Concerns",
            "Error Handling & Logging", "Code Reviews", "Documentation & Readability"
        ],
        "Software Engineering": [
            "OOP", "Clean Code", "Design Patterns", "Unit Testing",
            "Git", "Agile & Scrum", "Refactoring", "CI/CD Practices"
        ],
    },
}

# ── Skill Aliases & Acronyms Mapping ─────────────────────────────────────────

SKILL_ALIASES: Dict[str, str] = {
    # Core CS & Foundations
    "Data Structures & Algorithms": "DSA",
    "Data Structures and Algorithms": "DSA",
    "Data Structures": "DSA",
    "Algorithms": "DSA",
    "dsa": "DSA",
    "OOPS": "OOP",
    "Object-Oriented Programming": "OOP",
    "Object Oriented Programming": "OOP",
    "oop": "OOP",
    "oops": "OOP",
    "System Architecture": "System Design",
    "Distributed Systems": "System Design",
    "sys design": "System Design",
    "system design": "System Design",
    "OS": "Operating Systems",
    "Operating System": "Operating Systems",
    "os": "Operating Systems",
    "CN": "Computer Networks",
    "Networking": "Computer Networks",
    "Computer Network": "Computer Networks",
    "cn": "Computer Networks",
    "Database Management Systems": "DBMS",
    "Database Management System": "DBMS",
    "dbms": "DBMS",

    # Programming Languages
    "JS": "JavaScript",
    "javascript": "JavaScript",
    "ES6": "JavaScript",
    "TS": "TypeScript",
    "typescript": "TypeScript",
    "Golang": "Go",
    "golang": "Go",
    "go": "Go",
    "py": "Python",
    "python": "Python",
    "cpp": "C++",
    "c++": "C++",
    "c#": "C#",
    "csharp": "C#",
    "Structured Query Language": "SQL",
    "sql": "SQL",

    # Frontend
    "React.js": "React",
    "ReactJS": "React",
    "react": "React",
    "NextJS": "Next.js",
    "Next": "Next.js",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "Next 13": "Next.js",
    "Next 14": "Next.js",
    "Vue.js": "Vue",
    "VueJS": "Vue",
    "Vue 3": "Vue",
    "vue": "Vue",
    "AngularJS": "Angular",
    "angular": "Angular",
    "HTML": "HTML/CSS",
    "CSS": "HTML/CSS",
    "HTML5": "HTML/CSS",
    "CSS3": "HTML/CSS",
    "Tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "tailwind": "Tailwind CSS",
    "Redux Toolkit": "Redux",
    "RTK": "Redux",

    # Backend
    "Fast API": "FastAPI",
    "fastapi": "FastAPI",
    "NodeJS": "Node.js",
    "Node": "Node.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "Express.js": "Express",
    "ExpressJS": "Express",
    "express": "Express",
    "DRF": "Django",
    "Django Rest Framework": "Django",
    "SpringBoot": "Spring Boot",
    "spring boot": "Spring Boot",
    "Spring": "Spring Boot",
    "graphql": "GraphQL",
    "REST": "REST APIs",
    "REST API": "REST APIs",
    "RESTful": "REST APIs",

    # Databases
    "Postgres": "PostgreSQL",
    "PSQL": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "Mongo": "MongoDB",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "Elastic Search": "Elasticsearch",
    "Elastic": "Elasticsearch",
    "elasticsearch": "Elasticsearch",

    # Cloud & DevOps
    "K8s": "Kubernetes",
    "k8s": "Kubernetes",
    "kube": "Kubernetes",
    "Containerization": "Docker",
    "docker": "Docker",
    "Amazon Web Services": "AWS",
    "aws": "AWS",
    "Google Cloud": "GCP",
    "Google Cloud Platform": "GCP",
    "gcp": "GCP",
    "Microsoft Azure": "Azure",
    "azure": "Azure",
    "CICD": "CI/CD",
    "ci/cd": "CI/CD",

    # AI / ML
    "ML": "Machine Learning",
    "machine learning": "Machine Learning",
    "DL": "Deep Learning",
    "deep learning": "Deep Learning",
    "NLP": "Natural Language Processing",
    "Natural Language Processing (NLP)": "Natural Language Processing",
    "nlp": "Natural Language Processing",
    "CV": "Computer Vision",
    "cv": "Computer Vision",
    "LLM": "Large Language Models",
    "LLMs": "Large Language Models",
    "GenAI": "Large Language Models",
    "Generative AI": "Large Language Models",
    "llm": "Large Language Models",
    "TF": "TensorFlow",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",

    # Mobile
    "RN": "React Native",
    "react native": "React Native",
    "Android Development": "Android",
    "android": "Android",
    "iOS Development": "iOS",
    "ios": "iOS",

    # Practices
    "Testing": "Unit Testing",
    "Pytest": "Unit Testing",
    "Unittest": "Unit Testing",
    "unit testing": "Unit Testing",
    "Design Pattern": "Design Patterns",
    "Software Design Patterns": "Design Patterns",
    "Clean Code": "Clean Code & Architecture",
    "Software Architecture": "Clean Code & Architecture",
    "Datascience": "Data Science",
    "datascience": "Data Science",
    "data science": "Data Science",
    "mix skill": "Software Engineering",
    "mix skills": "Software Engineering",
    "Mix Skills": "Software Engineering",
    "software engineering": "Software Engineering",
}

# ── Precomputed Lookup Maps ──────────────────────────────────────────────────

# Map lowercase query -> (canonical_skill_name, domain_name)
_SKILL_TO_DOMAIN_MAP: Dict[str, Tuple[str, str]] = {}
# Map lowercase subtopic -> domain_name
_SUBTOPIC_TO_DOMAIN_MAP: Dict[str, str] = {}
# Map lowercase subtopic -> canonical_skill_name
_SUBTOPIC_TO_SKILL_MAP: Dict[str, str] = {}

for domain, skills_dict in SKILL_TAXONOMY.items():
    for canonical_skill, subtopics in skills_dict.items():
        # Canonical skill lookup
        _SKILL_TO_DOMAIN_MAP[canonical_skill.strip().lower()] = (canonical_skill, domain)
        for sub in subtopics:
            sub_key = sub.strip().lower()
            if sub_key not in _SUBTOPIC_TO_DOMAIN_MAP:
                _SUBTOPIC_TO_DOMAIN_MAP[sub_key] = domain
            if sub_key not in _SUBTOPIC_TO_SKILL_MAP:
                _SUBTOPIC_TO_SKILL_MAP[sub_key] = canonical_skill

for alias, canonical_target in SKILL_ALIASES.items():
    lower_alias = alias.strip().lower()
    lower_target = canonical_target.strip().lower()
    if lower_target in _SKILL_TO_DOMAIN_MAP:
        canonical_name, domain = _SKILL_TO_DOMAIN_MAP[lower_target]
        _SKILL_TO_DOMAIN_MAP[lower_alias] = (canonical_name, domain)


# ── Public API Functions ─────────────────────────────────────────────────────

def get_subtopics(skill_name: Optional[str]) -> List[str]:
    """
    Given any resume skill or alias (e.g. 'DSA', 'Data Structures & Algorithms'),
    returns its list of subtopics. Case-insensitive. Returns [] if not found.
    """
    if not skill_name or not isinstance(skill_name, str):
        return []
    key = skill_name.strip().lower()
    if key in _SKILL_TO_DOMAIN_MAP:
        canonical_skill, domain = _SKILL_TO_DOMAIN_MAP[key]
        return list(SKILL_TAXONOMY[domain][canonical_skill])
    return []


def get_domain(skill_name: Optional[str]) -> str:
    """
    Returns the top-level domain for a given skill, alias, or subtopic.
    Case-insensitive. Returns '' if not found.
    """
    if not skill_name or not isinstance(skill_name, str):
        return ""
    key = skill_name.strip().lower()
    # Check Level 2 skills & aliases first
    if key in _SKILL_TO_DOMAIN_MAP:
        return _SKILL_TO_DOMAIN_MAP[key][1]
    # Check Level 3 subtopics
    if key in _SUBTOPIC_TO_DOMAIN_MAP:
        return _SUBTOPIC_TO_DOMAIN_MAP[key]
    return ""


def get_all_skills_flat() -> List[str]:
    """
    Returns a sorted, deduplicated flat list of all recognizable skills,
    aliases, and subtopics for resume extraction.
    """
    skills_set = set()
    for domain, skills_dict in SKILL_TAXONOMY.items():
        for canonical_skill, subtopics in skills_dict.items():
            skills_set.add(canonical_skill)
            for sub in subtopics:
                skills_set.add(sub)
    for alias in SKILL_ALIASES.keys():
        skills_set.add(alias)
    return sorted(skills_set)


def get_canonical_skill(skill_name: Optional[str]) -> str:
    """
    Returns canonical Level 2 skill name if matched directly or via alias.
    Case-insensitive. Returns '' if not found.
    """
    if not skill_name or not isinstance(skill_name, str):
        return ""
    key = skill_name.strip().lower()
    if key in _SKILL_TO_DOMAIN_MAP:
        return _SKILL_TO_DOMAIN_MAP[key][0]
    return ""


def get_parent_skill(subtopic_name: Optional[str]) -> str:
    """
    Returns parent Level 2 skill for a given subtopic.
    Case-insensitive. Returns '' if not found.
    """
    if not subtopic_name or not isinstance(subtopic_name, str):
        return ""
    key = subtopic_name.strip().lower()
    if key in _SUBTOPIC_TO_SKILL_MAP:
        return _SUBTOPIC_TO_SKILL_MAP[key]
    return ""
