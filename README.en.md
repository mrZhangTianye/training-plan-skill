# training-plan-skill

[中文](README.md)

An independently usable Skill for planning, expanding and revising general training programs of up to 12 weeks. It combines functional strength, running and swimming, with ball sports treated as scheduling and recovery constraints.

Version 1.0 includes planning rules, a structured plan format, a training library, validators and Markdown renderers. Playwise is the separate local web interface that bundles a pinned copy. Its new swimming model workflow is still undergoing release verification.

## What it does

- Builds an explicit plan from goals, training background, availability, equipment and relevant limitations.
- Keeps dose, effort, rest, progression, dates and task requirements in structured JSON.
- Plans normal progression in advance. Missing optional feedback is not a weekly permission gate; reported problems adjust future work while preserving completed history.
- Checks schema, asset IDs, declared timing, group order, prerequisites and consistency.
- Separates deterministic validation from design review and real-world suitability. A passing check does not certify health, safety or training effects.

The library contains 336 catalog entries and 362 runtime interfaces. These are different counts, not 362 independently reviewed exercises.

## Use with an assistant

Place this directory in your assistant's supported Skill location and use `SKILL.md` as the entry point. Keep the relative `references`, `schemas`, `scripts`, `assets` and `tests` directories intact. The host assistant supplies the language-model connection; this Skill does not contain API credentials or a background network client.

No private knowledge base, personal account, Notion workspace or original book files are required to run the bundled tools. Bibliographic references identify sources; they do not supply or license those books.

## Command-line tools

Python 3.9+ is recommended. Runtime tools use the standard library. Tests additionally require pytest.

```sh
git clone https://github.com/mrZhangTianye/training-plan-skill.git
cd training-plan-skill
python3 scripts/validate_library.py
python3 scripts/validate_plan.py assets/examples/plan.json
python3 scripts/render_plan.py assets/examples/plan.json --view overall --output overview.md
python3 scripts/render_plan.py assets/examples/plan.json --view week --week 1 --output week-1.md
```

For a plan that is not ready for execution, rendering requires `--draft` and labels the output as a draft. Example plans are fictional test fixtures, not recommendations for a real person.

Additional tools include `render_weekly_log.py`, `export_plan.py`, `compare_plans.py` and `select_assets.py`. Run a tool with `--help` for its interface.

## Swimming in 1.0

Swimming rules now use one consistent progression and dose contract. The new breaststroke content is based on selected drills from Ruben J. Guzman's *The Swimming Drill Book*, Human Kinetics, 2007, not the later second edition.

- Six technique tasks can be scheduled when their exact prerequisites are confirmed.
- Two entries remain reference-only; they cannot be prescribed as 25/50 m tasks merely to fit a pool length.
- Continuous capacity is recorded for the specific task. Whole-stroke ability or another stroke does not automatically unlock it.
- Stationary practice uses time, not invented swimming distance or aerobic credit.
- A session has one technique focus. Optional completion, difficulty and focus feedback can inform later adjustments.

This is not a complete breaststroke endurance, speed, competition or rehabilitation library. Product doses, equipment checks and safety rules are implementation choices, not universal prescriptions copied from the book. See [the swimming contract](references/swim-technique-contract.md) and [source index](references/swim-technique-evidence.json).

## Data model and validation

`schemas/plan.schema.json` defines the plan; `change-set.schema.json` defines changes. `swim-feedback.schema.json` defines independent swimming feedback. Keep user facts, mastery, restrictions, equipment and uncertainty truthful. Do not promote unknown facts to independent mastery or change a review result just to make a plan pass.

The main plan separates objectives, stages, weeks and sessions. Work items retain sets, repetitions, time, distance, effort and rest. Pair/triple groups use explicit order. The validator checks declared facts and internal consistency; human or qualified professional review is still needed where the plan requires it.

## Verification

The 1.0 source passed 211 tests, library validation, exercise-name checks and documentation link checks. The public copy removes personal narrative and private customization while preserving runtime code, schemas, numerical assets and fictional fixtures.

```sh
python3 -m pip install 'pytest>=8,<9'
python3 -m pytest tests
python3 scripts/validate_library.py
python3 scripts/check_links.py
python3 scripts/check_exercise_names.py
```

## Scope and license

Intended for general health and broad physical ability, not clinical diagnosis, rehabilitation prescriptions, competition peaking or emergency decisions. Generated plans need to match the individual's actual conditions. Stop an activity if symptoms or safety conditions change and seek suitable professional advice when needed.

Original code, interfaces and documentation are licensed under [MIT](LICENSE). Cited books, papers, images and third-party trademarks are not licensed by this repository. See [third-party notices](THIRD_PARTY_NOTICES.md).
