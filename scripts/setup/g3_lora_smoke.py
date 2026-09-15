#!/usr/bin/env python3
"""Throwaway PEFT LoRA smoke on granite-4.2-8b. GPU job only. <=10 minutes."""
from __future__ import annotations

import json
import os
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("HF_HOME", "/scratch/n12194778/hf")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

SCRATCH = Path(os.environ.get("SIDEKICK_SCRATCH", "/scratch/n12194778/sidekick"))
OUT_DIR = Path(
    os.environ.get(
        "SIDEKICK_LORA_OUT",
        "/scratch/n12194778/sidekick/artifacts/adapters/smoke_lora",
    )
)
LOGDIR = SCRATCH / "logs"
MODEL = os.environ.get("SIDEKICK_LORA_MODEL", "ibm-granite/granite-4.2-8b")
MAX_TRAIN_S = float(os.environ.get("SIDEKICK_LORA_MAX_S", "600"))


def gpu_mem() -> dict:
    rec = {}
    try:
        import torch

        if torch.cuda.is_available():
            rec["torch_allocated_bytes"] = int(torch.cuda.memory_allocated())
            rec["torch_reserved_bytes"] = int(torch.cuda.memory_reserved())
            rec["torch_max_allocated_bytes"] = int(torch.cuda.max_memory_allocated())
            rec["device"] = torch.cuda.get_device_name(0)
    except Exception as e:  # noqa: BLE001
        rec["torch_error"] = repr(e)
    try:
        import subprocess

        p = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        rec["nvidia_smi"] = p.stdout.strip()
        rec["nvidia_smi_err"] = p.stderr.strip()[-500:]
    except Exception as e:  # noqa: BLE001
        rec["nvidia_smi_error"] = repr(e)
    return rec


def main() -> int:
    LOGDIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {
        "when": datetime.now(timezone.utc).isoformat(),
        "host": os.uname().nodename,
        "job": os.environ.get("PBS_JOBID"),
        "model": MODEL,
        "out": str(OUT_DIR),
        "failures": [],
        "gpu_before": gpu_mem(),
    }
    t_all = time.perf_counter()
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments
        from transformers import DataCollatorForLanguageModeling

        report["torch"] = {
            "version": torch.__version__,
            "cuda": torch.version.cuda,
            "cuda_available": torch.cuda.is_available(),
        }
        tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        texts = [
            f"<|im_start|>user\nSay the number {i} twice.<|im_end|>\n<|im_start|>assistant\n{i} {i}<|im_end|>\n"
            for i in range(50)
        ]
        ds = Dataset.from_dict({"text": texts})

        def tokenize(batch):
            out = tok(
                batch["text"],
                truncation=True,
                max_length=128,
                padding="max_length",
            )
            out["labels"] = [ids[:] for ids in out["input_ids"]]
            return out

        tds = ds.map(tokenize, batched=True, remove_columns=["text"])
        tds.set_format(type="torch")

        t_load = time.perf_counter()
        model = AutoModelForCausalLM.from_pretrained(
            MODEL,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )
        report["model_load_s"] = time.perf_counter() - t_load
        report["gpu_after_load"] = gpu_mem()

        lora = LoraConfig(
            r=64,
            lora_alpha=128,
            lora_dropout=0.0,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
            target_modules=[
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            ],
        )
        model = get_peft_model(model, lora)
        model.print_trainable_parameters()
        args = TrainingArguments(
            output_dir=str(SCRATCH / "artifacts" / "adapters" / "smoke_lora_work"),
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            num_train_epochs=1,
            max_steps=20,
            learning_rate=2e-4,
            logging_steps=1,
            save_strategy="no",
            report_to=[],
            bf16=True,
            fp16=False,
            remove_unused_columns=False,
            dataloader_num_workers=0,
            max_grad_norm=1.0,
        )
        collator = DataCollatorForLanguageModeling(tok, mlm=False)
        trainer = Trainer(
            model=model,
            args=args,
            train_dataset=tds,
            data_collator=collator,
        )
        t_tr = time.perf_counter()
        # Hard cap: stop if we somehow over-run.
        if t_tr - t_all > MAX_TRAIN_S:
            raise RuntimeError("load already exceeded max train window")
        train_out = trainer.train()
        report["train_s"] = time.perf_counter() - t_tr
        report["train_metrics"] = dict(train_out.metrics)
        report["gpu_after_train"] = gpu_mem()
        model.save_pretrained(str(OUT_DIR))
        tok.save_pretrained(str(OUT_DIR))
        report["saved_files"] = sorted(p.name for p in OUT_DIR.iterdir())
        report["ok"] = True
    except Exception:
        report["ok"] = False
        report["failures"].append(traceback.format_exc()[-8000:])
        print(report["failures"][-1], file=__import__("sys").stderr)
    report["wall_s"] = time.perf_counter() - t_all
    report["gpu_end"] = gpu_mem()
    path = LOGDIR / "g3_lora_smoke.json"
    path.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str)[:8000])
    print(f"[g3_lora] wrote {path} ok={report.get('ok')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
