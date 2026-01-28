#!/usr/bin/env python3
"""
Verification script for DataForge setup.

This script checks that all components are properly set up.
Run after installing dependencies: uv sync
"""

import sys
from pathlib import Path


def check_file_exists(path: str, description: str) -> bool:
    """Check if a file exists."""
    if Path(path).exists():
        print(f"✓ {description}")
        return True
    else:
        print(f"✗ {description} - MISSING")
        return False


def check_directory_exists(path: str, description: str) -> bool:
    """Check if a directory exists."""
    if Path(path).is_dir():
        print(f"✓ {description}")
        return True
    else:
        print(f"✗ {description} - MISSING")
        return False


def main():
    """Run all verification checks."""
    print("\n" + "=" * 60)
    print("DataForge Setup Verification")
    print("=" * 60 + "\n")

    checks = []

    # Core files
    print("Core Configuration Files:")
    checks.append(check_file_exists("pyproject.toml", "pyproject.toml"))
    checks.append(check_file_exists(".python-version", ".python-version"))
    checks.append(check_file_exists(".env.example", ".env.example"))
    checks.append(check_file_exists(".gitignore", ".gitignore"))

    print("\nDocumentation:")
    checks.append(check_file_exists("README.md", "README.md"))
    checks.append(check_file_exists("QUICKSTART.md", "QUICKSTART.md"))
    checks.append(check_file_exists("PROJECT_SETUP.md", "PROJECT_SETUP.md"))
    checks.append(check_file_exists("CONTRIBUTING.md", "CONTRIBUTING.md"))
    checks.append(check_file_exists("plan.md", "Original plan.md"))

    print("\nCore Modules:")
    checks.append(check_directory_exists("core/agents", "core/agents"))
    checks.append(check_file_exists("core/agents/base.py", "Base agent"))
    checks.append(check_file_exists("core/agents/modeling.py", "Modeling agent"))

    checks.append(check_directory_exists("core/mcp", "core/mcp"))
    checks.append(check_file_exists("core/mcp/registry.py", "MCP registry"))
    checks.append(check_file_exists("core/mcp/client.py", "MCP client"))

    checks.append(check_directory_exists("core/workspace", "core/workspace"))
    checks.append(check_file_exists("core/workspace/manager.py", "Workspace manager"))

    checks.append(check_directory_exists("core/utils", "core/utils"))
    checks.append(check_file_exists("core/utils/config.py", "Configuration"))
    checks.append(check_file_exists("core/utils/logger.py", "Logger"))

    print("\nInterfaces:")
    checks.append(check_directory_exists("interfaces/cli", "CLI interface"))
    checks.append(check_file_exists("interfaces/cli/main.py", "CLI main"))

    print("\nAPI:")
    checks.append(check_directory_exists("api", "API directory"))
    checks.append(check_file_exists("api/server.py", "API server"))

    print("\nTests:")
    checks.append(check_directory_exists("tests", "Tests directory"))
    checks.append(check_file_exists("tests/conftest.py", "Test configuration"))
    checks.append(check_file_exists("tests/unit/test_agents.py", "Agent tests"))

    # Try importing modules (only if dependencies installed)
    print("\nModule Imports:")
    try:
        from core.agents.base import BaseDataEngineeringAgent
        print("✓ core.agents.base")
        checks.append(True)
    except ImportError as e:
        print(f"✗ core.agents.base - {e}")
        print("  (Install dependencies: pip install -r requirements.txt)")
        checks.append(False)

    try:
        from core.mcp.registry import MCPRegistry
        print("✓ core.mcp.registry")
        checks.append(True)
    except ImportError as e:
        print(f"✗ core.mcp.registry - {e}")
        checks.append(False)

    try:
        from core.workspace.manager import WorkspaceManager
        print("✓ core.workspace.manager")
        checks.append(True)
    except ImportError as e:
        print(f"✗ core.workspace.manager - {e}")
        checks.append(False)

    # Summary
    print("\n" + "=" * 60)
    passed = sum(checks)
    total = len(checks)
    percentage = (passed / total * 100) if total > 0 else 0

    print(f"Results: {passed}/{total} checks passed ({percentage:.1f}%)")

    if passed == total:
        print("✓ All checks passed! Setup is complete.")
        print("\nNext steps:")
        print("  1. Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh")
        print("  2. cp .env.example .env")
        print("  3. Add your ANTHROPIC_API_KEY to .env")
        print("  4. uv sync")
        print("  5. uv run python -m interfaces.cli.main version")
        return 0
    else:
        print("✗ Some checks failed. Review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
