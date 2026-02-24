"""
EEG Experiment: Spelling Backwards vs. Quiet Meditation
========================================================
100 trials (50 each condition) with LabStreamingLayer markers.
Each trial lasts 5 seconds with a 1-second inter-trial interval.

LSL Markers:
  "spell_start"      - onset of a spelling-backwards trial
  "spell_end"        - offset of a spelling-backwards trial
  "meditate_start"   - onset of a meditation trial
  "meditate_end"     - offset of a meditation trial

Requirements:
  pip install pylsl
"""

import random
import time
from pylsl import StreamInfo, StreamOutlet


# ── Configuration ──────────────────────────────────────────────────────────────
TRIAL_DURATION = 5        # seconds
ITI_DURATION = 1          # inter-trial interval in seconds
N_SPELL = 50
N_MEDITATE = 50

FIVE_LETTER_WORDS = [
    "apple", "brain", "chair", "dance", "eagle",
    "flame", "grape", "house", "ivory", "joker",
    "knelt", "lemon", "mango", "night", "ocean",
    "piano", "queen", "river", "stone", "tiger",
    "ultra", "vivid", "whale", "xenon", "youth",
    "zebra", "blaze", "crest", "drift", "flint",
    "globe", "haste", "jazzy", "knack", "lymph",
    "merit", "noble", "ozone", "plumb", "quilt",
    "ridge", "shelf", "trove", "unity", "vapor",
    "wrist", "oxide", "yearn", "zonal", "charm",
]


def create_lsl_stream():
    """Create and return an LSL outlet for experiment markers."""
    info = StreamInfo(
        name="ExperimentMarkers",
        type="Markers",
        channel_count=1,
        nominal_srate=0,            # irregular rate
        channel_format="string",
        source_id="spelling_meditation_exp",
    )
    outlet = StreamOutlet(info)
    print("[LSL] Stream 'ExperimentMarkers' created. Waiting for consumer...")
    time.sleep(2)  # brief pause so a recorder can discover the stream
    return outlet


def send_marker(outlet, marker):
    """Push a single string marker to the LSL stream."""
    outlet.push_sample([marker])
    print(f"  [LSL marker] {marker}")


def build_trial_list():
    """Return a randomised list of 100 trial dicts."""
    words = random.sample(FIVE_LETTER_WORDS, N_SPELL)  # unique word per spell trial
    trials = []
    for w in words:
        trials.append({"type": "spell", "word": w})
    for _ in range(N_MEDITATE):
        trials.append({"type": "meditate"})
    random.shuffle(trials)
    return trials


def run_experiment():
    outlet = create_lsl_stream()
    trials = build_trial_list()
    total = len(trials)

    input("\nPress ENTER to start the experiment...")
    print(f"\n{'='*60}")
    print(f"  Starting experiment: {total} trials")
    print(f"  Trial duration: {TRIAL_DURATION}s | ITI: {ITI_DURATION}s")
    print(f"{'='*60}\n")
    time.sleep(1)

    for i, trial in enumerate(trials, start=1):
        if trial["type"] == "spell":
            word = trial["word"]
            print(f"[Trial {i:3d}/{total}]  SPELL BACKWARDS: concentrate on spelling "
                  f"'{word.upper()}' backwards")
            send_marker(outlet, "spell_start")
            time.sleep(TRIAL_DURATION)
            send_marker(outlet, "spell_end")
        else:
            print(f"[Trial {i:3d}/{total}]  MEDITATE: close your eyes and meditate quietly")
            send_marker(outlet, "meditate_start")
            time.sleep(TRIAL_DURATION)
            send_marker(outlet, "meditate_end")

        # Inter-trial interval (skip after last trial)
        if i < total:
            print(f"  ... rest ({ITI_DURATION}s) ...")
            time.sleep(ITI_DURATION)

    print(f"\n{'='*60}")
    print("  Experiment complete! Thank you.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_experiment()
