"""Tests for Mission Control incident processing."""

import unittest
from dataclasses import replace
from unittest.mock import patch

import app.mission as mission
from app.mission import (
    Incident,
    IncidentCategory,
    IncidentResult,
    MissionResponse,
    calculate_priority,
    classify_incident,
    get_mission_response,
    process_incident,
)


class CalculatePriorityTests(unittest.TestCase):
    """Verify priority lookup for known and unknown categories."""

    def test_returns_priority_for_each_known_category(self) -> None:
        expected_priorities = {
            IncidentCategory.THERMAL: "critical",
            IncidentCategory.BATTERY: "high",
            IncidentCategory.MOBILITY: "high",
            IncidentCategory.NAVIGATION: "medium",
            IncidentCategory.COMMUNICATION: "high",
        }

        for category, expected_priority in expected_priorities.items():
            with self.subTest(category=category):
                self.assertEqual(expected_priority, calculate_priority(category))

    def test_returns_low_for_unknown_category(self) -> None:
        self.assertEqual("low", calculate_priority("unknown"))
        self.assertEqual("low", calculate_priority("science"))
        self.assertEqual(
            "low",
            calculate_priority(IncidentCategory.UNCLASSIFIED),
        )

    def test_normalizes_string_category(self) -> None:
        self.assertEqual("critical", calculate_priority(" THERMAL "))

    def test_returns_priority_for_string_categories(self) -> None:
        expected_priorities = {
            "thermal": "critical",
            "battery": "high",
            "mobility": "high",
            "navigation": "medium",
            "communication": "high",
        }

        for category, expected_priority in expected_priorities.items():
            with self.subTest(category=category):
                self.assertEqual(expected_priority, calculate_priority(category))

    def test_rejects_non_string_category(self) -> None:
        for category in (None, 42, []):
            with self.subTest(category=category):
                with self.assertRaisesRegex(
                    TypeError,
                    "category must be an IncidentCategory or string",
                ):
                    calculate_priority(category)  # type: ignore[arg-type]

    def test_empty_and_unclassified_strings_have_low_priority(self) -> None:
        for category in ("", "   ", "unclassified"):
            with self.subTest(category=category):
                self.assertEqual("low", calculate_priority(category))


class ConfigurationTests(unittest.TestCase):
    """Verify that invalid category configuration fails fast."""

    def test_current_configuration_is_valid(self) -> None:
        mission._validate_configuration()

    def test_rejects_missing_category(self) -> None:
        incomplete_config = dict(mission._CATEGORY_CONFIG)
        del incomplete_config[IncidentCategory.THERMAL]

        with patch.dict(
            mission._CATEGORY_CONFIG,
            incomplete_config,
            clear=True,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "category configuration does not match IncidentCategory",
            ):
                mission._validate_configuration()

    def test_rejects_invalid_responses(self) -> None:
        category = IncidentCategory.THERMAL
        config = mission._CATEGORY_CONFIG[category]
        invalid_responses = (
            (
                replace(config.response, category=IncidentCategory.BATTERY),
                "response category does not match thermal",
            ),
            (
                replace(config.response, summary=" "),
                "incomplete response for thermal",
            ),
            (
                replace(config.response, actions=()),
                "incomplete response for thermal",
            ),
            (
                replace(config.response, actions=(" ",)),
                "empty response action for thermal",
            ),
        )

        for response, expected_error in invalid_responses:
            with self.subTest(expected_error=expected_error):
                invalid_config = replace(config, response=response)
                with patch.dict(
                    mission._CATEGORY_CONFIG,
                    {category: invalid_config},
                ):
                    with self.assertRaisesRegex(RuntimeError, expected_error):
                        mission._validate_configuration()

    def test_rejects_invalid_keywords(self) -> None:
        category = IncidentCategory.THERMAL
        config = mission._CATEGORY_CONFIG[category]
        invalid_keyword_sets = (
            (("heat", "heat"), "duplicate keywords for thermal"),
            (("Heat",), "invalid keyword for thermal"),
            (("",), "invalid keyword for thermal"),
        )

        for keywords, expected_error in invalid_keyword_sets:
            with self.subTest(keywords=keywords):
                invalid_config = replace(config, keywords=keywords)
                with patch.dict(
                    mission._CATEGORY_CONFIG,
                    {category: invalid_config},
                ):
                    with self.assertRaisesRegex(RuntimeError, expected_error):
                        mission._validate_configuration()

    def test_rejects_keywords_for_unclassified_category(self) -> None:
        category = IncidentCategory.UNCLASSIFIED
        config = mission._CATEGORY_CONFIG[category]
        invalid_config = replace(config, keywords=("unknown",))

        with patch.dict(
            mission._CATEGORY_CONFIG,
            {category: invalid_config},
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "unclassified category must not define keywords",
            ):
                mission._validate_configuration()


class ClassifyIncidentTests(unittest.TestCase):
    """Verify deterministic incident classification."""

    def test_classifies_each_supported_category(self) -> None:
        cases = {
            "Reactor temperature is rising and cooling is unstable.": (
                IncidentCategory.THERMAL
            ),
            "Battery voltage dropped during charging.": IncidentCategory.BATTERY,
            "The rover wheel motor is stuck.": IncidentCategory.MOBILITY,
            "Position differs from the planned trajectory.": (
                IncidentCategory.NAVIGATION
            ),
            "Telemetry signal was lost after the antenna failed.": (
                IncidentCategory.COMMUNICATION
            ),
        }

        for description, expected_category in cases.items():
            with self.subTest(description=description):
                result = classify_incident(description)
                self.assertEqual(expected_category, result.category)
                self.assertTrue(result.matched_keywords)

    def test_matching_is_case_insensitive_and_handles_punctuation(self) -> None:
        result = classify_incident("The RADIATOR, has excessive HEAT!")

        self.assertEqual(IncidentCategory.THERMAL, result.category)
        self.assertEqual(("heat", "radiator"), result.matched_keywords)

    def test_every_configured_keyword_selects_its_category(self) -> None:
        for category, config in mission._CATEGORY_CONFIG.items():
            if category is IncidentCategory.UNCLASSIFIED:
                continue
            for keyword in config.keywords:
                with self.subTest(category=category, keyword=keyword):
                    result = classify_incident(keyword)
                    self.assertEqual(category, result.category)
                    self.assertEqual((keyword,), result.matched_keywords)

    def test_keyword_must_match_a_complete_word(self) -> None:
        result = classify_incident("The signaler completed an unrelated task.")

        self.assertEqual(IncidentCategory.UNCLASSIFIED, result.category)
        self.assertEqual((), result.matched_keywords)

    def test_repeated_keyword_counts_only_once(self) -> None:
        result = classify_incident("Battery battery battery and radio.")

        self.assertEqual(IncidentCategory.UNCLASSIFIED, result.category)
        self.assertEqual(("battery", "radio"), result.matched_keywords)

    def test_equal_multi_keyword_scores_are_unclassified(self) -> None:
        result = classify_incident(
            "Battery voltage and radio signal failures were detected."
        )

        self.assertEqual(IncidentCategory.UNCLASSIFIED, result.category)
        self.assertEqual(
            ("battery", "radio", "signal", "voltage"),
            result.matched_keywords,
        )

    def test_category_with_highest_score_wins(self) -> None:
        result = classify_incident("Battery voltage is low and radio is offline.")

        self.assertEqual(IncidentCategory.BATTERY, result.category)
        self.assertEqual(("battery", "voltage"), result.matched_keywords)

    def test_normalizes_punctuation_in_multi_word_keyword(self) -> None:
        result = classify_incident("The power-cell is not charging.")

        self.assertEqual(IncidentCategory.BATTERY, result.category)
        self.assertEqual(("charging", "power cell"), result.matched_keywords)

    def test_normalizes_newlines_and_repeated_whitespace(self) -> None:
        result = classify_incident("The power\n\n  cell voltage is low.")

        self.assertEqual(IncidentCategory.BATTERY, result.category)
        self.assertEqual(("power cell", "voltage"), result.matched_keywords)

    def test_punctuation_only_incident_is_unclassified(self) -> None:
        result = classify_incident("... !!!")

        self.assertEqual(IncidentCategory.UNCLASSIFIED, result.category)
        self.assertEqual((), result.matched_keywords)

    def test_unknown_incident_is_unclassified(self) -> None:
        result = classify_incident("An unexpected condition was observed.")

        self.assertEqual(IncidentCategory.UNCLASSIFIED, result.category)
        self.assertEqual((), result.matched_keywords)

    def test_empty_description_is_rejected(self) -> None:
        for description in ("", "   "):
            with self.subTest(description=description):
                with self.assertRaisesRegex(
                    ValueError,
                    "description must not be empty",
                ):
                    classify_incident(description)

    def test_non_string_description_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "description must be a string"):
            classify_incident(None)  # type: ignore[arg-type]


class MissionResponseTests(unittest.TestCase):
    """Verify that every category has a useful response."""

    def test_every_category_has_a_response(self) -> None:
        for category in IncidentCategory:
            with self.subTest(category=category):
                response = get_mission_response(category)
                self.assertIsInstance(response, MissionResponse)
                self.assertEqual(category, response.category)
                self.assertTrue(response.summary)
                self.assertTrue(response.actions)
                self.assertTrue(all(response.actions))

    def test_invalid_category_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "IncidentCategory"):
            get_mission_response("thermal")  # type: ignore[arg-type]

    def test_thermal_response_contains_ordered_actions(self) -> None:
        response = get_mission_response(IncidentCategory.THERMAL)

        self.assertEqual("Stabilize spacecraft temperature.", response.summary)
        self.assertEqual("Reduce nonessential system load.", response.actions[0])
        self.assertIn("temperature", response.actions[-1].lower())


class ProcessIncidentTests(unittest.TestCase):
    """Verify the complete incident-processing workflow."""

    def test_returns_structured_result(self) -> None:
        incident = Incident("AUR-104", "Battery voltage is falling.")

        result = process_incident(incident)

        self.assertIsInstance(result, IncidentResult)
        self.assertIs(result.incident, incident)
        self.assertEqual(IncidentCategory.BATTERY, result.category)
        self.assertEqual(result.category, result.response.category)
        self.assertEqual(("battery", "voltage"), result.matched_keywords)

    def test_processes_every_classified_category(self) -> None:
        cases = {
            "Temperature and cooling are unstable.": IncidentCategory.THERMAL,
            "Battery voltage is falling.": IncidentCategory.BATTERY,
            "The wheel motor is stuck.": IncidentCategory.MOBILITY,
            "Position differs from the trajectory.": IncidentCategory.NAVIGATION,
            "The antenna lost its signal.": IncidentCategory.COMMUNICATION,
        }

        for index, (description, expected_category) in enumerate(
            cases.items(),
            start=1,
        ):
            with self.subTest(category=expected_category):
                result = process_incident(
                    Incident(f"AUR-{index:03}", description)
                )
                self.assertEqual(expected_category, result.category)
                self.assertEqual(expected_category, result.response.category)
                self.assertTrue(result.matched_keywords)

    def test_unclassified_incident_requests_human_review(self) -> None:
        result = process_incident(
            Incident("AUR-105", "An unexpected condition was observed.")
        )

        self.assertEqual(IncidentCategory.UNCLASSIFIED, result.category)
        self.assertIn("human review", result.response.summary.lower())

    def test_empty_incident_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "incident_id must not be empty"):
            process_incident(Incident(" ", "Battery voltage is low."))

    def test_non_incident_value_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "incident must be an Incident"):
            process_incident("Battery voltage is low.")  # type: ignore[arg-type]

    def test_non_string_incident_id_is_rejected(self) -> None:
        incident = Incident(123, "Battery voltage is low.")  # type: ignore[arg-type]

        with self.assertRaisesRegex(TypeError, "incident_id must be a string"):
            process_incident(incident)

    def test_invalid_description_is_rejected_during_processing(self) -> None:
        with self.assertRaisesRegex(ValueError, "description must not be empty"):
            process_incident(Incident("AUR-106", " "))

    def test_non_string_description_is_rejected_during_processing(self) -> None:
        incident = Incident("AUR-107", None)  # type: ignore[arg-type]

        with self.assertRaisesRegex(TypeError, "description must be a string"):
            process_incident(incident)


if __name__ == "__main__":
    unittest.main()