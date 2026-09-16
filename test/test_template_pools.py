import os
import sys
import threading
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from backend.templates import (
    EDITING_TEMPLATES,
    get_template,
    resolve_template_variant
)


def test_template_pools_structure():
    print("\n--- Test 1: Template Pools Structure & Default Keys ---")
    for tmpl_id, tmpl in EDITING_TEMPLATES.items():
        assert "bgm_track" in tmpl, f"Template {tmpl_id} missing default 'bgm_track'"
        assert "caption_style" in tmpl, f"Template {tmpl_id} missing default 'caption_style'"
        assert "bgm_track_pool" in tmpl, f"Template {tmpl_id} missing 'bgm_track_pool'"
        assert "caption_style_pool" in tmpl, f"Template {tmpl_id} missing 'caption_style_pool'"
        
        assert isinstance(tmpl["bgm_track_pool"], list) and len(tmpl["bgm_track_pool"]) >= 2
        assert isinstance(tmpl["caption_style_pool"], list) and len(tmpl["caption_style_pool"]) >= 2
        print(f"  ✓ Template '{tmpl_id}': default BGM={tmpl['bgm_track']}, BGM pool={tmpl['bgm_track_pool']}, Caption pool={tmpl['caption_style_pool']}")
    print("✅ All template pools and defaults correctly structured!")


def test_single_video_unaffected():
    print("\n--- Test 2: Single-Video get_template() Unaffected ---")
    # Single-video generator calls get_template() directly
    for tmpl_id in EDITING_TEMPLATES.keys():
        t = get_template(tmpl_id)
        # Should return base dict with default single values
        assert t["bgm_track"] == EDITING_TEMPLATES[tmpl_id]["bgm_track"]
        assert t["caption_style"] == EDITING_TEMPLATES[tmpl_id]["caption_style"]
    print("✅ get_template() produces exact single default values with zero disruption to single-video mode!")


def test_resolve_template_variant_with_exclude():
    print("\n--- Test 3: resolve_template_variant() & Exclude Logic ---")
    tmpl_id = "shorts_viral"
    base = get_template(tmpl_id)
    
    # Run multiple times with exclude to ensure the excluded value is never picked
    excluded_bgm = "lofi_chill.mp3"
    excluded_cap = "capcut-yellow"
    
    for _ in range(50):
        v = resolve_template_variant(tmpl_id, exclude={"bgm_track": excluded_bgm, "caption_style": excluded_cap})
        assert v["bgm_track"] != excluded_bgm, f"Excluded BGM {excluded_bgm} was picked!"
        assert v["caption_style"] != excluded_cap, f"Excluded caption {excluded_cap} was picked!"
        assert v["bgm_track"] in base["bgm_track_pool"]
        assert v["caption_style"] in base["caption_style_pool"]

    print("✅ resolve_template_variant() successfully avoids back-to-back excluded values!")


def test_batch_variation_across_5_videos():
    print("\n--- Test 4: Batch of 6 Videos Has Visible Variation & No Back-To-Back Repeats ---")
    tmpl_id = "shorts_viral"
    batch_results = []
    
    last_used = {"bgm_track": None, "caption_style": None}
    last_used_lock = threading.Lock()
    
    def simulate_worker(item_idx):
        with last_used_lock:
            variant = resolve_template_variant(tmpl_id, exclude=last_used)
            last_used["bgm_track"] = variant["bgm_track"]
            last_used["caption_style"] = variant["caption_style"]
        return variant

    for i in range(6):
        variant = simulate_worker(i)
        batch_results.append({
            "idx": i,
            "bgm_track": variant["bgm_track"],
            "caption_style": variant["caption_style"]
        })
        print(f"  Item #{i}: BGM='{variant['bgm_track']}', Caption='{variant['caption_style']}'")

    # 1. Check for visible variation across the batch (not all identical)
    unique_bgms = set(r["bgm_track"] for r in batch_results)
    unique_captions = set(r["caption_style"] for r in batch_results)
    
    assert len(unique_bgms) > 1, f"Expected variation in BGM tracks across batch, got: {unique_bgms}"
    assert len(unique_captions) > 1, f"Expected variation in Caption styles across batch, got: {unique_captions}"

    # 2. Check that no two consecutive videos have identical BGM or identical caption style
    for i in range(len(batch_results) - 1):
        curr = batch_results[i]
        nxt = batch_results[i + 1]
        assert curr["bgm_track"] != nxt["bgm_track"], f"Consecutive identical BGM at {i} -> {i+1}: {curr['bgm_track']}"
        assert curr["caption_style"] != nxt["caption_style"], f"Consecutive identical Caption at {i} -> {i+1}: {curr['caption_style']}"

    print(f"✅ Distinct BGMs used: {unique_bgms}")
    print(f"✅ Distinct Captions used: {unique_captions}")
    print("✅ Batch variation verified with zero consecutive repeats!")


def test_thread_safe_concurrent_batch():
    print("\n--- Test 5: Concurrent Multi-Worker Batch Thread-Safety ---")
    from concurrent.futures import ThreadPoolExecutor
    tmpl_id = "tech_explainer"
    last_used = {"bgm_track": None, "caption_style": None}
    last_used_lock = threading.Lock()
    results = [None] * 10

    def process_item(idx):
        with last_used_lock:
            v = resolve_template_variant(tmpl_id, exclude=last_used)
            last_used["bgm_track"] = v["bgm_track"]
            last_used["caption_style"] = v["caption_style"]
        results[idx] = v

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(process_item, range(10)))

    # Ensure all 10 completed with valid resolved variants
    assert all(r is not None for r in results)
    unique_bgms = set(r["bgm_track"] for r in results)
    unique_caps = set(r["caption_style"] for r in results)
    assert len(unique_bgms) > 1
    assert len(unique_caps) > 1
    print(f"✅ 10 concurrent items resolved successfully: {len(unique_bgms)} unique BGMs, {len(unique_caps)} unique Caption styles!")


if __name__ == "__main__":
    test_template_pools_structure()
    test_single_video_unaffected()
    test_resolve_template_variant_with_exclude()
    test_batch_variation_across_5_videos()
    test_thread_safe_concurrent_batch()
    print("\n==========================================")
    print("🎉 ALL TEMPLATE POOL & VARIANT TESTS PASSED!")
    print("==========================================")
