import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from backend.templates import EDITING_TEMPLATES, list_templates, get_template
from backend.video_renderer import _pick_transition, TRANSITION_POOL


def test_templates_transition_mode():
    print("\n--- Test 1: Templates transition_mode Field Verification ---")
    assert len(EDITING_TEMPLATES) >= 5, "Expected at least 5 editing templates"
    
    for tmpl_id, tmpl in EDITING_TEMPLATES.items():
        assert "transition_mode" in tmpl, f"Template '{tmpl_id}' missing 'transition_mode'"
        assert tmpl["transition_mode"] in ("fixed", "random"), (
            f"Template '{tmpl_id}' has invalid transition_mode: {tmpl['transition_mode']}"
        )
        assert "transition" in tmpl, f"Template '{tmpl_id}' missing fallback 'transition'"
        print(f"  ✓ Template '{tmpl_id}': transition='{tmpl['transition']}', transition_mode='{tmpl['transition_mode']}'")
    
    print("✅ All templates have valid transition_mode and fallback transition!")


def test_fixed_mode_behavior():
    print("\n--- Test 2: Fixed Mode Behavior ---")
    for t in ["fade", "smoothleft", "zoomin", "fadefast", "none"]:
        chosen = _pick_transition(0, mode="fixed", fallback=t)
        assert chosen == t, f"Expected {t}, got {chosen}"
    print("✅ Fixed mode consistently returns fallback transition.")


def test_no_consecutive_duplicates_random():
    print("\n--- Test 3: Random Mode No Consecutive Duplicates ---")
    last_picked = None
    sequence = []
    
    # Generate 150 consecutive transitions
    for i in range(150):
        t = _pick_transition(i, mode="random", fallback="smoothleft", last_picked=last_picked)
        assert t in TRANSITION_POOL, f"Invalid transition chosen: {t}"
        assert t != last_picked, f"Consecutive duplicate detected at index {i}: '{t}' was picked right after '{last_picked}'"
        sequence.append(t)
        last_picked = t

    print(f"  Sample sequence of 10 boundaries: {sequence[:10]}")
    print("✅ Verified 150 consecutive boundaries with zero repeated transitions!")


def test_random_non_deterministic():
    print("\n--- Test 4: Random Mode Non-Deterministic Output Across Runs ---")
    # Simulate picking 10 transitions across script run A and run B
    seq_a = []
    last_a = None
    for i in range(10):
        t = _pick_transition(i, mode="random", fallback="smoothleft", last_picked=last_a)
        seq_a.append(t)
        last_a = t

    seq_b = []
    last_b = None
    for i in range(10):
        t = _pick_transition(i, mode="random", fallback="smoothleft", last_picked=last_b)
        seq_b.append(t)
        last_b = t

    print(f"  Run A: {seq_a}")
    print(f"  Run B: {seq_b}")
    assert seq_a != seq_b, "Run A and Run B produced identical sequences! Should be stochastic random choice."
    print("✅ Verified different sequence produced on consecutive runs!")


def test_backward_compatibility():
    print("\n--- Test 5: Backward Compatibility for Existing Callers ---")
    # Caller passing only (idx, mode_string) where mode_string is a direct transition name
    res1 = _pick_transition(0, "fade")
    assert res1 == "fade", f"Expected 'fade', got {res1}"

    # Caller passing (idx, "random") without kwargs
    res2 = _pick_transition(0, "random")
    assert res2 in TRANSITION_POOL, f"Expected valid transition from pool, got {res2}"

    # Caller passing default mode without specifying fallback
    res3 = _pick_transition(0)
    assert res3 == "smoothleft", f"Expected default 'smoothleft', got {res3}"

    print("✅ Backward compatibility verified for legacy callers!")


if __name__ == "__main__":
    test_templates_transition_mode()
    test_fixed_mode_behavior()
    test_no_consecutive_duplicates_random()
    test_random_non_deterministic()
    test_backward_compatibility()
    print("\n==========================================")
    print("🎉 ALL TRANSITION TESTS PASSED SUCCESSFULLY!")
    print("==========================================")
