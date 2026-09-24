# Vendored BFCL subset (multi_turn_base only)

Source: https://github.com/ShishirPatil/gorilla, directory `berkeley-function-call-leaderboard/bfcl_eval/`,
commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8` (2026-03-23), cloned with `git clone --depth 1` on
2026-09-24. License: Apache-2.0, copied unmodified to `LICENSE` from the repository root.

Every file below is a byte-for-byte copy of the upstream file at the same path under `bfcl_eval/`.
Nothing was edited. `sha256sum` of each file is in `SHA256SUMS`.

| path under `bfcl_eval/` | why it is here |
|---|---|
| `__init__.py`, `constants/__init__.py`, `eval_checker/__init__.py`, `eval_checker/multi_turn_eval/__init__.py`, `eval_checker/multi_turn_eval/func_source_code/__init__.py` | empty package markers, so the upstream absolute imports resolve |
| `constants/executable_backend_config.py` | `CLASS_FILE_PATH_MAPPING`, `STATELESS_CLASSES`, `MULTI_TURN_FUNC_DOC_FILE_MAPPING` |
| `eval_checker/multi_turn_eval/multi_turn_checker.py` | upstream scoring: `state_checker`, `response_checker`, `multi_turn_checker` |
| `eval_checker/multi_turn_eval/multi_turn_utils.py` | upstream executor, imported by the checker; used only in the spike (a) cross-check |
| `eval_checker/multi_turn_eval/func_source_code/{gorilla_file_system,math_api,message_api,posting_api,ticket_api,trading_bot,travel_booking,vehicle_control}.py` | the eight backend classes that `multi_turn_base` involves |
| `eval_checker/multi_turn_eval/func_source_code/long_context.py` | constants imported by four of the backends |
| `data/BFCL_v4_multi_turn_base.json` | the 200 entries (questions, `initial_config`, `involved_classes`) |
| `data/possible_answer/BFCL_v4_multi_turn_base.json` | their ground-truth call lists, one list per turn |
| `data/multi_turn_func_doc/*.json` (eight files) | the function schemas shown to the model, one file per backend class |

Third-party import: `math_api.py` imports `mpmath`; the shared env has mpmath 1.3.0. Nothing else
outside the standard library is imported by the vendored code.

Not vendored: the other test categories, the model handlers, `utils.py`, the memory and web-search
backends. Upstream at this commit does not read the entries' `excluded_function` field anywhere in
its Python code (`grep -rn excluded_function` hits only the data files), so the adapter does not
apply it either: the model sees every function of every involved class, as upstream's
`populate_test_cases_with_predefined_functions` builds it.

The adapter (`src/sidekick/environments/bfcl_env.py`) puts this directory on `sys.path` and never
calls upstream's `execute_multi_turn_func_call` during an episode: that function caches instances in
module `globals()` keyed by model name and entry id, so a second episode of the same entry in one
process would start from the first one's mutated state.
