"""
Regression tests for merge_analysis_results' representative-selection rule
(main.py). Plain assert-based script, matching this directory's existing
testing convention (match_damage.py) rather than adding a pytest
dependency. Run with:

    python test_merge.py

Does not load the YOLO models or touch any AI threshold — these are pure
dict-merging tests against synthetic per-image results shaped like
analyze_image()'s real output.
"""

from main import merge_analysis_results


def _result(filename, part, severity, damage_percentage, damage_confidence,
            part_confidence, status, recommended_action):

    return {
        "filename": filename,
        "analysis": {
            "damage_detected": True,
            "damaged_parts": [
                {
                    "part": part,
                    "severity": severity,
                    "damage_percentage": damage_percentage,
                    "damage_confidence": damage_confidence,
                    "part_confidence": part_confidence,
                    "status": status,
                    "recommended_action": recommended_action,
                }
            ],
            "summary": {},
        },
    }


def test_representative_kept_as_one_unit_not_reassembled():
    # Two Accepted observations of the same part. image_a has the higher
    # damage_percentage but LOWER confidence; image_b has lower damage
    # but HIGHER confidence. The old (buggy) merge logic would report
    # image_a's damage_percentage paired with image_b's confidence — a
    # combination neither image actually produced. The fix must keep
    # image_a's full record together, since it wins on damage_percentage.
    results = [
        _result("image_a.jpg", "Rear bumper", "Moderate", 36.14, 0.33, 0.71,
                "Accepted", "Repair"),
        _result("image_b.jpg", "Rear bumper", "Moderate", 34.29, 0.87, 0.80,
                "Accepted", "Repair"),
    ]

    merged = merge_analysis_results(results)
    part = merged["damaged_parts"][0]

    assert part["damage_percentage"] == 36.14
    # damage_confidence must match the SAME observation as damage_percentage
    # (image_a, 0.33) — not the max across images (0.87).
    assert part["damage_confidence"] == 0.33
    assert part["part_confidence"] == 0.71

    # Aggregate metadata is tracked separately and IS allowed to reflect
    # the max across all images.
    assert part["max_damage_confidence_seen"] == 0.87
    assert part["max_part_confidence_seen"] == 0.80
    assert part["observation_count"] == 2
    assert part["detected_in_images"] == ["image_a.jpg", "image_b.jpg"]


def test_accepted_observation_always_beats_review_required():
    # image_a is Review Required with a large (candidate-mask) damage
    # percentage; image_b is Accepted with a smaller (trusted-mask)
    # percentage. Trust must win regardless of the raw percentage.
    results = [
        _result("image_a.jpg", "Headlight - (R)", "Uncertain", 79.55, 0.08, 0.61,
                "Review Required", "Manual Inspection"),
        _result("image_b.jpg", "Headlight - (R)", "Severe", 27.86, 0.69, 0.44,
                "Accepted", "Replace"),
    ]

    merged = merge_analysis_results(results)
    part = merged["damaged_parts"][0]

    assert part["status"] == "Accepted"
    assert part["severity"] == "Severe"
    assert part["damage_percentage"] == 27.86
    assert part["damage_confidence"] == 0.69
    assert part["observation_count"] == 2


def test_higher_damage_percentage_wins_within_same_status_tier():
    results = [
        _result("image_a.jpg", "Car hood", "Moderate", 20.0, 0.5, 0.9,
                "Accepted", "Repair + Repaint"),
        _result("image_b.jpg", "Car hood", "Severe", 50.25, 0.26, 0.9,
                "Accepted", "Replace / Major Repair"),
    ]

    merged = merge_analysis_results(results)
    part = merged["damaged_parts"][0]

    assert part["severity"] == "Severe"
    assert part["damage_percentage"] == 50.25
    assert part["recommended_action"] == "Replace / Major Repair"


def test_single_observation_part_has_observation_count_one():
    results = [
        _result("image_a.jpg", "Front bumper", "Minor", 8.0, 0.4, 0.6,
                "Review Required", "Manual Inspection"),
    ]

    merged = merge_analysis_results(results)
    part = merged["damaged_parts"][0]

    assert part["observation_count"] == 1
    assert part["detected_in_images"] == ["image_a.jpg"]
    assert part["max_damage_confidence_seen"] == 0.4
    assert part["max_part_confidence_seen"] == 0.6


def test_merged_output_carries_no_pricing_fields():
    # The ai-service response contract must never include cost data —
    # pricing is the backend's responsibility (services/cost_model),
    # since it requires vehicle metadata this service never sees.
    results = [
        _result("image_a.jpg", "Rear bumper", "Moderate", 36.14, 0.33, 0.71,
                "Accepted", "Repair"),
    ]

    merged = merge_analysis_results(results)
    part = merged["damaged_parts"][0]

    assert "estimated_cost" not in part
    assert "estimated_cost_min" not in merged["summary"]
    assert "estimated_cost_max" not in merged["summary"]


def _run_all():
    tests = [
        test_representative_kept_as_one_unit_not_reassembled,
        test_accepted_observation_always_beats_review_required,
        test_higher_damage_percentage_wins_within_same_status_tier,
        test_single_observation_part_has_observation_count_one,
        test_merged_output_carries_no_pricing_fields,
    ]

    failures = 0

    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as error:
            failures += 1
            print(f"FAIL  {test.__name__}: {error}")

    print()
    if failures:
        print(f"{failures} test(s) failed.")
        raise SystemExit(1)

    print(f"All {len(tests)} tests passed.")


if __name__ == "__main__":
    _run_all()
