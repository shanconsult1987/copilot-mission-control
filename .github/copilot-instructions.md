# Mission Control Copilot Instructions

## Project

This is the Aurora Mission Control Python application.

## Development Rules

- Use Python.
- Prefer the standard library.
- Keep the architecture simple.
- Use type hints.
- Use dataclasses for simple data models.
- Write unit tests for new behavior.
- Do not introduce dependencies unless explicitly requested.
- Preserve existing public function names unless explicitly asked to change them.
- Keep functions small and readable.
- Add docstrings to public functions.
- Do not invent requirements.
- Read specs.md before implementing significant changes.

## Testing

Run:

python -m unittest discover -v

For coverage:

python -m coverage run -m unittest discover -v
python -m coverage report

## Documentation

Update developer documentation when behavior changes.