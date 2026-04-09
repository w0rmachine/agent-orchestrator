"""Repository analysis for tech stack detection."""

import json
import re
import tomllib
from pathlib import Path
from typing import Any


class RepoAnalyzer:
    """Analyzes repository structure to detect tech stack."""

    def __init__(self, repo_path: str | Path):
        """Initialize analyzer for a repository.

        Args:
            repo_path: Path to repository root
        """
        self.repo_path = Path(repo_path).expanduser().resolve()

    def detect_tech_stack(self) -> list[str]:
        """Detect technologies used in the repository.

        Returns:
            List of detected technologies (e.g., ["Python", "FastAPI", "React"])
        """
        if not self.repo_path.exists():
            return []

        tech_stack = set()

        # Language and framework detection
        tech_stack.update(self._detect_python())
        tech_stack.update(self._detect_javascript())
        tech_stack.update(self._detect_rust())
        tech_stack.update(self._detect_go())
        tech_stack.update(self._detect_ruby())
        tech_stack.update(self._detect_php())
        tech_stack.update(self._detect_java())

        # Sort for consistency
        return sorted(tech_stack)

    def _detect_python(self) -> set[str]:
        """Detect Python and its frameworks."""
        tech = set()

        # Check for Python project files
        pyproject = self.repo_path / "pyproject.toml"
        requirements = self.repo_path / "requirements.txt"
        pipfile = self.repo_path / "Pipfile"

        if not any([pyproject.exists(), requirements.exists(), pipfile.exists()]):
            return tech

        tech.add("Python")

        # Parse pyproject.toml
        if pyproject.exists():
            try:
                with open(pyproject, "rb") as f:
                    data = tomllib.load(f)
                    deps = self._extract_pyproject_deps(data)
                    tech.update(self._identify_python_frameworks(deps))
            except Exception:
                pass

        # Parse requirements.txt
        if requirements.exists():
            try:
                deps = self._parse_requirements_txt(requirements)
                tech.update(self._identify_python_frameworks(deps))
            except Exception:
                pass

        return tech

    def _extract_pyproject_deps(self, data: dict[str, Any]) -> set[str]:
        """Extract dependencies from pyproject.toml."""
        deps = set()

        # Poetry dependencies
        if "tool" in data and "poetry" in data["tool"]:
            poetry_deps = data["tool"]["poetry"].get("dependencies", {})
            deps.update(poetry_deps.keys())
            dev_deps = data["tool"]["poetry"].get("dev-dependencies", {})
            deps.update(dev_deps.keys())

        # PEP 621 dependencies
        if "project" in data:
            project_deps = data["project"].get("dependencies", [])
            for dep in project_deps:
                # Extract package name from "package>=1.0.0" format
                match = re.match(r"^([a-zA-Z0-9_-]+)", dep)
                if match:
                    deps.add(match.group(1))

        return deps

    def _parse_requirements_txt(self, filepath: Path) -> set[str]:
        """Parse requirements.txt file."""
        deps = set()
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Extract package name before version specifier
                match = re.match(r"^([a-zA-Z0-9_-]+)", line)
                if match:
                    deps.add(match.group(1))
        return deps

    def _identify_python_frameworks(self, deps: set[str]) -> set[str]:
        """Identify Python frameworks from dependency names."""
        frameworks = set()

        framework_map = {
            "fastapi": "FastAPI",
            "flask": "Flask",
            "django": "Django",
            "sqlmodel": "SQLModel",
            "sqlalchemy": "SQLAlchemy",
            "pydantic": "Pydantic",
            "pytest": "pytest",
            "typer": "Typer",
            "click": "Click",
            "uvicorn": "Uvicorn",
            "starlette": "Starlette",
            "asyncio": "asyncio",
            "aiohttp": "aiohttp",
            "requests": "requests",
            "httpx": "httpx",
            "numpy": "NumPy",
            "pandas": "Pandas",
            "torch": "PyTorch",
            "tensorflow": "TensorFlow",
            "scikit-learn": "scikit-learn",
            "anthropic": "Anthropic SDK",
            "openai": "OpenAI SDK",
        }

        for dep in deps:
            dep_lower = dep.lower()
            if dep_lower in framework_map:
                frameworks.add(framework_map[dep_lower])

        return frameworks

    def _detect_javascript(self) -> set[str]:
        """Detect JavaScript/TypeScript and frameworks."""
        tech = set()

        # Check root and common subdirectories
        search_paths = [
            self.repo_path / "package.json",
            self.repo_path / "frontend" / "package.json",
            self.repo_path / "client" / "package.json",
            self.repo_path / "web" / "package.json",
            self.repo_path / "ui" / "package.json",
        ]

        package_json = None
        for path in search_paths:
            if path.exists():
                package_json = path
                break

        if not package_json:
            return tech

        try:
            with open(package_json) as f:
                data = json.load(f)

            # Detect TypeScript
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

            if "typescript" in deps:
                tech.add("TypeScript")
            else:
                tech.add("JavaScript")

            # Detect frameworks
            framework_map = {
                "react": "React",
                "next": "Next.js",
                "vue": "Vue.js",
                "@vue/cli": "Vue.js",
                "nuxt": "Nuxt.js",
                "svelte": "Svelte",
                "@sveltejs/kit": "SvelteKit",
                "angular": "Angular",
                "@angular/core": "Angular",
                "express": "Express",
                "fastify": "Fastify",
                "koa": "Koa",
                "vite": "Vite",
                "webpack": "Webpack",
                "tailwindcss": "Tailwind CSS",
                "@tanstack/react-query": "TanStack Query",
                "axios": "Axios",
            }

            for dep, framework in framework_map.items():
                if dep in deps:
                    tech.add(framework)

        except Exception:
            pass

        return tech

    def _detect_rust(self) -> set[str]:
        """Detect Rust and crates."""
        tech = set()

        cargo_toml = self.repo_path / "Cargo.toml"
        if not cargo_toml.exists():
            return tech

        tech.add("Rust")

        try:
            with open(cargo_toml, "rb") as f:
                data = tomllib.load(f)

            deps = data.get("dependencies", {})

            crate_map = {
                "tokio": "Tokio",
                "actix-web": "Actix Web",
                "axum": "Axum",
                "rocket": "Rocket",
                "serde": "Serde",
                "sqlx": "SQLx",
                "diesel": "Diesel",
            }

            for crate, name in crate_map.items():
                if crate in deps:
                    tech.add(name)

        except Exception:
            pass

        return tech

    def _detect_go(self) -> set[str]:
        """Detect Go and modules."""
        tech = set()

        go_mod = self.repo_path / "go.mod"
        if not go_mod.exists():
            return tech

        tech.add("Go")

        try:
            with open(go_mod) as f:
                content = f.read()

            framework_patterns = {
                "github.com/gin-gonic/gin": "Gin",
                "github.com/gofiber/fiber": "Fiber",
                "github.com/labstack/echo": "Echo",
                "gorm.io/gorm": "GORM",
            }

            for pattern, framework in framework_patterns.items():
                if pattern in content:
                    tech.add(framework)

        except Exception:
            pass

        return tech

    def _detect_ruby(self) -> set[str]:
        """Detect Ruby and gems."""
        tech = set()

        gemfile = self.repo_path / "Gemfile"
        if not gemfile.exists():
            return tech

        tech.add("Ruby")

        try:
            with open(gemfile) as f:
                content = f.read()

            if "rails" in content:
                tech.add("Rails")
            if "sinatra" in content:
                tech.add("Sinatra")

        except Exception:
            pass

        return tech

    def _detect_php(self) -> set[str]:
        """Detect PHP and frameworks."""
        tech = set()

        composer_json = self.repo_path / "composer.json"
        if not composer_json.exists():
            return tech

        tech.add("PHP")

        try:
            with open(composer_json) as f:
                data = json.load(f)

            deps = {**data.get("require", {}), **data.get("require-dev", {})}

            framework_map = {
                "laravel/framework": "Laravel",
                "symfony/symfony": "Symfony",
                "symfony/framework-bundle": "Symfony",
            }

            for dep, framework in framework_map.items():
                if dep in deps:
                    tech.add(framework)

        except Exception:
            pass

        return tech

    def _detect_java(self) -> set[str]:
        """Detect Java and frameworks."""
        tech = set()

        # Check for Maven
        pom_xml = self.repo_path / "pom.xml"
        if pom_xml.exists():
            tech.add("Java")
            tech.add("Maven")

            # Could parse pom.xml for Spring Boot, etc., but that's complex
            # Simple string search for now
            try:
                with open(pom_xml) as f:
                    content = f.read()
                if "spring-boot" in content.lower():
                    tech.add("Spring Boot")
            except Exception:
                pass

        # Check for Gradle
        build_gradle = self.repo_path / "build.gradle"
        build_gradle_kts = self.repo_path / "build.gradle.kts"

        if build_gradle.exists() or build_gradle_kts.exists():
            tech.add("Java")
            tech.add("Gradle")

        return tech

    def get_file_tree_summary(self, max_depth: int = 2, max_files: int = 100) -> dict[str, Any]:
        """Get a summary of the repository file tree.

        Args:
            max_depth: Maximum directory depth to traverse
            max_files: Maximum number of files to include

        Returns:
            Dictionary with file tree information
        """
        if not self.repo_path.exists():
            return {"error": "Repository path does not exist"}

        file_count = 0
        dir_count = 0
        extensions = {}
        top_level_items = []

        try:
            # Get top-level items
            for item in sorted(self.repo_path.iterdir()):
                if item.name.startswith(".") and item.name not in [".github"]:
                    continue
                if item.name in ["node_modules", "__pycache__", "venv", ".venv", "target", "dist", "build"]:
                    continue

                top_level_items.append(item.name + ("/" if item.is_dir() else ""))

            # Count files and extensions
            for path in self.repo_path.rglob("*"):
                if any(
                    skip in path.parts
                    for skip in ["node_modules", "__pycache__", "venv", ".venv", "target", "dist", "build", ".git"]
                ):
                    continue

                if path.is_file():
                    file_count += 1
                    ext = path.suffix
                    if ext:
                        extensions[ext] = extensions.get(ext, 0) + 1

                    if file_count >= max_files:
                        break
                elif path.is_dir():
                    dir_count += 1

            return {
                "file_count": file_count,
                "dir_count": dir_count,
                "top_level": top_level_items,
                "extensions": dict(sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:20]),
            }

        except Exception as e:
            return {"error": str(e)}
