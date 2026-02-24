"""
EEG Experiment: Spelling Backwards vs. Quiet Meditation
========================================================
Full-screen visual presentation using Tkinter with LSL markers.

100 trials (50 spelling backwards, 50 meditation) in random order.
Each trial: 5 seconds with 1-second fixation cross between trials.

LSL Markers:
  "spell_start"      - onset of spelling-backwards trial
  "spell_end"        - offset of spelling-backwards trial
  "meditate_start"   - onset of meditation trial
  "meditate_end"     - offset of meditation trial

Requirements:
  pip install pylsl
  (Tkinter is included with Python)
"""

import random
import tkinter as tk
from pylsl import StreamInfo, StreamOutlet


# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
TRIAL_DURATION_MS = 5000   # milliseconds per trial
ITI_DURATION_MS = 1000     # inter-trial interval (fixation cross)
N_SPELL = 50
N_MEDITATE = 50

BG_COLOR = "#2B2B2B"
TEXT_COLOR = "#FFFFFF"
ACCENT_COLOR = "#66CCFF"
FIXATION_COLOR = "#888888"
INSTRUCTION_COLOR = "#DDDDDD"

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


# ═══════════════════════════════════════════════════════════════════════════════
#  LSL SETUP
# ═══════════════════════════════════════════════════════════════════════════════
def create_lsl_stream():
    info = StreamInfo(
        name="ExperimentMarkers",
        type="Markers",
        channel_count=1,
        nominal_srate=0,
        channel_format="string",
        source_id="spelling_meditation_exp",
    )
    return StreamOutlet(info)


def send_marker(outlet, marker):
    outlet.push_sample([marker])


# ═══════════════════════════════════════════════════════════════════════════════
#  TRIAL LIST
# ═══════════════════════════════════════════════════════════════════════════════
def build_trial_list():
    words = random.sample(FIVE_LETTER_WORDS, N_SPELL)
    trials = []
    for w in words:
        trials.append({"type": "spell", "word": w})
    for _ in range(N_MEDITATE):
        trials.append({"type": "meditate"})
    random.shuffle(trials)
    return trials


# ═══════════════════════════════════════════════════════════════════════════════
#  EXPERIMENT APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════
class ExperimentApp:
    def __init__(self):
        # ── LSL ────────────────────────────────────────────────────────────
        self.outlet = create_lsl_stream()

        # ── Trial data ─────────────────────────────────────────────────────
        self.trials = build_trial_list()
        self.current_trial = 0
        self.countdown_remaining = 0
        self.countdown_id = None

        # ── Tkinter window ─────────────────────────────────────────────────
        self.root = tk.Tk()
        self.root.title("EEG Experiment")
        self.root.configure(bg=BG_COLOR)
        self.root.attributes("-fullscreen", True)
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("<space>", self._on_space)

        # ── Canvas (covers entire screen) ──────────────────────────────────
        self.canvas = tk.Canvas(
            self.root, bg=BG_COLOR, highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Get screen dimensions after packing
        self.root.update_idletasks()
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.cx = self.screen_w // 2
        self.cy = self.screen_h // 2

        # ── State ──────────────────────────────────────────────────────────
        self.state = "welcome"  # welcome -> running -> end
        self._show_welcome()

    # ───────────────────────────────────────────────────────────────────────
    #  SCREENS
    # ───────────────────────────────────────────────────────────────────────
    def _clear(self):
        """Clear everything from the canvas."""
        if self.countdown_id is not None:
            self.root.after_cancel(self.countdown_id)
            self.countdown_id = None
        self.canvas.delete("all")

    def _show_welcome(self):
        self._clear()
        welcome = (
            "Welcome to the Experiment\n\n"
            "In this study you will complete 100 trials.\n\n"
            "On each trial you will either:\n"
            "  \u2022 See a word and spell it BACKWARDS in your mind\n"
            "  \u2022 Close your eyes and meditate quietly\n\n"
            "Each trial lasts 5 seconds.\n"
            "A fixation cross (+) will appear between trials.\n\n"
            "Press ESCAPE at any time to quit.\n\n\n"
            "Press SPACEBAR to begin"
        )
        self.canvas.create_text(
            self.cx, self.cy, text=welcome,
            fill=INSTRUCTION_COLOR, font=("Arial", 28),
            justify=tk.CENTER, width=self.screen_w * 0.7,
        )

    def _show_fixation(self):
        """Show fixation cross, then start next trial after ITI."""
        self._clear()
        self.canvas.create_text(
            self.cx, self.cy, text="+",
            fill=FIXATION_COLOR, font=("Arial", 72),
        )
        self.root.after(ITI_DURATION_MS, self._start_trial)

    def _show_spell(self, word, remaining_sec):
        """Draw the spelling-backwards screen."""
        self._clear()
        # Instruction
        self.canvas.create_text(
            self.cx, self.cy - 100,
            text="Spell this word BACKWARDS in your mind:",
            fill=TEXT_COLOR, font=("Arial", 32), justify=tk.CENTER,
        )
        # The word
        self.canvas.create_text(
            self.cx, self.cy + 20,
            text=word.upper(),
            fill=ACCENT_COLOR, font=("Arial", 80, "bold"), justify=tk.CENTER,
        )
        # Countdown
        self.canvas.create_text(
            self.cx, self.cy + 160,
            text=f"{remaining_sec}s",
            fill=FIXATION_COLOR, font=("Arial", 24),
        )
        # Trial counter
        self.canvas.create_text(
            self.screen_w - 30, 30,
            text=f"{self.current_trial + 1} / {len(self.trials)}",
            fill=FIXATION_COLOR, font=("Arial", 18), anchor=tk.NE,
        )

    def _show_meditate(self, remaining_sec):
        """Draw the meditation screen."""
        self._clear()
        self.canvas.create_text(
            self.cx, self.cy - 20,
            text="Close your eyes and\nmeditate quietly",
            fill=TEXT_COLOR, font=("Arial", 48), justify=tk.CENTER,
        )
        self.canvas.create_text(
            self.cx, self.cy + 140,
            text=f"{remaining_sec}s",
            fill=FIXATION_COLOR, font=("Arial", 24),
        )
        self.canvas.create_text(
            self.screen_w - 30, 30,
            text=f"{self.current_trial + 1} / {len(self.trials)}",
            fill=FIXATION_COLOR, font=("Arial", 18), anchor=tk.NE,
        )

    def _show_end(self):
        self._clear()
        self.state = "end"
        end_msg = (
            "Experiment Complete!\n\n"
            "Thank you for participating.\n\n\n"
            "Press SPACEBAR to exit"
        )
        self.canvas.create_text(
            self.cx, self.cy, text=end_msg,
            fill=INSTRUCTION_COLOR, font=("Arial", 36),
            justify=tk.CENTER,
        )

    # ───────────────────────────────────────────────────────────────────────
    #  TRIAL LOGIC
    # ───────────────────────────────────────────────────────────────────────
    def _start_trial(self):
        """Begin the current trial."""
        if self.current_trial >= len(self.trials):
            self._show_end()
            return

        trial = self.trials[self.current_trial]
        self.countdown_remaining = TRIAL_DURATION_MS // 1000

        if trial["type"] == "spell":
            send_marker(self.outlet, "spell_start")
            self._show_spell(trial["word"], self.countdown_remaining)
            self._start_countdown("spell", trial["word"])
        else:
            send_marker(self.outlet, "meditate_start")
            self._show_meditate(self.countdown_remaining)
            self._start_countdown("meditate", None)

    def _start_countdown(self, trial_type, word):
        """Tick the countdown each second; end trial when done."""
        if self.countdown_remaining <= 0:
            # Trial is over
            if trial_type == "spell":
                send_marker(self.outlet, "spell_end")
            else:
                send_marker(self.outlet, "meditate_end")

            self.current_trial += 1

            if self.current_trial >= len(self.trials):
                self._show_end()
            else:
                self._show_fixation()
            return

        # Schedule next tick
        self.countdown_id = self.root.after(
            1000, self._tick_countdown, trial_type, word
        )

    def _tick_countdown(self, trial_type, word):
        """Called every second to update the display."""
        self.countdown_remaining -= 1

        if self.countdown_remaining <= 0:
            # End of trial
            self._start_countdown(trial_type, word)
            return

        # Redraw with updated countdown
        if trial_type == "spell":
            self._show_spell(word, self.countdown_remaining)
        else:
            self._show_meditate(self.countdown_remaining)

        # Schedule next tick
        self.countdown_id = self.root.after(
            1000, self._tick_countdown, trial_type, word
        )

    # ───────────────────────────────────────────────────────────────────────
    #  INPUT HANDLERS
    # ───────────────────────────────────────────────────────────────────────
    def _on_space(self, event):
        if self.state == "welcome":
            self.state = "running"
            self._show_fixation()
        elif self.state == "end":
            self.root.destroy()

    def _on_escape(self, event):
        self.root.destroy()

    # ───────────────────────────────────────────────────────────────────────
    #  RUN
    # ───────────────────────────────────────────────────────────────────────
    def run(self):
        self.root.mainloop()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = ExperimentApp()
    app.run()
