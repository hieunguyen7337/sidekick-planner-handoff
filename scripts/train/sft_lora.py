#!/usr/bin/env python3
"""LoRA SFT on granite-4.2-8b with manual assistant-token masking.

Installed APIs this script was written against (scratch venv):
  trl 1.13.0, peft 0.20.0, transformers 5.17.0, torch 2.13.0, vllm 0.29.0
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path
from typing import Any

# Login-node / job hygiene: never let BLAS oversubscribe a shared node.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("HF_HOME", "/scratch/n12194778/hf")

from sidekick.training.sft_data import tokenize_sft_row

DEFAULT_BASE_MODEL = "ibm-granite/granite-4.2-8b"
DEFAULT_TARGETS = [
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
]
MAX_LENGTH = 32768
EFFECTIVE_BATCH = 8


def _pkg(name: str) -> str:
    try:
        return pkg_version(name)
    except PackageNotFoundError:
        return "unknown"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            obj = json.loads(stripped)
            if not isinstance(obj, dict) or "messages" not in obj:
                raise ValueError(f"JSONL line is not an SFT record with 'messages': {stripped[:120]}")
            rows.append(obj)
    if not rows:
        raise ValueError(f"no SFT records in {path}")
    return rows


def _row_run_id(row: dict[str, Any]) -> str | None:
    meta = row.get("meta")
    if not isinstance(meta, dict):
        return None
    rid = meta.get("run_id")
    if isinstance(rid, str) and rid:
        return rid
    return None


def _has_supervised_labels(example: dict[str, Any]) -> bool:
    labels = example.get("labels") or []
    return any(lab != -100 for lab in labels)


def _drop_reason(
    row: dict[str, Any],
    example: dict[str, Any],
    tokenizer: Any,
    max_length: int | None,
) -> str:
    """Classify a fully-masked row without changing the kept example.

    A second tokenisation with ``max_length=None`` is used only on the drop
    path so "never had labels" can be separated from "truncation removed them".
    """
    if not example.get("truncated") or max_length is None:
        return "fully_masked_before_truncation"
    untrunc = tokenize_sft_row(row, tokenizer, max_length=None)
    if _has_supervised_labels(untrunc):
        return "truncated_past_labels"
    return "fully_masked_before_truncation"


def _emit_drop_warning(stats: dict[str, Any], *, n_sequences: int) -> None:
    n_drop = int(stats["n_dropped_no_supervised_tokens"])
    n_trunc_kept = int(stats["n_truncated_kept"])
    n_in = int(stats["n_rows_in"])
    if n_drop:
        ids = stats.get("dropped_run_ids") or []
        id_note = f" dropped_run_ids={ids}" if ids else ""
        print(
            f"WARNING: dropped {n_drop}/{n_in} SFT rows with no supervised tokens "
            f"(truncated_past_labels={stats['n_dropped_truncated_past_labels']}, "
            f"fully_masked_before_truncation="
            f"{stats['n_dropped_fully_masked_before_truncation']}). "
            f"n_sequences={n_sequences} (rows trained on). "
            f"n_truncated_kept={n_trunc_kept}.{id_note}",
            file=sys.stderr,
        )
    elif n_trunc_kept:
        print(
            f"WARNING: kept {n_trunc_kept}/{n_in} SFT rows that were truncated "
            f"but still had supervised tokens. n_sequences={n_sequences}.",
            file=sys.stderr,
        )


def collect_tokenized_sft_rows(
    rows: list[dict[str, Any]],
    tokenizer: Any,
    *,
    max_length: int | None = MAX_LENGTH,
    retain_examples: bool = True,
    progress_every: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Tokenise rows; skip fully-masked examples; record what was dropped.

    Drop behaviour matches the previous silent ``continue``: a row with no
    supervised tokens is not trained on. This function only counts, classifies,
    and warns. ``retain_examples=False`` still counts kept rows but does not
    hold the token arrays (for tokenizer-only audits).
    """
    tokenized: list[dict[str, Any]] = []
    dropped_run_ids: list[str] = []
    dropped_truncated_past_labels_run_ids: list[str] = []
    dropped_fully_masked_before_truncation_run_ids: list[str] = []
    truncated_kept_run_ids: list[str] = []
    n_kept = 0
    n_dropped = 0
    n_dropped_truncated_past_labels = 0
    n_dropped_fully_masked_before_truncation = 0
    n_truncated_kept = 0
    n_dropped_missing_run_id = 0

    for i, row in enumerate(rows, start=1):
        example = tokenize_sft_row(row, tokenizer, max_length=max_length)
        run_id = _row_run_id(row)
        if not _has_supervised_labels(example):
            n_dropped += 1
            reason = _drop_reason(row, example, tokenizer, max_length)
            if run_id is None:
                n_dropped_missing_run_id += 1
            else:
                dropped_run_ids.append(run_id)
            if reason == "truncated_past_labels":
                n_dropped_truncated_past_labels += 1
                if run_id is not None:
                    dropped_truncated_past_labels_run_ids.append(run_id)
            else:
                n_dropped_fully_masked_before_truncation += 1
                if run_id is not None:
                    dropped_fully_masked_before_truncation_run_ids.append(run_id)
        else:
            n_kept += 1
            if example.get("truncated"):
                n_truncated_kept += 1
                if run_id is not None:
                    truncated_kept_run_ids.append(run_id)
            if retain_examples:
                tokenized.append(example)
        if progress_every and i % progress_every == 0:
            print(
                f"tokenised {i}/{len(rows)} kept={n_kept} dropped={n_dropped} "
                f"truncated_kept={n_truncated_kept}",
                file=sys.stderr,
                flush=True,
            )

    stats = {
        "n_rows_in": len(rows),
        "n_dropped_no_supervised_tokens": n_dropped,
        "n_dropped_truncated_past_labels": n_dropped_truncated_past_labels,
        "n_dropped_fully_masked_before_truncation": n_dropped_fully_masked_before_truncation,
        "n_dropped_missing_run_id": n_dropped_missing_run_id,
        "n_truncated_kept": n_truncated_kept,
        "dropped_run_ids": dropped_run_ids,
        "dropped_truncated_past_labels_run_ids": dropped_truncated_past_labels_run_ids,
        "dropped_fully_masked_before_truncation_run_ids": dropped_fully_masked_before_truncation_run_ids,
        "truncated_kept_run_ids": truncated_kept_run_ids,
    }
    _emit_drop_warning(stats, n_sequences=n_kept)
    return tokenized, stats


class JsonlLossCallback:
    """Write per-step loss to train_log.jsonl. Constructed after transformers import."""

    def __init__(self, path: Path, inner_cls: type) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8")
        self._inner_cls = inner_cls

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def make(self):
        callback_cls = self._inner_cls
        outer = self

        class _Cb(callback_cls):  # type: ignore[misc, valid-type]
            def on_log(self, args, state, control, logs=None, **kwargs):
                if not logs:
                    return
                rec = {"step": int(state.global_step)}
                for key, val in logs.items():
                    if isinstance(val, (int, float, str, bool)) or val is None:
                        rec[key] = val
                    else:
                        rec[key] = str(val)
                outer._fh.write(json.dumps(rec) + "\n")
                outer._fh.flush()

        return _Cb()


def train(
    *,
    data: Path,
    out: Path,
    base_model: str,
    epochs: float,
    lr: float,
    rank: int,
    dry_run: bool,
    seed: int,
) -> dict[str, Any]:
    import torch
    from datasets import Dataset
    from peft import LoraConfig, TaskType
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainerCallback
    from trl import SFTConfig, SFTTrainer

    rows = _load_rows(data)
    if dry_run:
        rows = rows[:20]
        if len(rows) < 1:
            raise ValueError("dry-run needs at least one sequence")

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    tokenized, drop_stats = collect_tokenized_sft_rows(
        rows, tokenizer, max_length=MAX_LENGTH
    )
    if not tokenized:
        raise ValueError("every example was fully masked or empty after tokenisation")

    ds = Dataset.from_list(tokenized)
    out.mkdir(parents=True, exist_ok=True)

    lora = LoraConfig(
        r=int(rank),
        lora_alpha=128,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=list(DEFAULT_TARGETS),
    )

    # transformers 5.17.0 dropped warmup_ratio; warmup_steps in [0, 1) is a ratio.
    per_device = 1
    grad_accum = 1 if dry_run else EFFECTIVE_BATCH
    sft_args = SFTConfig(
        output_dir=str(out / "trainer_state"),
        num_train_epochs=1 if dry_run else float(epochs),
        max_steps=20 if dry_run else -1,
        per_device_train_batch_size=per_device,
        gradient_accumulation_steps=grad_accum,
        learning_rate=float(lr),
        lr_scheduler_type="cosine",
        warmup_steps=0.03,
        logging_steps=1,
        save_strategy="no",
        bf16=True,
        fp16=False,
        gradient_checkpointing=True,
        packing=False,
        max_length=MAX_LENGTH,
        dataset_kwargs={"skip_prepare_dataset": True},
        remove_unused_columns=False,
        report_to=[],
        seed=int(seed),
        dataloader_num_workers=0,
        # assistant_only_loss relies on {% generation %} markers; we mask by hand.
        assistant_only_loss=False,
    )

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.bfloat16,
        trust_remote_code=True,
    )
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    if getattr(model.config, "use_cache", None):
        model.config.use_cache = False

    loss_log = out / "train_log.jsonl"
    if loss_log.exists():
        loss_log.unlink()
    cb_factory = JsonlLossCallback(loss_log, TrainerCallback)
    callback = cb_factory.make()
    try:
        trainer = SFTTrainer(
            model=model,
            args=sft_args,
            train_dataset=ds,
            processing_class=tokenizer,
            peft_config=lora,
            callbacks=[callback],
        )
        train_out = trainer.train()
        trainer.save_model(str(out))
        tokenizer.save_pretrained(str(out))
        metrics = dict(train_out.metrics) if train_out is not None else {}
    finally:
        cb_factory.close()

    train_ids: list[str] = []
    for row in rows:
        meta = row.get("meta") or {}
        tid = meta.get("task_id")
        if isinstance(tid, str):
            train_ids.append(tid)

    manifest = {
        "base_model": base_model,
        "data": str(data),
        "data_sha256": _sha256(data),
        "out": str(out),
        "dry_run": dry_run,
        "seed": int(seed),
        "commit": os.environ.get("SIDEKICK_START_COMMIT", "").strip() or None,
        "hyperparameters": {
            "r": int(rank),
            "lora_alpha": 128,
            "lora_dropout": 0.05,
            "target_modules": list(DEFAULT_TARGETS),
            "lr": float(lr),
            "lr_scheduler_type": "cosine",
            "warmup_steps": 0.03,
            "warmup_steps_note": (
                "transformers 5.17.0 has no warmup_ratio; a float in [0, 1) on "
                "warmup_steps is the ratio of total steps"
            ),
            "epochs": 1 if dry_run else float(epochs),
            "max_steps": 20 if dry_run else None,
            "bf16": True,
            "gradient_checkpointing": True,
            "per_device_train_batch_size": per_device,
            "gradient_accumulation_steps": grad_accum,
            "effective_batch": per_device * grad_accum,
            "max_length": MAX_LENGTH,
            "masking": "manual_assistant_token_spans",
            "assistant_only_loss": False,
        },
        "train_task_ids": sorted(set(train_ids)),
        "n_sequences": len(tokenized),
        **drop_stats,
        "metrics": {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in metrics.items()},
        "package_versions": {
            "trl": _pkg("trl"),
            "peft": _pkg("peft"),
            "transformers": _pkg("transformers"),
            "torch": _pkg("torch"),
            "vllm": _pkg("vllm"),
            "datasets": _pkg("datasets"),
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "adapter": str(out),
                "dry_run": dry_run,
                "n_sequences": len(tokenized),
                "n_rows_in": drop_stats["n_rows_in"],
                "n_dropped_no_supervised_tokens": drop_stats["n_dropped_no_supervised_tokens"],
                "n_truncated_kept": drop_stats["n_truncated_kept"],
            },
            indent=2,
        )
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LoRA SFT with manual assistant-token masking.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--epochs", type=float, default=2)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--rank", type=int, default=64)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    train(
        data=Path(args.data),
        out=Path(args.out),
        base_model=args.base_model,
        epochs=args.epochs,
        lr=args.lr,
        rank=args.rank,
        dry_run=args.dry_run,
        seed=args.seed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
