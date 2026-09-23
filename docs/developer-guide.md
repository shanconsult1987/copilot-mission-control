# Mission Control Developer Guide

## Architecture

Mission Control is a small, standard-library-only Python application with two
layers:

- [`app/mission.py`](../app/mission.py) contains domain models, incident
  classification, response lookup, priority calculation, and orchestration.
- [`app/main.py`](../app/main.py) provides the command-line interface (CLI).

There is no database, network service, framework, or external runtime
dependency. Category keywords, priorities, and responses are stored together
in the private `_CATEGORY_CONFIG` mapping. Configuration is validated when the
module is imported.

## Application Flow

1. The CLI reads an incident ID and description.
2. It creates an `Incident`.
3. `process_incident` validates the incident ID.
4. `classify_incident` validates and classifies the description.
5. `get_mission_response` selects the configured response.
6. `process_incident` returns an `IncidentResult`.
7. The CLI prints the category, matched keywords, response summary, and ordered
   actions.

Successful CLI execution returns exit code `0`. Incident validation errors are
written to standard error and return exit code `2`.

## Mission Request

The codebase does not define a `MissionRequest` class. The implemented request
model is the immutable `Incident` dataclass:

```python
Incident(
    incident_id="AUR-104",
    description="Battery voltage dropped during charging.",
)
```

`incident_id` and `description` must be strings. `process_incident` rejects an
empty or whitespace-only ID, while `classify_incident` rejects an empty or
whitespace-only description.

## Incident Classification

`classify_incident(description)` returns a `ClassificationResult` containing an
`IncidentCategory` and the keywords that supported the result.

Supported categories are:

- `thermal`
- `battery`
- `mobility`
- `navigation`
- `communication`
- `unclassified`

The classifier:

1. Converts the description to lowercase.
2. Replaces characters other than ASCII letters and digits with spaces.
3. Collapses repeated whitespace.
4. Matches complete words and normalized phrases.
5. Scores each category by its number of distinct matched keywords.

A unique highest-scoring category wins. No matches produce `UNCLASSIFIED` with
no evidence. A tie also produces `UNCLASSIFIED`, with sorted and deduplicated
keywords from the tied categories. Repeating a keyword in a description does
not increase its score.

## Response Generation

`get_mission_response(category)` returns an immutable `MissionResponse` with:

- The response category
- A short summary
- An ordered tuple of actions

Every `IncidentCategory`, including `UNCLASSIFIED`, has a configured response.
Passing a value that is not an `IncidentCategory` raises `TypeError`.

`process_incident(incident)` combines classification and response selection
into an `IncidentResult` containing:

- The original `Incident`
- The selected category
- The `MissionResponse`
- The matched keywords

## Priority Calculation

`calculate_priority(category)` accepts an `IncidentCategory` or string and
returns one of `critical`, `high`, `medium`, or `low`.

| Category | Priority |
|---|---|
| Thermal | Critical |
| Battery | High |
| Mobility | High |
| Navigation | Medium |
| Communication | High |
| Unclassified or unknown string | Low |

String values are stripped and matched case-insensitively. Non-string values
that are not `IncidentCategory` members raise `TypeError`.

## Running the Application

Run commands from the repository root:

```powershell
python -m app.main AUR-104 "Battery voltage dropped during charging."
```

The CLI requires both positional arguments. Descriptions containing spaces
must be quoted.

## Testing

Tests use the standard-library `unittest` framework:

- [`tests/test_mission.py`](../tests/test_mission.py) covers domain behavior,
  validation, configuration invariants, classification, responses, priorities,
  and end-to-end processing.
- [`tests/test_main.py`](../tests/test_main.py) covers CLI parsing, formatting,
  successful execution, and validation failures.

Run all tests:

```powershell
python -m unittest discover -s tests -v
```

## Coverage Report

The latest branch-coverage run executed 39 tests successfully with
`coverage.py 7.15.4`:

| File | Statements | Branches | Overall |
|---|---:|---:|---:|
| `app/main.py` | 24/25 | 1/2 | 93% |
| `app/mission.py` | 113/113 | 38/38 | 100% |
| **Total** | **137/138** | **39/40** | **99%** |

The only uncovered line is the direct-execution guard that raises
`SystemExit` in `app/main.py`.

Run coverage and enforce the current minimum:

```powershell
python -m coverage run --branch --source=app -m unittest discover -s tests -v
python -m coverage report -m --fail-under=95
```

`coverage.py` is a development tool and is not required to run the
application.

## Extension Points

### Add an incident category

1. Add a member to `IncidentCategory`.
2. Add one `_CategoryConfig` entry with normalized keywords, a priority, and a
   matching `MissionResponse`.
3. Add classification, response, priority, and end-to-end tests.

Import-time configuration validation rejects missing categories, mismatched
response categories, incomplete responses, empty actions, duplicate keywords,
and non-normalized keywords.

### Adjust classification

Update the keywords in `_CATEGORY_CONFIG`. Keywords must be lowercase and
normalized in the same form produced by `_normalize`.

### Change mission responses or priorities

Update the relevant `_CategoryConfig` entry. No classifier control-flow changes
are required.

### Add another interface

Call `process_incident` from the new interface and format the returned
`IncidentResult`. Domain behavior does not depend on the CLI.
