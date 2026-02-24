#!/usr/bin/env python3
"""EEG state-labeling participant runner.

Runs a full-screen focus vs relaxation session and emits LSL markers for
active-state start/end boundaries only.
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from dataclasses import dataclass
from typing import Literal

try:
    import tkinter as tk
    import tkinter.font as tkfont
except (ImportError, ModuleNotFoundError) as exc:
    raise SystemExit(
        "Missing tkinter runtime support. Install/use a Python build with Tk."
    ) from exc

try:
    from pylsl import StreamInfo, StreamOutlet, local_clock
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: pylsl. Install with `pip install -r requirements.txt`."
    ) from exc

State = Literal["focus", "relaxation"]
Line = tuple[str, tkfont.Font, str]

MAX_RUN_LENGTH = 5
MAX_SEQUENCE_ATTEMPTS = 5000
DEFAULT_WINDOW_SIZE = (1280, 720)

BG_COLOR = "#0A0E16"
TEXT_COLOR = "#F2F6FC"
ACCENT_COLOR = "#75D1FF"
SUBTEXT_COLOR = "#AEB8C6"

@dataclass(slots=True, frozen=True)
class Trial:
    state: State
    start_number: int | None = None
    subtractor: int | None = None


@dataclass(slots=True, frozen=True)
class Config:
    trials_per_state: int
    active_duration: float
    iti_min: float
    iti_max: float
    initial_fixation: float
    fullscreen: bool
    seed: int | None


class ExperimentAborted(Exception):
    """Raised when the participant aborts via Esc or closes the window."""


@dataclass(slots=True)
class TkUI:
    root: tk.Tk
    canvas: tk.Canvas
    heading_font: tkfont.Font
    body_font: tkfont.Font
    subtext_font: tkfont.Font
    abort_requested: bool = False
    abort_reason: str = "Aborted."


def parse_args(argv: list[str]) -> Config:
    parser = argparse.ArgumentParser(
        description="Run full-screen EEG state-labeling experiment with LSL markers."
    )
    parser.add_argument("--seed", type=int, default=None, help="Optional RNG seed.")
    parser.add_argument(
        "--fullscreen",
        dest="fullscreen",
        action="store_true",
        default=True,
        help="Run in fullscreen mode (default).",
    )
    parser.add_argument(
        "--windowed",
        dest="fullscreen",
        action="store_false",
        help="Run in windowed mode (for development).",
    )
    parser.add_argument(
        "--trials-per-state",
        type=int,
        default=50,
        help="Number of focus and relaxation trials (default: 50).",
    )
    parser.add_argument(
        "--active-duration",
        type=float,
        default=10.0,
        help="Duration in seconds for each active trial (default: 10.0).",
    )
    parser.add_argument(
        "--iti-min",
        type=float,
        default=4.0,
        help="Minimum ITI/fixation duration in seconds (default: 4.0).",
    )
    parser.add_argument(
        "--iti-max",
        type=float,
        default=4.0,
        help="Maximum ITI/fixation duration in seconds (default: 4.0).",
    )
    parser.add_argument(
        "--initial-fixation",
        type=float,
        default=4.0,
        help="Initial fixation duration in seconds (default: 4.0).",
    )

    args = parser.parse_args(argv)
    if args.trials_per_state <= 0:
        parser.error("--trials-per-state must be > 0.")
    if args.active_duration <= 0:
        parser.error("--active-duration must be > 0.")
    if args.initial_fixation <= 0:
        parser.error("--initial-fixation must be > 0.")
    if args.iti_min <= 0:
        parser.error("--iti-min must be > 0.")
    if args.iti_max <= 0:
        parser.error("--iti-max must be > 0.")
    if args.iti_max < args.iti_min:
        parser.error("--iti-max must be >= --iti-min.")

    return Config(
        trials_per_state=args.trials_per_state,
        active_duration=args.active_duration,
        iti_min=args.iti_min,
        iti_max=args.iti_max,
        initial_fixation=args.initial_fixation,
        fullscreen=args.fullscreen,
        seed=args.seed,
    )


def build_state_sequence(
    rng: random.Random,
    trials_per_state: int,
    max_run_length: int = MAX_RUN_LENGTH,
) -> list[State]:
    """Build balanced sequence with run-length limit."""
    total_trials = trials_per_state * 2

    for _ in range(MAX_SEQUENCE_ATTEMPTS):
        remaining: dict[State, int] = {
            "focus": trials_per_state,
            "relaxation": trials_per_state,
        }
        sequence: list[State] = []
        last_state: State | None = None
        streak = 0

        while len(sequence) < total_trials:
            weighted_candidates: list[State] = []
            for state in ("focus", "relaxation"):
                count = remaining[state]
                if count <= 0:
                    continue
                if state == last_state and streak >= max_run_length:
                    continue
                weighted_candidates.extend([state] * count)

            if not weighted_candidates:
                break

            next_state = rng.choice(weighted_candidates)
            sequence.append(next_state)
            remaining[next_state] -= 1
            if next_state == last_state:
                streak += 1
            else:
                last_state = next_state
                streak = 1

        if len(sequence) == total_trials:
            return sequence

    raise RuntimeError("Failed to generate a valid trial sequence with run-length limit.")


def sample_subtraction_prompts(rng: random.Random, count: int) -> list[tuple[int, int]]:
    """Generate (start_number, subtractor) prompts for focus trials."""
    prompts: list[tuple[int, int]] = []
    for _ in range(count):
        start_number = rng.randint(100, 999)
        subtractor = rng.randint(1, 99)
        prompts.append((start_number, subtractor))
    return prompts


def build_trials(rng: random.Random, trials_per_state: int) -> list[Trial]:
    sequence = build_state_sequence(rng, trials_per_state)
    subtraction_prompts = iter(sample_subtraction_prompts(rng, trials_per_state))
    trials: list[Trial] = []

    for state in sequence:
        if state == "focus":
            start_number, subtractor = next(subtraction_prompts)
            trials.append(
                Trial(state=state, start_number=start_number, subtractor=subtractor)
            )
        else:
            trials.append(Trial(state=state))

    return trials


def create_lsl_outlet() -> StreamOutlet:
    info = StreamInfo(
        name="EEGStateMarkers",
        type="Markers",
        channel_count=1,
        nominal_srate=0.0,
        channel_format="string",
        source_id=f"eeg_state_runner_{int(time.time())}",
    )
    return StreamOutlet(info)


def send_marker(outlet: StreamOutlet, marker: str) -> None:
    outlet.push_sample([marker], local_clock())
    print(f"[LSL] {marker}")


def create_tk_ui(fullscreen: bool) -> TkUI:
    root = tk.Tk()
    root.title("EEG State Labeling")
    root.configure(bg=BG_COLOR)
    if fullscreen:
        root.attributes("-fullscreen", True)
    else:
        root.geometry(f"{DEFAULT_WINDOW_SIZE[0]}x{DEFAULT_WINDOW_SIZE[1]}")

    canvas = tk.Canvas(root, bg=BG_COLOR, highlightthickness=0, bd=0)
    canvas.pack(fill=tk.BOTH, expand=True)
    root.update_idletasks()
    root.update()

    canvas_h = max(canvas.winfo_height(), 1)
    heading_size = max(64, canvas_h // 8)
    body_size = max(36, canvas_h // 18)
    subtext_size = max(28, canvas_h // 24)

    ui = TkUI(
        root=root,
        canvas=canvas,
        heading_font=tkfont.Font(root=root, family="TkDefaultFont", size=heading_size, weight="bold"),
        body_font=tkfont.Font(root=root, family="TkDefaultFont", size=body_size),
        subtext_font=tkfont.Font(root=root, family="TkDefaultFont", size=subtext_size),
    )

    def request_abort_escape(_event: tk.Event | None = None) -> None:
        ui.abort_requested = True
        ui.abort_reason = "Escape pressed."

    def request_abort_close() -> None:
        ui.abort_requested = True
        ui.abort_reason = "Window closed."

    root.bind("<Escape>", request_abort_escape)
    root.protocol("WM_DELETE_WINDOW", request_abort_close)
    return ui


def pump_events(ui: TkUI) -> None:
    try:
        ui.root.update_idletasks()
        ui.root.update()
    except tk.TclError as exc:
        raise ExperimentAborted("Window closed.") from exc

    if ui.abort_requested:
        raise ExperimentAborted(ui.abort_reason)


def wait_seconds(duration: float, ui: TkUI) -> None:
    deadline = time.monotonic() + duration
    while True:
        pump_events(ui)
        if time.monotonic() >= deadline:
            return
        time.sleep(0.01)


def draw_centered_lines(ui: TkUI, lines: list[Line]) -> None:
    canvas_w = max(ui.canvas.winfo_width(), 1)
    canvas_h = max(ui.canvas.winfo_height(), 1)

    ui.canvas.delete("all")
    ui.canvas.configure(bg=BG_COLOR)

    line_heights = [font.metrics("linespace") for _, font, _ in lines]
    spacing = max(12, canvas_h // 52)
    total_height = sum(line_heights) + spacing * max(0, len(lines) - 1)
    y = (canvas_h - total_height) // 2

    for (text, font, color), line_height in zip(lines, line_heights, strict=True):
        ui.canvas.create_text(
            canvas_w // 2,
            y + (line_height // 2),
            text=text,
            fill=color,
            font=font,
            justify=tk.CENTER,
        )
        y += line_height + spacing

    pump_events(ui)


def fixation_lines(
    heading_font: tkfont.Font, body_font: tkfont.Font
) -> list[Line]:
    return [
        ("+", heading_font, TEXT_COLOR),
        ("Blink / reset", body_font, SUBTEXT_COLOR),
    ]


def focus_lines(
    heading_font: tkfont.Font,
    body_font: tkfont.Font,
    start_number: int,
    subtractor: int,
) -> list[Line]:
    return [
        ("FOCUS", heading_font, ACCENT_COLOR),
        ("Repeat this subtraction in your mind.", body_font, TEXT_COLOR),
        (f"Start: {start_number}", heading_font, TEXT_COLOR),
        (f"Subtract: {subtractor}", body_font, SUBTEXT_COLOR),
    ]


def relaxation_lines(heading_font: tkfont.Font, body_font: tkfont.Font) -> list[Line]:
    return [
        ("RELAX", heading_font, ACCENT_COLOR),
        ("Relax. Breathe naturally.", body_font, TEXT_COLOR),
    ]


def run_experiment(config: Config) -> int:
    rng = random.Random(config.seed)
    trials = build_trials(rng, config.trials_per_state)
    outlet = create_lsl_outlet()
    print("[LSL] Outlet created: EEGStateMarkers")
    print(
        "[Session] Starting",
        f"focus={config.trials_per_state}",
        f"relaxation={config.trials_per_state}",
        f"seed={config.seed}",
    )

    ui = create_tk_ui(config.fullscreen)

    try:
        draw_centered_lines(ui, fixation_lines(ui.heading_font, ui.body_font))
        wait_seconds(config.initial_fixation, ui)

        for index, trial in enumerate(trials, start=1):
            pump_events(ui)

            if trial.state == "focus":
                start_number = trial.start_number if trial.start_number is not None else 500
                subtractor = trial.subtractor if trial.subtractor is not None else 7
                draw_centered_lines(
                    ui,
                    focus_lines(ui.heading_font, ui.body_font, start_number, subtractor),
                )
                send_marker(outlet, "focus_start")
                wait_seconds(config.active_duration, ui)
                send_marker(outlet, "focus_end")
            else:
                draw_centered_lines(ui, relaxation_lines(ui.heading_font, ui.body_font))
                send_marker(outlet, "relaxation_start")
                wait_seconds(config.active_duration, ui)
                send_marker(outlet, "relaxation_end")

            if index < len(trials):
                iti_duration = rng.uniform(config.iti_min, config.iti_max)
                draw_centered_lines(ui, fixation_lines(ui.heading_font, ui.body_font))
                wait_seconds(iti_duration, ui)

    except ExperimentAborted as exc:
        print(f"[Session] Aborted: {exc}")
        return 130
    finally:
        try:
            ui.root.destroy()
        except tk.TclError:
            pass

    print("[Session] Complete.")
    return 0


def main(argv: list[str] | None = None) -> int:
    config = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return run_experiment(config)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
