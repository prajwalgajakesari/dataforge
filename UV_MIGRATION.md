# Migration to uv

This project now uses **[uv](https://github.com/astral-sh/uv)** instead of pip for package management. uv is significantly faster and more reliable than pip/pip-tools.

## 🎯 Why uv?

- **10-100x faster** than pip
- **Deterministic** dependency resolution
- **Built-in virtual environment** management
- **Drop-in replacement** for pip
- **Modern Python packaging** with full PEP 517/518 support
- **Single lockfile** for reproducible builds

## 🚀 Quick Migration

### For Users

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or: brew install uv (macOS)
# Or: see https://github.com/astral-sh/uv#installation

# 2. Remove old virtual environment (if exists)
rm -rf venv

# 3. Install dependencies
uv sync

# 4. You're done! Run commands with:
uv run dataforge --help
```

### For Contributors

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install with all development dependencies
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest
```

## 📝 Command Reference

### Old (pip) vs New (uv)

| Task | Old Command (pip) | New Command (uv) |
|------|-------------------|------------------|
| Create venv | `python -m venv venv` | Automatic with `uv sync` |
| Activate venv | `source venv/bin/activate` | Optional - use `uv run` |
| Install deps | `pip install -r requirements.txt` | `uv sync` |
| Install dev deps | `pip install -e ".[dev]"` | `uv sync --extra dev` |
| Install all extras | `pip install -e ".[dev,test,docs]"` | `uv sync --all-extras` |
| Add new package | `pip install package` | `uv add package` |
| Remove package | `pip uninstall package` | `uv remove package` |
| Run command | `python script.py` or activate first | `uv run python script.py` |
| Run tool | `pytest` (after activate) | `uv run pytest` |
| Update deps | `pip install --upgrade` | `uv sync --upgrade` |

## 💡 Key Concepts

### 1. No More requirements.txt

Dependencies are now in `pyproject.toml`:
```toml
[project]
dependencies = [
    "anthropic>=0.25.0",
    "pydantic>=2.7.0",
    # ...
]
```

### 2. Automatic Virtual Environments

uv creates and manages `.venv/` automatically. You don't need to activate it - just use `uv run`:

```bash
# No need to activate!
uv run dataforge init my-project
uv run pytest
uv run python script.py
```

### 3. Lockfile (uv.lock)

uv generates `uv.lock` for reproducible installs. This file should be committed to git.

```bash
# First time or after changing dependencies
uv lock

# Install exact versions from lockfile
uv sync
```

## 🔧 Common Tasks

### Installing Packages

```bash
# Add a production dependency
uv add anthropic

# Add a development dependency
uv add --dev pytest

# Add with version constraint
uv add "pydantic>=2.0,<3.0"
```

### Running Commands

```bash
# Run Python
uv run python script.py

# Run module
uv run python -m interfaces.cli.main

# Run tool from dependencies
uv run pytest
uv run black .
uv run mypy core/

# Run interactive Python
uv run python
```

### Updating Dependencies

```bash
# Update all dependencies
uv sync --upgrade

# Update specific package
uv add anthropic --upgrade

# Update to latest compatible versions
uv lock --upgrade
uv sync
```

## 🆕 New Workflow Example

```bash
# Clone and setup
git clone https://github.com/your-org/dataforge.git
cd dataforge

# Install (creates .venv automatically)
uv sync --all-extras

# Copy environment file
cp .env.example .env
# Edit .env with your API key

# Run tests
uv run pytest

# Start development
uv run python -m interfaces.cli.main version

# Add a new dependency
uv add some-package

# Commit changes (including uv.lock)
git add pyproject.toml uv.lock
git commit -m "Add some-package dependency"
```

## 🔄 Differences from pip

### What Changed

1. **No requirements.txt** - Dependencies in pyproject.toml
2. **No setup.py** - Build config in pyproject.toml
3. **Automatic venv** - No manual venv creation
4. **Use `uv run`** - Or activate venv manually if preferred
5. **Lockfile** - uv.lock tracks exact versions

### What Stayed the Same

- Virtual environments still in `.venv/`
- Can still activate venv manually: `source .venv/bin/activate`
- All Python tools work the same way
- Project structure unchanged

## 📚 Additional Resources

- **uv Documentation**: https://github.com/astral-sh/uv
- **Installation Guide**: https://github.com/astral-sh/uv#installation
- **Python Packaging Guide**: https://packaging.python.org/

## ❓ FAQ

**Q: Can I still use pip?**
A: Technically yes, but we strongly recommend uv for this project. It's much faster and the lockfile ensures everyone has identical environments.

**Q: Do I need to activate the virtual environment?**
A: No! Just use `uv run` for all commands. But you can still activate it manually if you prefer.

**Q: What happened to requirements.txt?**
A: It's been replaced by `pyproject.toml` (dependencies) and `uv.lock` (exact versions).

**Q: How do I add a new dependency?**
A: `uv add package-name` and commit both pyproject.toml and uv.lock.

**Q: The migration broke something!**
A: Try:
```bash
rm -rf .venv uv.lock
uv sync
```

If still broken, open an issue with the error message.

**Q: Can I use uv with my IDE?**
A: Yes! Point your IDE to `.venv/bin/python`. Most modern IDEs auto-detect it.

**Q: Is this compatible with CI/CD?**
A: Yes! uv works great in CI:
```yaml
- name: Install uv
  run: curl -LsSf https://astral.sh/uv/install.sh | sh

- name: Install dependencies
  run: uv sync

- name: Run tests
  run: uv run pytest
```

---

**Questions?** Open an issue or discussion on GitHub!
