# Aurora Mission Control - Implementation Plan

## 1. Problem Understanding

Build a small Python application that:

1. Accepts a spacecraft incident containing a description and basic metadata.
2. Classifies the incident into exactly one supported category:
   - `thermal`
   - `battery`
   - `mobility`
   - `navigation`
   - `communication`
3. Produces a mission response appropriate to that category.
4. Handles invalid, empty, or unrecognized incidents explicitly.

For a training workshop, classification should be deterministic and explainable. A keyword-based classifier is preferable to machine learning or external AI services.

### Assumptions

- Input is one incident at a time.
- Incident descriptions are plain English.
- Classification is based on configured keywords.
- Mission responses are predefined operational instructions.
- No database, network service, authentication, or external dependency is required.
- The first version is a Python library with a small command-line entry point.
- An incident that cannot be confidently classified is reported as `unclassified`, rather than silently assigned an arbitrary category.

## 2. Minimal Architecture

Use a simple three-stage pipeline:

```text
Incident input
      |
      v
Input validation
      |
      v
Keyword classification
      |
      v
Mission response selection
      |
      v
Incident result
```

### Responsibilities

- **Models:** Represent incidents, categories, and results.
- **Classifier:** Analyze normalized incident text and choose a category.
- **Response service:** Map the selected category to mission instructions.
- **Application service:** Coordinate validation, classification, and response generation.
- **CLI:** Provide a simple interactive demonstration.
- **Tests:** Verify each component independently and the complete workflow.

This separation keeps the domain logic reusable without introducing unnecessary frameworks or design patterns.

## 3. Python Modules

Proposed project structure:

```text
aurora_mission_control/
|-- __init__.py
|-- models.py
|-- classifier.py
|-- responses.py
|-- service.py
`-- cli.py

tests/
|-- test_classifier.py
|-- test_responses.py
`-- test_service.py
```

### Module Purposes

| Module | Responsibility |
|---|---|
| `models.py` | Domain enums and dataclasses |
| `classifier.py` | Text normalization and category classification |
| `responses.py` | Category-to-response mapping |
| `service.py` | End-to-end incident processing |
| `cli.py` | Workshop-friendly command-line interface |
| `__init__.py` | Expose the small public API |
| `test_classifier.py` | Classification unit tests |
| `test_responses.py` | Response-selection unit tests |
| `test_service.py` | Validation and workflow tests |

No third-party runtime packages are needed. Tests can use the standard-library `unittest` framework, keeping setup minimal.

## 4. Data Structures

### `IncidentCategory`

A string-backed enum containing:

```text
THERMAL
BATTERY
MOBILITY
NAVIGATION
COMMUNICATION
UNCLASSIFIED
```

Including `UNCLASSIFIED` makes an inconclusive result explicit.

### `Incident`

An immutable dataclass representing input:

| Field | Type | Purpose |
|---|---|---|
| `incident_id` | `str` | Identifier used for tracking |
| `description` | `str` | Human-readable incident details |

Optional fields such as severity and timestamp should be deferred until required by the workshop.

### `MissionResponse`

An immutable dataclass:

| Field | Type | Purpose |
|---|---|---|
| `category` | `IncidentCategory` | Category addressed by the response |
| `summary` | `str` | Short response title |
| `actions` | `tuple[str, ...]` | Ordered mission actions |

### `IncidentResult`

An immutable dataclass representing successful processing:

| Field | Type | Purpose |
|---|---|---|
| `incident` | `Incident` | Original validated incident |
| `category` | `IncidentCategory` | Classification result |
| `response` | `MissionResponse` | Recommended mission response |
| `matched_keywords` | `tuple[str, ...]` | Evidence explaining the classification |

The matched keywords make the classifier transparent and easier to demonstrate.

### `ClassificationResult`

An immutable dataclass containing:

| Field | Type | Purpose |
|---|---|---|
| `category` | `IncidentCategory` | Selected category |
| `matched_keywords` | `tuple[str, ...]` | Keywords supporting the decision |

### Static Configuration

Maintain two module-level mappings:

1. Category to keywords.
2. Category to mission response.

Example concepts:

| Category | Example signals |
|---|---|
| Thermal | overheating, temperature, cooling, radiator |
| Battery | battery, voltage, charging, power cell |
| Mobility | wheel, actuator, motor, stuck |
| Navigation | position, heading, trajectory, coordinates |
| Communication | signal, antenna, telemetry, radio |

## 5. Public Functions

### Classification

```python
classify_incident(description: str) -> ClassificationResult
```

Responsibilities:

- Validate the description.
- Normalize case and punctuation.
- Match whole words or phrases against category keywords.
- Score categories by the number of matched keywords.
- Return the winning category and its matched keywords.
- Return `UNCLASSIFIED` if there are no matches.

### Mission Response Selection

```python
get_mission_response(
    category: IncidentCategory,
) -> MissionResponse
```

Responsibilities:

- Return the configured response for a valid category.
- Include a safe escalation response for `UNCLASSIFIED`.
- Reject values that are not `IncidentCategory` members.

### End-to-End Processing

```python
process_incident(incident: Incident) -> IncidentResult
```

Responsibilities:

1. Validate the incident identifier and description.
2. Classify the description.
3. Select the mission response.
4. Return a complete result.

This should be the primary public function used by callers.

### CLI Entry Point

```python
main() -> int
```

Responsibilities:

- Read an incident identifier and description.
- Call `process_incident`.
- Print the category, evidence, and ordered actions.
- Print validation errors clearly.
- Return `0` on success and a nonzero status on invalid input.

### Public API

The package should expose only the main domain types and functions:

```text
Incident
IncidentCategory
IncidentResult
MissionResponse
classify_incident
get_mission_response
process_incident
```

Internal normalization and scoring helpers should remain private.

## 6. Classification Rules

To keep behavior predictable:

1. Convert text to lowercase.
2. Normalize punctuation and repeated whitespace.
3. Match complete words and configured multi-word phrases.
4. Assign one point for each distinct keyword matched.
5. Select the category with the highest score.
6. If no category scores, return `UNCLASSIFIED`.
7. If multiple categories have the same highest score, return `UNCLASSIFIED` rather than relying on dictionary order.

This avoids arbitrary classifications and gives operators an escalation path for ambiguous reports.

An `UNCLASSIFIED` response should recommend:

- Preserving telemetry.
- Avoiding irreversible actions.
- Requesting operator review.
- Gathering additional diagnostics.

## 7. Test Cases

### Classifier Tests

1. **Thermal incident**
   - Input: "Reactor temperature is rising and the cooling loop is unstable."
   - Expected: `THERMAL`.

2. **Battery incident**
   - Input: "Battery voltage dropped during charging."
   - Expected: `BATTERY`.

3. **Mobility incident**
   - Input: "The rover wheel motor is stuck."
   - Expected: `MOBILITY`.

4. **Navigation incident**
   - Input: "Current position differs from the planned trajectory."
   - Expected: `NAVIGATION`.

5. **Communication incident**
   - Input: "Telemetry signal was lost after the antenna stopped responding."
   - Expected: `COMMUNICATION`.

6. **Case insensitivity**
   - Uppercase or mixed-case keywords still match.

7. **Punctuation handling**
   - Keywords adjacent to commas or periods still match.

8. **Whole-word matching**
   - A short keyword must not match merely because it appears inside an unrelated word.

9. **Multiple keywords in one category**
   - All distinct matches are returned as evidence.

10. **Unknown incident**
    - Input: "An unexpected condition was observed."
    - Expected: `UNCLASSIFIED`.

11. **Cross-category tie**
    - Equal evidence for battery and communication.
    - Expected: `UNCLASSIFIED`.

12. **Clear cross-category winner**
    - Mentions several categories, but one has a higher score.
    - Expected: highest-scoring category.

13. **Repeated keyword**
    - Repeating one keyword does not artificially increase its score.

### Response Tests

For every category:

- A response exists.
- Its category matches the requested category.
- Its summary is nonempty.
- It contains at least one nonempty action.
- The unclassified response requests human review.

### Service Tests

1. Valid incident returns a complete `IncidentResult`.
2. The original incident is preserved.
3. The result category and response category agree.
4. Empty incident identifier is rejected.
5. Whitespace-only incident identifier is rejected.
6. Empty description is rejected.
7. Whitespace-only description is rejected.
8. Non-string fields are rejected clearly if runtime construction permits them.

### CLI Tests

Keep CLI testing light:

- Valid input produces category and action output.
- Invalid input produces an error and nonzero exit code.

The workshop can prioritize domain tests if CLI input mocking would distract from the core lesson.

## 8. Potential Failure Cases

| Failure case | Planned behavior |
|---|---|
| Empty description | Raise a clear validation error |
| Whitespace-only description | Raise a clear validation error |
| Missing incident identifier | Raise a clear validation error |
| Unknown terminology | Return `UNCLASSIFIED` with escalation instructions |
| Equal scores across categories | Return `UNCLASSIFIED` |
| Incident genuinely involves multiple systems | Choose only a clear score winner; otherwise escalate |
| Keyword appears inside another word | Do not count it |
| Same keyword repeated many times | Count it once |
| Invalid category passed to response lookup | Raise `TypeError` or `ValueError` explicitly |
| Category has no configured response | Raise a configuration error rather than fabricate output |
| Keyword configuration overlaps categories | Detect through tests and document intentional overlaps |
| Extremely long description | Functionally supported; optional input limits are out of scope |
| Non-English incident | Likely unclassified; localization is out of scope |
| Negated statement, such as "battery is not failing" | May produce a false positive; advanced language interpretation is out of scope |

The major limitation should be documented: keyword matching is suitable for teaching and demonstration, not autonomous flight-critical decision-making.

## 9. Mission Response Content

Each response should be short, operational, and ordered.

### Thermal

- Reduce nonessential load.
- Collect temperature and cooling telemetry.
- Activate or verify thermal-control measures.
- Escalate if limits continue to rise.

### Battery

- Reduce power consumption.
- Inspect voltage, current, and charging telemetry.
- Isolate a suspected battery path if procedures permit.
- Preserve power for essential systems.

### Mobility

- Stop movement.
- Inspect motor, actuator, and wheel telemetry.
- Avoid repeated commands that could worsen damage.
- Plan a controlled recovery maneuver.

### Navigation

- Hold or enter a safe navigation state.
- Compare primary and backup position sources.
- Recalculate position or trajectory.
- Require confirmation before resuming movement.

### Communication

- Preserve onboard telemetry.
- Check antenna and radio status.
- Attempt an approved backup channel or retry sequence.
- Escalate after the configured communication window.

### Unclassified

- Preserve current state and telemetry.
- Avoid irreversible actions.
- Gather additional diagnostics.
- Request human operator classification.

These are illustrative workshop responses and should be reviewed by actual mission-domain experts before operational use.

## 10. Implementation Sequence

1. Create package and test directories.
2. Define enums and immutable dataclasses.
3. Add keyword and response configuration.
4. Implement text normalization.
5. Implement deterministic classification and tie handling.
6. Implement response lookup.
7. Implement incident validation and orchestration.
8. Expose the public package API.
9. Add the minimal CLI.
10. Write tests for all categories, ambiguity, validation, and response completeness.
11. Run the focused test suite.
12. Add a short usage example and document classifier limitations.

## Definition of Done

The implementation is complete when:

- Every supported category can be classified from representative text.
- Every category has a nonempty mission response.
- Unknown and ambiguous incidents safely produce `UNCLASSIFIED`.
- Invalid inputs fail with explicit errors.
- The public API is small and type-annotated.
- All tests pass using only the Python standard library.
- The code remains understandable within a short training workshop.
