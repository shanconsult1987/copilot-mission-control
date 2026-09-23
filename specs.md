# Mission Control Specification

This document is the source of truth for the current Mission Control
application. Requirements use **MUST**, **SHOULD**, and **MAY** in their usual
normative sense.

## 1. Problem Statement

Mission Control accepts a spacecraft incident identifier and description,
classifies the description into a supported incident category, and returns a
structured mission response. Classification is deterministic and based on
configured words and phrases.

The application provides a Python API and a command-line interface. It does not
persist incidents or communicate with external systems.

## 2. Functional Requirements

### 2.1 Incident input

- An incident MUST be represented by the immutable `Incident` dataclass.
- `Incident` MUST contain:
  - `incident_id: str`
  - `description: str`
- `process_incident` MUST reject a non-`Incident` value.
- `process_incident` MUST reject an incident ID that is not a string.
- `process_incident` MUST reject an empty or whitespace-only incident ID.
- `classify_incident` MUST reject a description that is not a string.
- `classify_incident` MUST reject an empty or whitespace-only description.

### 2.2 Incident processing

`process_incident(incident)` MUST:

1. Validate the incident ID.
2. Classify the incident description.
3. Retrieve the response for the selected category.
4. Return an `IncidentResult`.

### 2.3 Classification

`classify_incident(description)` MUST:

1. Convert the description to lowercase.
2. Replace characters other than ASCII letters and digits with spaces.
3. Collapse repeated whitespace.
4. Match configured complete words and normalized phrases.
5. Give a category one point for each distinct configured keyword present.
6. Select the category with the unique highest score.

Repeating the same keyword in a description MUST NOT increase its score.

### 2.4 Response generation

`get_mission_response(category)` MUST return the configured immutable
`MissionResponse` for an `IncidentCategory`.

Every category, including `UNCLASSIFIED`, MUST have a response containing:

- The matching `IncidentCategory`
- A nonempty summary
- One or more nonempty ordered actions

### 2.5 Priority calculation

`calculate_priority(category)` MUST accept an `IncidentCategory` or a string.

- String input MUST be stripped of surrounding whitespace.
- String matching MUST be case-insensitive.
- A known category MUST return its configured priority.
- An unknown string MUST return `low`.
- A value that is neither a string nor an `IncidentCategory` MUST raise
  `TypeError`.

Priority calculation is a separate API. Priority is not included in
`IncidentResult` or CLI output.

### 2.6 Command-line interface

The CLI MUST accept two positional arguments:

1. Incident ID
2. Incident description

On success, the CLI MUST print:

- Incident ID
- Category value
- Matched keywords, or `none`
- Response summary
- Numbered response actions

Successful execution MUST return exit code `0`. Incident validation errors MUST
be written to standard error and return exit code `2`.

## 3. Incident Categories

| Category | Configured keywords | Priority |
|---|---|---|
| `thermal` | `cooling`, `heat`, `overheating`, `radiator`, `temperature` | `critical` |
| `battery` | `battery`, `charging`, `power cell`, `voltage` | `high` |
| `mobility` | `actuator`, `motor`, `stuck`, `wheel` | `high` |
| `navigation` | `coordinates`, `heading`, `position`, `trajectory` | `medium` |
| `communication` | `antenna`, `radio`, `signal`, `telemetry` | `high` |
| `unclassified` | None | `low` |

Each category MUST have a configured mission response. Category configuration
MUST be validated when `app.mission` is imported.

## 4. Expected Outputs

### 4.1 `ClassificationResult`

Classification MUST return an immutable `ClassificationResult` containing:

- `category: IncidentCategory`
- `matched_keywords: tuple[str, ...]`

For a uniquely classified incident, `matched_keywords` MUST contain the
configured keywords that contributed to the winning score.

### 4.2 `MissionResponse`

A response MUST be an immutable `MissionResponse` containing:

- `category: IncidentCategory`
- `summary: str`
- `actions: tuple[str, ...]`

Actions MUST remain in their configured order.

### 4.3 `IncidentResult`

Processing MUST return an immutable `IncidentResult` containing:

- The original `Incident`
- The selected `IncidentCategory`
- The selected `MissionResponse`
- The matched keyword tuple

The result category and response category MUST agree when produced by
`process_incident`.

## 5. Error and Unknown Behavior

### 5.1 Unknown descriptions

If no category keyword matches, classification MUST return:

- Category `UNCLASSIFIED`
- An empty matched-keyword tuple

The unclassified response MUST request human review and recommend preserving
state and telemetry, avoiding irreversible actions, and gathering diagnostics.

### 5.2 Ambiguous descriptions

If multiple categories share the highest nonzero score:

- Classification MUST return `UNCLASSIFIED`.
- Matched evidence MUST contain the sorted, deduplicated keywords from the tied
  categories.

### 5.3 Invalid values

- Invalid runtime types MUST raise `TypeError`.
- Empty required text MUST raise `ValueError`.
- `get_mission_response` MUST raise `TypeError` for a value that is not an
  `IncidentCategory`.

### 5.4 Invalid configuration

Import-time configuration validation MUST raise `RuntimeError` for:

- Missing or extra category configuration
- A response whose category does not match its configuration key
- An empty response summary
- Missing response actions
- Empty response actions
- Duplicate keywords within a category
- Empty or non-normalized keywords
- Keywords assigned to `UNCLASSIFIED`

## 6. Non-Functional Requirements

- Runtime behavior MUST use only the Python standard library.
- Classification MUST be deterministic for the same configuration and input.
- Public functions and domain fields MUST use type hints.
- Public functions and domain models SHOULD have useful docstrings.
- Domain result objects MUST be immutable dataclasses.
- Category data MUST remain centralized so keywords, priority, and response can
  be reviewed together.
- The application MUST remain usable without a database, network connection,
  framework, or external service.

## 7. Testing Requirements

- Tests MUST use Python `unittest`.
- Tests MUST cover:
  - Every incident category
  - Every configured keyword
  - Unknown incidents
  - Ambiguous category ties
  - Case, punctuation, phrase, and whitespace normalization
  - Invalid incident IDs and descriptions
  - Response generation
  - Priority calculation
  - Configuration validation failures
  - End-to-end processing for every classified category
  - CLI parsing, formatting, success, and validation failure
- The full test suite MUST pass with:

  ```powershell
  python -m unittest discover -s tests -v
  ```

- Branch coverage across `app` MUST remain at or above 95% when measured with:

  ```powershell
  python -m coverage run --branch --source=app -m unittest discover -s tests -v
  python -m coverage report -m --fail-under=95
  ```

The current baseline is 39 passing tests and 99% combined statement/branch
coverage.

## 8. Constraints

- Classification is keyword-based; it does not interpret intent, negation, or
  semantic context.
- Text normalization is ASCII-oriented. Non-ASCII letters are replaced with
  spaces.
- A description may mention multiple systems, but the output contains only one
  category or `UNCLASSIFIED`.
- The CLI processes one incident per invocation.
- Incident IDs and descriptions are not persisted.
- No severity, timestamp, authentication, authorization, telemetry ingestion,
  database, HTTP API, or external-service integration exists.
- The configured response is advisory text; the application does not execute
  response actions.