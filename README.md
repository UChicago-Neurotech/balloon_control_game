# EEG State Labeling Runner

Participant-facing experiment runner for EEG labeling using standard-library `tkinter` (stimulus display) and `pylsl` (marker stream).

## Requirements
- Python `3.12.8`
- Python build with Tk support (`tkinter`)
- Desktop environment with display access

## Install
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```bash
python3.12 lsl_experiment.py
```

Windowed dev mode:
```bash
python3.12 lsl_experiment.py --windowed
```

## CLI options
- `--seed <int>`
- `--trials-per-state <int>` (default `50`)
- `--active-duration <float>` (default `10.0`)
- `--iti-min <float>` (default `4.0`)
- `--iti-max <float>` (default `4.0`)
- `--initial-fixation <float>` (default `4.0`)
- `--fullscreen` (default behavior)
- `--windowed`

## Controls
- `Esc`: abort immediately and exit.

## LSL markers
- `focus_start`
- `focus_end`
- `relaxation_start`
- `relaxation_end`
