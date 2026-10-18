"""Authored learning-topic catalog: practice recipes, prerequisites and resources.

These entries are team-authored study guidance. They are not source requirements,
skill assessments or claims about any program's syllabus. The graph records which
topics a target's facts map to and traverses prerequisite edges; this module owns
the reviewed vocabulary, the authored practice estimates and the starting
resources. Prerequisites are learning-order advice, not eligibility rules.
"""

from __future__ import annotations

import re

from app.models import Opportunity

# Fact fields whose list values are scanned for topics. Identical to the fields
# the preparation recipes treat as skill/qualification lists.
SKILL_FIELDS = {
    "skills", "preferred_skills", "technical_skills", "preferred_technical_skills", "programming_languages",
    "preferred_programming_languages", "cs_topics", "preferred_cs_topics", "tools", "preferred_tools",
}

# Reviewed topics. practice = (title, low hours, high hours) used by shared
# foundation tasks; prerequisites reference other catalog keys; resources are
# team-authored starting points (not fetched or verified in this app).
TOPIC_CATALOG: dict[str, dict] = {
    "programming": {
        "title": "Programming fundamentals", "family": "Programming", "prerequisites": [],
        "practice": ("Implement and test a small program in a language you choose", 2.0, 4.0),
        "resources": [
            {"title": "CS50: Introduction to Computer Science (free)", "url": "https://cs50.harvard.edu/x/"},
            {"title": "Exercism: practice tracks in many languages", "url": "https://exercism.org/"},
        ],
    },
    "python": {
        "title": "Python", "family": "Programming", "prerequisites": [],
        "practice": ("Practice Python with a small tested exercise", 2.0, 4.0),
        "resources": [
            {"title": "Python official tutorial", "url": "https://docs.python.org/3/tutorial/"},
            {"title": "Exercism: Python track", "url": "https://exercism.org/tracks/python"},
            {"title": "Automate the Boring Stuff with Python", "url": "https://automatetheboringstuff.com/"},
        ],
    },
    "java": {
        "title": "Java", "family": "Programming", "prerequisites": [],
        "practice": ("Practice Java with a small tested exercise", 2.0, 4.0),
        "resources": [
            {"title": "Dev.java: Learn Java", "url": "https://dev.java/learn/"},
            {"title": "Exercism: Java track", "url": "https://exercism.org/tracks/java"},
        ],
    },
    "cpp": {
        "title": "C++", "family": "Programming", "prerequisites": [],
        "practice": ("Practice C++ with a small tested exercise", 2.0, 4.0),
        "resources": [
            {"title": "LearnCpp.com tutorial", "url": "https://www.learncpp.com/"},
            {"title": "cppreference", "url": "https://en.cppreference.com/w/"},
        ],
    },
    "c": {
        "title": "C", "family": "Programming", "prerequisites": [],
        "practice": ("Practice C with a small tested exercise", 2.0, 4.0),
        "resources": [
            {"title": "C reference (cppreference)", "url": "https://en.cppreference.com/w/c"},
            {"title": "Learn-C.org interactive tutorial", "url": "https://www.learn-c.org/"},
        ],
    },
    "javascript": {
        "title": "JavaScript", "family": "Programming", "prerequisites": [],
        "practice": ("Practice JavaScript with a small tested exercise", 2.0, 4.0),
        "resources": [
            {"title": "MDN: Learn web development", "url": "https://developer.mozilla.org/en-US/docs/Learn_web_development"},
            {"title": "javascript.info", "url": "https://javascript.info/"},
        ],
    },
    "typescript": {
        "title": "TypeScript", "family": "Programming", "prerequisites": [],
        "practice": ("Practice TypeScript with a small tested exercise", 2.0, 4.0),
        "resources": [
            {"title": "TypeScript handbook", "url": "https://www.typescriptlang.org/docs/handbook/intro.html"},
        ],
    },
    "algorithms": {
        "title": "Algorithms", "family": "CS fundamentals", "prerequisites": ["programming"],
        "practice": ("Practice explaining and testing two basic algorithms", 2.0, 4.0),
        "resources": [
            {"title": "Khan Academy: Algorithms", "url": "https://www.khanacademy.org/computing/computer-science/algorithms"},
            {"title": "Algorithms, 4th edition (companion site)", "url": "https://algs4.cs.princeton.edu/home/"},
        ],
    },
    "data_structures": {
        "title": "Data structures", "family": "CS fundamentals", "prerequisites": ["programming"],
        "practice": ("Practice choosing and testing basic data structures", 2.0, 4.0),
        "resources": [
            {"title": "VisuAlgo: visualise data structures", "url": "https://visualgo.net/en"},
            {"title": "Hello Algo (free book)", "url": "https://www.hello-algo.com/en/"},
        ],
    },
    "complexity": {
        "title": "Complexity analysis", "family": "CS fundamentals", "prerequisites": ["algorithms"],
        "practice": ("Practice time and space complexity explanations for example code", 1.0, 2.0),
        "resources": [
            {"title": "Big-O cheat sheet", "url": "https://www.bigocheatsheet.com/"},
        ],
    },
    "object_oriented_programming": {
        "title": "Object-oriented programming", "family": "CS fundamentals", "prerequisites": ["programming"],
        "practice": ("Practice object-oriented design in a small example", 1.0, 2.0),
        "resources": [
            {"title": "Python tutorial: classes", "url": "https://docs.python.org/3/tutorial/classes.html"},
        ],
    },
    "object_oriented_design": {
        "title": "Object-oriented design", "family": "CS fundamentals", "prerequisites": ["object_oriented_programming"],
        "practice": ("Practice explaining object-oriented design choices in a small example", 1.0, 2.0),
        "resources": [
            {"title": "Refactoring Guru: design patterns", "url": "https://refactoring.guru/design-patterns"},
        ],
    },
    "sql": {
        "title": "SQL", "family": "Data & AI", "prerequisites": [],
        "practice": ("Practice SQL queries against a small sample dataset", 1.0, 2.0),
        "resources": [
            {"title": "SQLBolt interactive lessons", "url": "https://sqlbolt.com/"},
            {"title": "Mode Analytics SQL tutorial", "url": "https://mode.com/sql-tutorial/"},
        ],
    },
    "git": {
        "title": "Git", "family": "Process & tools", "prerequisites": [],
        "practice": ("Practice a small Git change and review workflow", 0.5, 1.0),
        "resources": [
            {"title": "Pro Git (free book)", "url": "https://git-scm.com/book/en/v2"},
            {"title": "Learn Git Branching (interactive)", "url": "https://learngitbranching.js.org/"},
        ],
    },
    "software_testing": {
        "title": "Software testing", "family": "Process & tools", "prerequisites": [],
        "practice": ("Practice writing tests and recording their limitations", 1.0, 2.0),
        "resources": [
            {"title": "The Practical Test Pyramid", "url": "https://martinfowler.com/articles/practical-test-pyramid.html"},
        ],
    },
    "linux": {
        "title": "Linux command line", "family": "Systems & tools", "prerequisites": [],
        "practice": ("Practice Linux command-line basics with a small exercise", 1.0, 2.0),
        "resources": [
            {"title": "Linux Journey", "url": "https://linuxjourney.com/"},
            {"title": "The Linux Command Line (free book)", "url": "https://linuxcommand.org/tlcl.php"},
        ],
    },
    "docker": {
        "title": "Docker & containers", "family": "Systems & tools", "prerequisites": ["linux"],
        "practice": ("Package and run a small app with Docker", 1.0, 2.0),
        "resources": [
            {"title": "Docker: Getting started", "url": "https://docs.docker.com/get-started/"},
        ],
    },
    "cloud_computing": {
        "title": "Cloud computing", "family": "Systems & tools", "prerequisites": ["linux"],
        "practice": ("Deploy a small sample using one cloud provider's getting-started guide", 2.0, 4.0),
        "resources": [
            {"title": "AWS Skill Builder (free tier)", "url": "https://skillbuilder.aws/"},
            {"title": "Google Cloud Skills Boost", "url": "https://www.cloudskillsboost.google/"},
        ],
    },
    "statistics": {
        "title": "Statistics", "family": "Data & AI", "prerequisites": [],
        "practice": ("Summarize a small dataset with basic statistics", 2.0, 4.0),
        "resources": [
            {"title": "Khan Academy: Statistics and probability", "url": "https://www.khanacademy.org/math/statistics-probability"},
        ],
    },
    "data_analysis": {
        "title": "Data analysis (Python)", "family": "Data & AI", "prerequisites": ["python", "statistics"],
        "practice": ("Analyze a small dataset with a Python data tool", 2.0, 4.0),
        "resources": [
            {"title": "pandas: getting started", "url": "https://pandas.pydata.org/docs/getting_started/index.html"},
            {"title": "Python for Data Analysis (free online book)", "url": "https://wesmckinney.com/book/"},
        ],
    },
    "machine_learning": {
        "title": "Machine learning", "family": "Data & AI", "prerequisites": ["python", "statistics", "data_structures"],
        "practice": ("Train and evaluate a small model on a toy dataset", 3.0, 6.0),
        "resources": [
            {"title": "scikit-learn: getting started", "url": "https://scikit-learn.org/stable/getting_started.html"},
            {"title": "Google: Machine Learning Crash Course", "url": "https://developers.google.com/machine-learning/crash-course"},
        ],
    },
    "deep_learning": {
        "title": "Deep learning", "family": "Data & AI", "prerequisites": ["machine_learning"],
        "practice": ("Work through one introduction-to-deep-learning lesson", 3.0, 6.0),
        "resources": [
            {"title": "fast.ai: Practical Deep Learning", "url": "https://course.fast.ai/"},
            {"title": "3Blue1Brown: Neural networks", "url": "https://www.3blue1brown.com/topics/neural-networks"},
        ],
    },
    "web_development": {
        "title": "Web development", "family": "Programming", "prerequisites": ["javascript"],
        "practice": ("Build a small interactive web page and explain its structure", 2.0, 4.0),
        "resources": [
            {"title": "MDN: Learn web development", "url": "https://developer.mozilla.org/en-US/docs/Learn_web_development"},
            {"title": "freeCodeCamp: Responsive Web Design", "url": "https://www.freecodecamp.org/learn/2022/responsive-web-design/"},
        ],
    },
}

# Recipes keep their established task titles and hour ranges; derive them from
# the catalog so a single authored source stays authoritative.
SKILL_FOUNDATIONS: dict[str, tuple[str, float, float]] = {
    key: entry["practice"] for key, entry in TOPIC_CATALOG.items()
}

SKILL_ALIASES = {
    "c++": "cpp", "c plus plus": "cpp", "js": "javascript", "ts": "typescript",
    "general purpose programming": "programming", "general purpose programming language": "programming",
    "general purpose programming languages": "programming", "programming fundamentals": "programming",
    "algorithm": "algorithms", "data structure": "data_structures", "data structures": "data_structures",
    "algorithm design": "algorithms",
    "complexity analysis": "complexity", "time complexity": "complexity", "space complexity": "complexity",
    "object oriented programming": "object_oriented_programming", "oop": "object_oriented_programming",
    "object oriented design": "object_oriented_design",
    "software testing": "software_testing",
    "ml": "machine_learning", "artificial intelligence": "machine_learning", "ai": "machine_learning",
    "neural network": "deep_learning", "neural networks": "deep_learning",
    "tensorflow": "deep_learning", "pytorch": "deep_learning",
    "data science": "data_analysis", "data analytics": "data_analysis", "pandas": "data_analysis",
    "numpy": "data_analysis", "matplotlib": "data_analysis", "data visualization": "data_analysis",
    "statistical analysis": "statistics", "probability": "statistics",
    "unix": "linux", "bash": "linux", "shell": "linux", "shell scripting": "linux",
    "containers": "docker", "containerization": "docker",
    "cloud": "cloud_computing", "aws": "cloud_computing", "azure": "cloud_computing",
    "gcp": "cloud_computing", "google cloud": "cloud_computing", "amazon web services": "cloud_computing",
    "microsoft azure": "cloud_computing",
    "webdev": "web_development", "web dev": "web_development", "html": "web_development",
    "css": "web_development", "html/css": "web_development", "react": "web_development",
    "frontend": "web_development", "front end": "web_development", "node": "web_development",
    "nodejs": "web_development", "node.js": "web_development", "django": "web_development",
    "flask": "web_development",
    "database": "sql", "databases": "sql", "mysql": "sql", "postgres": "sql",
    "postgresql": "sql", "sqlite": "sql",
}

_ALTERNATIVES = re.compile(r"\b(?:one of|at least one|such as|e\.g|or)\b", re.I)


def catalog_key(value: str) -> str | None:
    """Map one source label to a reviewed topic key, or None when unreviewed."""
    normalized = re.sub(r"[-_\s]+", " ", value.casefold()).strip()
    key = SKILL_ALIASES.get(normalized, normalized.replace(" ", "_"))
    return key if key in TOPIC_CATALOG else None


def fact_topic_keys(name: str, value: object, excerpt: str) -> list[str]:
    """Reviewed topics for one skill-list fact, mirroring the recipes' rule.

    When the source lists language alternatives ("Java or Python"), reviewed
    language options collapse to the language-neutral programming topic and no
    single listed language is treated as mandatory.
    """
    if not (isinstance(value, list) and value and all(isinstance(item, str) and item.strip() for item in value)):
        return []
    items = list(dict.fromkeys(value))
    if "programming_languages" in name and _ALTERNATIVES.search(excerpt or ""):
        if any(catalog_key(item) for item in items):
            return ["programming"]
    keys: list[str] = []
    for item in items:
        key = catalog_key(item)
        if key and key not in keys:
            keys.append(key)
    return keys


def topic_keys_for(opportunity: Opportunity) -> list[str]:
    """Directly required reviewed topics across the opportunity's skill facts."""
    keys: list[str] = []
    for fact in opportunity.facts:
        if fact.name not in SKILL_FIELDS or fact.status != "known" or not fact.excerpt.strip():
            continue
        for key in fact_topic_keys(fact.name, fact.value, fact.excerpt):
            if key not in keys:
                keys.append(key)
    return keys


def fact_topic_links(opportunity: Opportunity) -> list[dict]:
    """Graph links from each skill fact to its directly reviewed topics."""
    links: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for fact in opportunity.facts:
        if fact.name not in SKILL_FIELDS or fact.status != "known" or not fact.excerpt.strip():
            continue
        for key in fact_topic_keys(fact.name, fact.value, fact.excerpt):
            pair = (fact.name, key)
            if pair in seen:
                continue
            seen.add(pair)
            links.append({"fact_id": f"{opportunity.id}/{fact.name}", "topic_key": key})
    return links


def prerequisite_closure(keys: list[str]) -> list[str]:
    """All keys plus their prerequisite closure, dependencies first (stable)."""
    ordered: list[str] = []
    seen: set[str] = set()

    def visit(key: str, stack: set[str]) -> None:
        if key in seen or key in stack or key not in TOPIC_CATALOG:
            return
        stack.add(key)
        for prerequisite in TOPIC_CATALOG[key]["prerequisites"]:
            visit(prerequisite, stack)
        stack.discard(key)
        if key not in seen:
            seen.add(key)
            ordered.append(key)

    for key in keys:
        visit(key, set())
    return ordered


def catalog_rows(keys: list[str]) -> dict:
    """Graph write rows for the reviewed topics, their resources and prereq edges."""
    topics = []
    resources = []
    edges = []
    for key in keys:
        entry = TOPIC_CATALOG.get(key)
        if entry is None:
            continue
        title, _low, _high = entry["practice"]
        topics.append({
            "key": key, "title": entry["title"], "family": entry["family"],
            "prerequisites": [p for p in entry["prerequisites"] if p in TOPIC_CATALOG],
            "resources": entry["resources"],
        })
        for prerequisite in entry["prerequisites"]:
            if prerequisite in TOPIC_CATALOG:
                edges.append({"topic": key, "prerequisite": prerequisite})
        for resource in entry["resources"]:
            slug = re.sub(r"[^a-z0-9]+", "-", resource["url"].casefold()).strip("-")[:80]
            resources.append({
                "id": f"{key}/{slug}", "topic": key, "title": resource["title"],
                "url": resource["url"], "provenance": "authored_guide",
            })
    return {"topics": topics, "resources": resources, "edges": edges}
