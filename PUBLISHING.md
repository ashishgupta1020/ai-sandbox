# Publishing to PyPI

Steps to ship a new version of `ataskman` with Twine (same name on PyPI and TestPyPI).

1) Bump version  
Update `[project].version` in `pyproject.toml` (PyPI refuses reused versions).

2) Confirm name  
Ensure `[project].name = "ataskman"` in `pyproject.toml`.

3) Clean build directories  
```bash
rm -rf dist build src/taskman.egg-info src/ataskman.egg-info
```

4) Fresh tooling  
```bash
python -m venv venv && source venv/bin/activate
python -m pip install --upgrade pip build twine
```

5) Build artifacts  
```bash
python -m build
twine check dist/*
```

6) Optional TestPyPI dry run  
```bash
TWINE_USERNAME=__token__ TWINE_PASSWORD=<testpypi_token> \
twine upload --repository testpypi dist/*

# Verify install
python -m venv /tmp/taskman-test && source /tmp/taskman-test/bin/activate
python -m pip install --index-url https://test.pypi.org/simple \
  --extra-index-url https://pypi.org/simple ataskman
```

7) Publish to PyPI  
```bash
TWINE_USERNAME=__token__ TWINE_PASSWORD=<pypi_token> \
twine upload dist/*
```

Notes  
- Always bump the version before publishing to PyPI.  
- Keep 2FA enabled; use API tokens for uploads.  
- Rebuild every release; do not reuse old `dist/` files.
