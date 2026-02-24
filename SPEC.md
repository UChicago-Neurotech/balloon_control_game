# EEG State-Labeling Experiment Runner Specification

## 1. Purpose
Build a Python experiment runner for EEG labeling that:
- presents full-screen participant prompts,
- controls fixed-duration mental-state trials,
- sends LSL markers for labeled state boundaries only.

This module is for participant-facing execution only. No experimenter UI or live operator interaction is required.

## 2. Scope
### In scope
- Run one session with:
  - an initial fixation period,
  - randomized active trials for two classes (`focus`, `relaxation`),
  - fixation/blink separators between active trials.
- Send LSL event markers for `focus` and `relaxation` trial boundaries.
- Full-screen visual presentation for participant instructions.
- Emergency abort key (`Esc`).

### Out of scope
- EEG signal acquisition/storage.
- Any data logging beyond LSL marker output.
- Experimenter control panel.
- PsychoPy dependency.

## 3. Runtime and Dependencies
- Python version: `3.12.8`.
- Presentation library: `pygame` (PsychoPy explicitly avoided).
- LSL library: `pylsl`.
- Target platform: desktop environment capable of full-screen window rendering.

## 4. State Model
Discrete conceptual states:
- `fixation` (visual separator/rest state, unlabeled in LSL),
- `focus` (labeled),
- `relaxation` (labeled).

LSL markers are emitted only for `focus` and `relaxation`.

## 5. Session Timeline
1. Start session in full-screen.
2. Initial fixation: `4.0s`.
3. Run `100` active trials total:
   - `50` `focus` trials,
   - `50` `relaxation` trials.
4. Active trial duration: `10.0s` each.
5. Between active trials, show fixation/blink separator for `4.0s`.
6. No final fixation block after the last active trial.
7. Session ends immediately after last active trial.

Separator count is `99` (between 100 active trials only).

## 6. Randomization Rules
- Build a balanced active-trial schedule with exactly 50 `focus` and 50 `relaxation`.
- Shuffle schedule with constraint:
  - no more than 5 active trials of the same class consecutively.
- If sequence generation attempt violates constraints, regenerate until valid.
- Optional reproducibility:
  - allow an optional random seed argument.

## 7. Participant Stimuli
### Focus trial (`focus`)
Display instruction for internal cognitive task:
- "Repeatedly subtract this number in your mind."
- Show:
  - one random 3-digit start number (`100-999`),
  - one random 1-2 digit subtractor (`1-99`).

Prompt handling requirements:
- Generate one subtraction prompt per focus trial.
- Participant continues repeated subtraction from the shown start number for the full trial duration.

### Relaxation trial (`relaxation`)
Display calm instruction:
- "Relax. Breathe naturally."

### Fixation/blink separator (`fixation`)
Display central fixation cross and brief reset instruction, e.g.:
- "+"
- "Blink / reset"

## 8. LSL Interface Contract
Create one LSL outlet for marker events (string markers, irregular rate).

Required marker vocabulary:
- `focus_start`
- `focus_end`
- `relaxation_start`
- `relaxation_end`

Emission rules:
- At onset of each `focus` trial: emit `focus_start`.
- At end of each `focus` trial: emit `focus_end`.
- At onset of each `relaxation` trial: emit `relaxation_start`.
- At end of each `relaxation` trial: emit `relaxation_end`.
- Do not emit markers for fixation periods.

## 9. Controls and UX Behavior
- No runtime prompts required for an experimenter.
- Session starts automatically when script is launched.
- `Esc` must abort immediately and close cleanly.
- Recommended optional CLI args:
  - `--seed` (int),
  - `--fullscreen` (default true),
  - `--trials-per-state` (default 50, for dev/testing),
  - `--active-duration` (default 10.0),
  - `--iti-min` (default 4.0),
  - `--iti-max` (default 4.0),
  - `--initial-fixation` (default 4.0).

## 10. Timing Requirements
- Trial durations should target wall-clock accuracy suitable for EEG event labeling.
- Use monotonic timing APIs.
- Marker send call should occur as close as possible to visual state boundary.
- Expected practical tolerance target: within approximately +/-50 ms of scheduled boundary on a typical desktop.

## 11. Acceptance Criteria (v1)
The implementation is accepted when all are true:
1. Starts full-screen and runs with no experimenter interaction.
2. Performs exactly one initial 4s fixation block.
3. Executes exactly 100 active trials with 50/50 class balance.
4. Never exceeds run-length of 5 same-class active trials.
5. Uses 10.0s active trial duration and 4.0s fixation separators.
6. Emits only the four approved marker strings.
7. Emits start/end markers for every active trial, none for fixation.
8. Ends cleanly after final active trial with no final fixation.
9. `Esc` abort works at any point.

## 12. Future Extensions (Non-v1)
- Optional marker/log export for offline QA.
- Optional participant/session identifiers in marker payload metadata.
- Configurable task instructions and multilingual prompt sets.
