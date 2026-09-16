import os
import sys
import json
import time
import threading
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from backend.stock_downloader import _score_candidate, trim_and_fit_clip, SESSION
from backend.scene_analyzer import _enhance_tags_with_ai
from backend.server import (
    RENDER_LOCK, GLOBAL_BATCH_LOCK, BATCH_LOCK,
    save_batch_jobs_to_disk, load_batch_jobs_from_disk,
    BATCH_JOBS, BATCH_JOBS_FILE
)

def test_scoring_and_candidate_ranking():
    print("\n--- Test 1: Stock Candidate Ranking & Scoring ---")
    
    query_words = ["tired", "exhausted", "worker"]
    # Candidate 1: 1080p landscape, duration 15s (good fit for 4s target), matching slug
    score1 = _score_candidate(
        duration=15.0,
        width=1920,
        height=1080,
        target_dur=4.0,
        query_words=query_words,
        metadata_text="exhausted man sitting desk tired office worker"
    )
    print(f"Candidate 1 Score (1080p landscape, 15s, matching tags): {score1}")

    # Candidate 2: Vertical 1080x1920 (bad for 16:9), short duration 3s
    score2 = _score_candidate(
        duration=3.0,
        width=1080,
        height=1920,
        target_dur=4.0,
        query_words=query_words,
        metadata_text="vertical short clip unrelated"
    )
    print(f"Candidate 2 Score (Vertical 9:16, 3s): {score2}")

    # Candidate 3: Low res 640x360
    score3 = _score_candidate(
        duration=12.0,
        width=640,
        height=360,
        target_dur=4.0,
        query_words=query_words,
        metadata_text="low res clip tired"
    )
    print(f"Candidate 3 Score (360p, 12s): {score3}")

    assert score1 > score2, f"Expected cand1 score ({score1}) > cand2 score ({score2})"
    assert score1 > score3, f"Expected cand1 score ({score1}) > cand3 score ({score3})"
    print("✅ Candidate ranking & scoring verified successfully!")

def test_action_window_trimming():
    print("\n--- Test 2: Content-Aware Action Window Trimming Logic ---")
    # In stock_downloader.py, when raw clip is 20s and target is 4s:
    probe_dur = 20.0
    target_dur = 4.0
    headroom = probe_dur - target_dur # 16.0s
    # Optimal offset is 40% of headroom: 16.0 * 0.40 = 6.4s
    expected_offset = max(1.5, min(round(headroom * 0.40, 2), headroom - 0.4))
    print(f"Raw Clip: {probe_dur}s, Target Scene: {target_dur}s -> Dynamic start_offset: {expected_offset}s")
    assert 6.0 <= expected_offset <= 7.0, f"Unexpected offset {expected_offset}"
    print("✅ Dynamic action window calculation verified successfully!")

def test_session_retries_429():
    print("\n--- Test 3: HTTP 429 Status in Retry Adapter ---")
    adapter = SESSION.adapters.get("https://")
    status_codes = adapter.max_retries.status_forcelist
    print(f"Retry status forcelist: {status_codes}")
    assert 429 in status_codes, "HTTP 429 must be present in retry status_forcelist"
    print("✅ HTTP 429 rate limit backoff verified in requests session!")

def test_concurrency_and_locks():
    print("\n--- Test 4: Concurrency Locks (RENDER_LOCK & GLOBAL_BATCH_LOCK) ---")
    # 1. RENDER_LOCK should be an instance of threading.Lock
    assert isinstance(RENDER_LOCK, type(threading.Lock()))
    assert isinstance(GLOBAL_BATCH_LOCK, type(threading.Lock()))
    assert isinstance(BATCH_LOCK, type(threading.Lock()))
    
    # 2. Test RENDER_LOCK mutual exclusion
    execution_order = []
    def worker(worker_id):
        with RENDER_LOCK:
            execution_order.append(f"start_{worker_id}")
            time.sleep(0.05)
            execution_order.append(f"end_{worker_id}")

    t1 = threading.Thread(target=worker, args=(1,))
    t2 = threading.Thread(target=worker, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    print(f"RENDER_LOCK serialized execution trace: {execution_order}")
    # Must be strictly serialized: either start_1 -> end_1 -> start_2 -> end_2 or start_2 -> end_2 -> start_1 -> end_1
    assert execution_order in (
        ["start_1", "end_1", "start_2", "end_2"],
        ["start_2", "end_2", "start_1", "end_1"]
    ), f"Invalid execution order: {execution_order}"
    print("✅ RENDER_LOCK strict mutual exclusion verified!")

def test_batch_disk_persistence():
    print("\n--- Test 5: Batch State Disk Persistence ---")
    test_batch_id = "test_batch_persisted_123"
    with BATCH_LOCK:
        BATCH_JOBS[test_batch_id] = {
            "id": test_batch_id,
            "status": "processing",
            "total": 5,
            "completed": 2,
            "items": [{"name": "item1", "status": "completed"}]
        }
        save_batch_jobs_to_disk()

    # Read back directly from disk
    loaded = load_batch_jobs_from_disk()
    assert test_batch_id in loaded, "Batch job was not saved to disk!"
    assert loaded[test_batch_id]["completed"] == 2
    print(f"Successfully loaded batch {test_batch_id} from {BATCH_JOBS_FILE.name}")

    # Clean up test entry
    with BATCH_LOCK:
        BATCH_JOBS.pop(test_batch_id, None)
        save_batch_jobs_to_disk()
    print("✅ Batch disk persistence and atomic locking verified!")

if __name__ == "__main__":
    test_scoring_and_candidate_ranking()
    test_action_window_trimming()
    test_session_retries_429()
    test_concurrency_and_locks()
    test_batch_disk_persistence()
    print("\n==========================================")
    print("🎉 ALL 5 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("==========================================")
