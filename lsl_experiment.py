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
    import pygame
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: pygame. Install with `pip install -r requirements.txt`."
    ) from exc

try:
    from pylsl import StreamInfo, StreamOutlet, local_clock
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing dependency: pylsl. Install with `pip install -r requirements.txt`."
    ) from exc

State = Literal["focus", "relaxation"]
Line = tuple[str, pygame.font.Font, tuple[int, int, int]]

MAX_RUN_LENGTH = 5
MAX_SEQUENCE_ATTEMPTS = 5000
DEFAULT_WINDOW_SIZE = (1280, 720)

BG_COLOR = (10, 14, 22)
TEXT_COLOR = (242, 246, 252)
ACCENT_COLOR = (117, 209, 255)
SUBTEXT_COLOR = (174, 184, 198)

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


def poll_abort_events() -> None:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            raise ExperimentAborted("Window closed.")
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            raise ExperimentAborted("Escape pressed.")


def wait_seconds(duration: float, clock: pygame.time.Clock) -> None:
    deadline = time.monotonic() + duration
    while True:
        poll_abort_events()
        if time.monotonic() >= deadline:
            return
        clock.tick(120)


def create_fonts(screen_height: int) -> tuple[pygame.font.Font, pygame.font.Font, pygame.font.Font]:
    heading_size = max(64, screen_height // 8)
    body_size = max(36, screen_height // 18)
    subtext_size = max(28, screen_height // 24)
    return (
        pygame.font.Font(None, heading_size),
        pygame.font.Font(None, body_size),
        pygame.font.Font(None, subtext_size),
    )


def draw_centered_lines(screen: pygame.Surface, lines: list[Line]) -> None:
    screen.fill(BG_COLOR)
    rendered = [font.render(text, True, color) for text, font, color in lines]
    spacing = max(12, screen.get_height() // 52)
    total_height = sum(surface.get_height() for surface in rendered)
    total_height += spacing * max(0, len(rendered) - 1)

    y = (screen.get_height() - total_height) // 2
    for surface in rendered:
        rect = surface.get_rect(center=(screen.get_width() // 2, y + surface.get_height() // 2))
        screen.blit(surface, rect)
        y += surface.get_height() + spacing

    pygame.display.flip()


def fixation_lines(
    heading_font: pygame.font.Font, body_font: pygame.font.Font
) -> list[Line]:
    return [
        ("+", heading_font, TEXT_COLOR),
        ("Blink / reset", body_font, SUBTEXT_COLOR),
    ]


def focus_lines(
    heading_font: pygame.font.Font,
    body_font: pygame.font.Font,
    start_number: int,
    subtractor: int,
) -> list[Line]:
    return [
        ("FOCUS", heading_font, ACCENT_COLOR),
        ("Repeat this subtraction in your mind.", body_font, TEXT_COLOR),
        (f"Start: {start_number}", heading_font, TEXT_COLOR),
        (f"Subtract: {subtractor}", body_font, SUBTEXT_COLOR),
    ]


def relaxation_lines(heading_font: pygame.font.Font, body_font: pygame.font.Font) -> list[Line]:
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

    pygame.init()
    pygame.display.set_caption("EEG State Labeling")
    flags = pygame.FULLSCREEN if config.fullscreen else 0
    size = (0, 0) if config.fullscreen else DEFAULT_WINDOW_SIZE
    screen = pygame.display.set_mode(size, flags)
    heading_font, body_font, _ = create_fonts(screen.get_height())
    clock = pygame.time.Clock()

    try:
        draw_centered_lines(screen, fixation_lines(heading_font, body_font))
        wait_seconds(config.initial_fixation, clock)

        for index, trial in enumerate(trials, start=1):
            poll_abort_events()

            if trial.state == "focus":
                start_number = trial.start_number if trial.start_number is not None else 500
                subtractor = trial.subtractor if trial.subtractor is not None else 7
                draw_centered_lines(
                    screen,
                    focus_lines(heading_font, body_font, start_number, subtractor),
                )
                send_marker(outlet, "focus_start")
                wait_seconds(config.active_duration, clock)
                send_marker(outlet, "focus_end")
            else:
                draw_centered_lines(screen, relaxation_lines(heading_font, body_font))
                send_marker(outlet, "relaxation_start")
                wait_seconds(config.active_duration, clock)
                send_marker(outlet, "relaxation_end")

            if index < len(trials):
                iti_duration = rng.uniform(config.iti_min, config.iti_max)
                draw_centered_lines(screen, fixation_lines(heading_font, body_font))
                wait_seconds(iti_duration, clock)

    except ExperimentAborted as exc:
        print(f"[Session] Aborted: {exc}")
        return 130
    finally:
        pygame.quit()

    print("[Session] Complete.")
    return 0


def main(argv: list[str] | None = None) -> int:
    config = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return run_experiment(config)
    except (RuntimeError, pygame.error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
