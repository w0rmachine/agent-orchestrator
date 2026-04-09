"""Tests for repository analyzer."""

import json
import tempfile
from pathlib import Path

import pytest

from backend.repo_analyzer import RepoAnalyzer


@pytest.fixture
def temp_repo():
    """Create a temporary directory for test repositories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_empty_repo(temp_repo):
    """Test analyzer on empty repository."""
    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()
    assert tech_stack == []


def test_python_pyproject_toml(temp_repo):
    """Test Python detection via pyproject.toml."""
    pyproject = temp_repo / "pyproject.toml"
    pyproject.write_text("""
[project]
name = "test-project"
dependencies = [
    "fastapi>=0.100.0",
    "sqlmodel>=0.0.14",
    "pytest>=8.0.0",
]
""")

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "Python" in tech_stack
    assert "FastAPI" in tech_stack
    assert "SQLModel" in tech_stack
    assert "pytest" in tech_stack


def test_python_requirements_txt(temp_repo):
    """Test Python detection via requirements.txt."""
    requirements = temp_repo / "requirements.txt"
    requirements.write_text("""
flask==2.3.0
sqlalchemy>=2.0.0
requests>=2.31.0
# Comment line
pytest>=8.0.0
""")

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "Python" in tech_stack
    assert "Flask" in tech_stack
    assert "SQLAlchemy" in tech_stack
    assert "pytest" in tech_stack
    assert "requests" in tech_stack


def test_python_poetry(temp_repo):
    """Test Python detection via Poetry in pyproject.toml."""
    pyproject = temp_repo / "pyproject.toml"
    pyproject.write_text("""
[tool.poetry]
name = "test-project"

[tool.poetry.dependencies]
python = "^3.11"
django = "^4.2.0"
pydantic = "^2.0.0"

[tool.poetry.dev-dependencies]
pytest = "^8.0.0"
""")

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "Python" in tech_stack
    assert "Django" in tech_stack
    assert "Pydantic" in tech_stack
    assert "pytest" in tech_stack


def test_javascript_package_json(temp_repo):
    """Test JavaScript detection via package.json."""
    package_json = temp_repo / "package.json"
    package_json.write_text(json.dumps({
        "name": "test-app",
        "dependencies": {
            "react": "^18.2.0",
            "express": "^4.18.0",
        },
        "devDependencies": {
            "vite": "^5.0.0",
        }
    }))

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "JavaScript" in tech_stack
    assert "React" in tech_stack
    assert "Express" in tech_stack
    assert "Vite" in tech_stack


def test_typescript_detection(temp_repo):
    """Test TypeScript detection."""
    package_json = temp_repo / "package.json"
    package_json.write_text(json.dumps({
        "name": "test-app",
        "dependencies": {
            "react": "^18.2.0",
        },
        "devDependencies": {
            "typescript": "^5.0.0",
            "vite": "^5.0.0",
        }
    }))

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "TypeScript" in tech_stack
    assert "JavaScript" not in tech_stack  # Should be TypeScript, not JavaScript
    assert "React" in tech_stack
    assert "Vite" in tech_stack


def test_nextjs_detection(temp_repo):
    """Test Next.js detection."""
    package_json = temp_repo / "package.json"
    package_json.write_text(json.dumps({
        "name": "test-app",
        "dependencies": {
            "react": "^18.2.0",
            "next": "^14.0.0",
        }
    }))

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "JavaScript" in tech_stack
    assert "React" in tech_stack
    assert "Next.js" in tech_stack


def test_rust_cargo_toml(temp_repo):
    """Test Rust detection via Cargo.toml."""
    cargo_toml = temp_repo / "Cargo.toml"
    cargo_toml.write_text("""
[package]
name = "test-app"
version = "0.1.0"

[dependencies]
tokio = { version = "1.0", features = ["full"] }
axum = "0.7"
serde = { version = "1.0", features = ["derive"] }
""")

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "Rust" in tech_stack
    assert "Tokio" in tech_stack
    assert "Axum" in tech_stack
    assert "Serde" in tech_stack


def test_go_detection(temp_repo):
    """Test Go detection via go.mod."""
    go_mod = temp_repo / "go.mod"
    go_mod.write_text("""
module example.com/myapp

go 1.21

require (
    github.com/gin-gonic/gin v1.9.1
    gorm.io/gorm v1.25.5
)
""")

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "Go" in tech_stack
    assert "Gin" in tech_stack
    assert "GORM" in tech_stack


def test_ruby_gemfile(temp_repo):
    """Test Ruby detection via Gemfile."""
    gemfile = temp_repo / "Gemfile"
    gemfile.write_text("""
source 'https://rubygems.org'

gem 'rails', '~> 7.0'
gem 'pg', '~> 1.5'
""")

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "Ruby" in tech_stack
    assert "Rails" in tech_stack


def test_php_composer_json(temp_repo):
    """Test PHP detection via composer.json."""
    composer_json = temp_repo / "composer.json"
    composer_json.write_text(json.dumps({
        "name": "test/app",
        "require": {
            "php": "^8.2",
            "laravel/framework": "^10.0"
        }
    }))

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "PHP" in tech_stack
    assert "Laravel" in tech_stack


def test_java_maven(temp_repo):
    """Test Java detection via pom.xml."""
    pom_xml = temp_repo / "pom.xml"
    pom_xml.write_text("""
<?xml version="1.0" encoding="UTF-8"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>demo</artifactId>
    <version>0.0.1-SNAPSHOT</version>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
    </dependencies>
</project>
""")

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "Java" in tech_stack
    assert "Maven" in tech_stack
    assert "Spring Boot" in tech_stack


def test_java_gradle(temp_repo):
    """Test Java detection via build.gradle."""
    build_gradle = temp_repo / "build.gradle"
    build_gradle.write_text("""
plugins {
    id 'java'
    id 'org.springframework.boot' version '3.2.0'
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
}
""")

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "Java" in tech_stack
    assert "Gradle" in tech_stack


def test_multi_language_repo(temp_repo):
    """Test repository with multiple languages."""
    # Python backend
    requirements = temp_repo / "requirements.txt"
    requirements.write_text("fastapi>=0.100.0\nuvicorn>=0.24.0")

    # JavaScript frontend
    package_json = temp_repo / "package.json"
    package_json.write_text(json.dumps({
        "dependencies": {
            "react": "^18.2.0",
            "vite": "^5.0.0",
        },
        "devDependencies": {
            "typescript": "^5.0.0",
        }
    }))

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    # Should detect both stacks
    assert "Python" in tech_stack
    assert "FastAPI" in tech_stack
    assert "TypeScript" in tech_stack
    assert "React" in tech_stack
    assert "Vite" in tech_stack


def test_file_tree_summary(temp_repo):
    """Test file tree summary generation."""
    # Create directory structure
    (temp_repo / "src").mkdir()
    (temp_repo / "src" / "main.py").write_text("# Main file")
    (temp_repo / "src" / "utils.py").write_text("# Utils")
    (temp_repo / "tests").mkdir()
    (temp_repo / "tests" / "test_main.py").write_text("# Tests")
    (temp_repo / "README.md").write_text("# Readme")
    (temp_repo / ".github").mkdir()
    (temp_repo / ".github" / "workflows").mkdir()

    analyzer = RepoAnalyzer(temp_repo)
    summary = analyzer.get_file_tree_summary()

    assert summary["file_count"] >= 3
    assert summary["dir_count"] >= 2
    assert ".py" in summary["extensions"]
    assert ".md" in summary["extensions"]
    assert "src/" in summary["top_level"]
    assert "tests/" in summary["top_level"]
    assert "README.md" in summary["top_level"]


def test_file_tree_ignores_common_dirs(temp_repo):
    """Test that file tree summary ignores common directories."""
    # Create directories that should be ignored
    (temp_repo / "node_modules").mkdir()
    (temp_repo / "node_modules" / "pkg").mkdir()
    (temp_repo / "__pycache__").mkdir()
    (temp_repo / ".venv").mkdir()

    # Create actual project files
    (temp_repo / "src").mkdir()
    (temp_repo / "src" / "main.py").write_text("# Main")

    analyzer = RepoAnalyzer(temp_repo)
    summary = analyzer.get_file_tree_summary()

    # Should not include ignored directories in top level
    assert "node_modules/" not in summary["top_level"]
    assert "__pycache__/" not in summary["top_level"]
    assert ".venv/" not in summary["top_level"]
    assert "src/" in summary["top_level"]


def test_nonexistent_repo():
    """Test analyzer on non-existent repository."""
    analyzer = RepoAnalyzer("/nonexistent/path")
    tech_stack = analyzer.detect_tech_stack()
    assert tech_stack == []

    summary = analyzer.get_file_tree_summary()
    assert "error" in summary


def test_tech_stack_sorted():
    """Test that tech stack is always sorted."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)

        # Create files in random order
        requirements = repo / "requirements.txt"
        requirements.write_text("fastapi\ndjango\nflask")

        analyzer = RepoAnalyzer(repo)
        tech_stack = analyzer.detect_tech_stack()

        # Should be alphabetically sorted
        assert tech_stack == sorted(tech_stack)


def test_current_repo_detection():
    """Test detection on the current agent-orchestrator repo."""
    # This test uses the actual repo we're in
    current_repo = Path(__file__).parent.parent
    analyzer = RepoAnalyzer(current_repo)
    tech_stack = analyzer.detect_tech_stack()

    # Should detect Python and FastAPI at minimum
    assert "Python" in tech_stack
    assert "FastAPI" in tech_stack
    assert "SQLModel" in tech_stack or "Pydantic" in tech_stack

    # Likely has JavaScript/TypeScript frontend
    if (current_repo / "frontend" / "package.json").exists():
        assert "TypeScript" in tech_stack or "JavaScript" in tech_stack


def test_malformed_json_handling(temp_repo):
    """Test handling of malformed JSON files."""
    package_json = temp_repo / "package.json"
    package_json.write_text("{ invalid json")

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    # Should not crash, just return empty
    assert tech_stack == []


def test_malformed_toml_handling(temp_repo):
    """Test handling of malformed TOML files."""
    cargo_toml = temp_repo / "Cargo.toml"
    cargo_toml.write_text("[invalid toml\nmissing closing bracket")

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    # Should still detect Rust (file exists) but not crash
    assert "Rust" in tech_stack


def test_tailwind_detection(temp_repo):
    """Test Tailwind CSS detection."""
    package_json = temp_repo / "package.json"
    package_json.write_text(json.dumps({
        "devDependencies": {
            "tailwindcss": "^3.4.0",
        }
    }))

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "Tailwind CSS" in tech_stack


def test_anthropic_sdk_detection(temp_repo):
    """Test Anthropic SDK detection (our use case!)."""
    requirements = temp_repo / "requirements.txt"
    requirements.write_text("anthropic>=0.34.0\nfastapi>=0.100.0")

    analyzer = RepoAnalyzer(temp_repo)
    tech_stack = analyzer.detect_tech_stack()

    assert "Python" in tech_stack
    assert "Anthropic SDK" in tech_stack
    assert "FastAPI" in tech_stack
