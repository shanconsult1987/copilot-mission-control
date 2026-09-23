"""Core incident classification and response logic for Mission Control."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class IncidentCategory(str, Enum):
    """Categories recognized by Mission Control."""

    THERMAL = "thermal"
    BATTERY = "battery"
    MOBILITY = "mobility"
    NAVIGATION = "navigation"
    COMMUNICATION = "communication"
    UNCLASSIFIED = "unclassified"


@dataclass(frozen=True)
class Incident:
    """A spacecraft incident submitted to Mission Control."""

    incident_id: str
    description: str


@dataclass(frozen=True)
class ClassificationResult:
    """The category selected for an incident and the evidence used."""

    category: IncidentCategory
    matched_keywords: tuple[str, ...]


@dataclass(frozen=True)
class MissionResponse:
    """A summary and ordered actions for an incident category."""

    category: IncidentCategory
    summary: str
    actions: tuple[str, ...]


@dataclass(frozen=True)
class IncidentResult:
    """The structured result of processing an incident."""

    incident: Incident
    category: IncidentCategory
    response: MissionResponse
    matched_keywords: tuple[str, ...]


Priority = Literal["critical", "high", "medium", "low"]


@dataclass(frozen=True)
class _CategoryConfig:
    """Classification and response settings for one incident category."""

    keywords: tuple[str, ...]
    priority: Priority
    response: MissionResponse


_CATEGORY_CONFIG: dict[IncidentCategory, _CategoryConfig] = {
    IncidentCategory.THERMAL: _CategoryConfig(
        keywords=("cooling", "heat", "overheating", "radiator", "temperature"),
        priority="critical",
        response=MissionResponse(
            IncidentCategory.THERMAL,
            "Stabilize spacecraft temperature.",
            (
                "Reduce nonessential system load.",
                "Collect temperature and cooling telemetry.",
                "Verify thermal-control systems.",
                "Escalate if temperature limits continue to rise.",
            ),
        ),
    ),
    IncidentCategory.BATTERY: _CategoryConfig(
        keywords=("battery", "charging", "power cell", "voltage"),
        priority="high",
        response=MissionResponse(
            IncidentCategory.BATTERY,
            "Protect remaining electrical power.",
            (
                "Reduce nonessential power consumption.",
                "Inspect voltage, current, and charging telemetry.",
                "Isolate the suspected battery path if procedures permit.",
                "Preserve power for essential systems.",
            ),
        ),
    ),
    IncidentCategory.MOBILITY: _CategoryConfig(
        keywords=("actuator", "motor", "stuck", "wheel"),
        priority="high",
        response=MissionResponse(
            IncidentCategory.MOBILITY,
            "Prevent further mobility-system damage.",
            (
                "Stop spacecraft or rover movement.",
                "Inspect motor, actuator, and wheel telemetry.",
                "Avoid repeated movement commands.",
                "Plan a controlled recovery maneuver.",
            ),
        ),
    ),
    IncidentCategory.NAVIGATION: _CategoryConfig(
        keywords=("coordinates", "heading", "position", "trajectory"),
        priority="medium",
        response=MissionResponse(
            IncidentCategory.NAVIGATION,
            "Re-establish a reliable navigation solution.",
            (
                "Enter a safe navigation state.",
                "Compare primary and backup position sources.",
                "Recalculate position or trajectory.",
                "Confirm the solution before resuming movement.",
            ),
        ),
    ),
    IncidentCategory.COMMUNICATION: _CategoryConfig(
        keywords=("antenna", "radio", "signal", "telemetry"),
        priority="high",
        response=MissionResponse(
            IncidentCategory.COMMUNICATION,
            "Restore the communication link.",
            (
                "Preserve onboard telemetry.",
                "Check antenna and radio status.",
                "Attempt an approved backup channel or retry sequence.",
                "Escalate after the communication recovery window.",
            ),
        ),
    ),
    IncidentCategory.UNCLASSIFIED: _CategoryConfig(
        keywords=(),
        priority="low",
        response=MissionResponse(
            IncidentCategory.UNCLASSIFIED,
            "Request human review before taking corrective action.",
            (
                "Preserve the current state and telemetry.",
                "Avoid irreversible actions.",
                "Gather additional diagnostics.",
                "Request human operator classification.",
            ),
        ),
    ),
}


def calculate_priority(category: IncidentCategory | str) -> Priority:
    """Return the mission priority for a category, or ``low`` if unknown.

    String categories are matched without regard to case or surrounding
    whitespace.

    Raises:
        TypeError: If ``category`` is neither a string nor an incident category.
    """

    if isinstance(category, IncidentCategory):
        normalized_category = category
    elif isinstance(category, str):
        try:
            normalized_category = IncidentCategory(category.strip().lower())
        except ValueError:
            return _CATEGORY_CONFIG[IncidentCategory.UNCLASSIFIED].priority
    else:
        raise TypeError("category must be an IncidentCategory or string")

    return _CATEGORY_CONFIG[normalized_category].priority


def _normalize(text: str) -> str:
    """Return lowercase text with punctuation and whitespace normalized."""

    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _contains_keyword(normalized_description: str, keyword: str) -> bool:
    """Return whether a normalized keyword occurs as a word or phrase."""

    padded_description = f" {normalized_description} "
    return f" {keyword} " in padded_description


def _validate_configuration() -> None:
    """Fail fast when category configuration is incomplete or invalid."""

    missing_categories = set(IncidentCategory) - set(_CATEGORY_CONFIG)
    extra_categories = set(_CATEGORY_CONFIG) - set(IncidentCategory)
    if missing_categories or extra_categories:
        raise RuntimeError(
            "category configuration does not match IncidentCategory"
        )

    for category, config in _CATEGORY_CONFIG.items():
        if config.response.category is not category:
            raise RuntimeError(
                f"response category does not match {category.value}"
            )
        if not config.response.summary.strip() or not config.response.actions:
            raise RuntimeError(f"incomplete response for {category.value}")
        if any(not action.strip() for action in config.response.actions):
            raise RuntimeError(f"empty response action for {category.value}")
        if len(config.keywords) != len(set(config.keywords)):
            raise RuntimeError(f"duplicate keywords for {category.value}")
        if any(
            not keyword or _normalize(keyword) != keyword
            for keyword in config.keywords
        ):
            raise RuntimeError(f"invalid keyword for {category.value}")

    if _CATEGORY_CONFIG[IncidentCategory.UNCLASSIFIED].keywords:
        raise RuntimeError("unclassified category must not define keywords")


def _validate_description(description: str) -> None:
    """Validate an incident description."""

    if not isinstance(description, str):
        raise TypeError("description must be a string")
    if not description.strip():
        raise ValueError("description must not be empty")


def _find_category_matches(
    normalized_description: str,
) -> dict[IncidentCategory, tuple[str, ...]]:
    """Return matching keywords grouped by incident category."""

    return {
        category: tuple(
            keyword
            for keyword in config.keywords
            if _contains_keyword(normalized_description, keyword)
        )
        for category, config in _CATEGORY_CONFIG.items()
        if category is not IncidentCategory.UNCLASSIFIED
    }


def _find_winners(
    matches: Mapping[IncidentCategory, tuple[str, ...]],
) -> tuple[IncidentCategory, ...]:
    """Return all categories tied for the highest nonzero score."""

    highest_score = max((len(keywords) for keywords in matches.values()), default=0)
    if highest_score == 0:
        return ()

    return tuple(
        category
        for category, keywords in matches.items()
        if len(keywords) == highest_score
    )


def _unclassified_result(
    matched_keywords: tuple[str, ...] = (),
) -> ClassificationResult:
    """Return an unclassified result with any available evidence."""

    return ClassificationResult(
        IncidentCategory.UNCLASSIFIED,
        matched_keywords,
    )


def classify_incident(description: str) -> ClassificationResult:
    """Classify an incident description using deterministic keyword scoring.

    Each distinct keyword contributes one point to its category. Descriptions
    with no matches or a tie for the highest score are unclassified.

    Raises:
        TypeError: If ``description`` is not a string.
        ValueError: If ``description`` is empty or contains only whitespace.
    """

    _validate_description(description)
    normalized_description = _normalize(description)
    matches = _find_category_matches(normalized_description)
    winners = _find_winners(matches)

    if not winners:
        return _unclassified_result()

    if len(winners) != 1:
        tied_keywords = tuple(
            sorted({
                keyword
                for category in winners
                for keyword in matches[category]
            })
        )
        return _unclassified_result(tied_keywords)

    winner = winners[0]
    return ClassificationResult(winner, matches[winner])


def get_mission_response(category: IncidentCategory) -> MissionResponse:
    """Return the predefined mission response for ``category``.

    Raises:
        TypeError: If ``category`` is not an :class:`IncidentCategory`.
    """

    if not isinstance(category, IncidentCategory):
        raise TypeError("category must be an IncidentCategory")

    return _CATEGORY_CONFIG[category].response


def process_incident(incident: Incident) -> IncidentResult:
    """Validate, classify, and generate a response for an incident.

    Raises:
        TypeError: If the incident or either of its fields has the wrong type.
        ValueError: If the incident identifier or description is empty.
    """

    if not isinstance(incident, Incident):
        raise TypeError("incident must be an Incident")
    if not isinstance(incident.incident_id, str):
        raise TypeError("incident_id must be a string")
    if not incident.incident_id.strip():
        raise ValueError("incident_id must not be empty")

    classification = classify_incident(incident.description)
    response = get_mission_response(classification.category)
    return IncidentResult(
        incident=incident,
        category=classification.category,
        response=response,
        matched_keywords=classification.matched_keywords,
    )


_validate_configuration()
