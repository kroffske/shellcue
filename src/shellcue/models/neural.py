"""Lazy local Transformers decoding for ShellCue artifacts."""

from __future__ import annotations

import logging
import os
from dataclasses import replace
from typing import Any

from shellcue.models.artifact import (
    DecodeBudget,
    InferenceConfig,
    LoadedArtifact,
    Suggestion,
    SuggestionRequest,
)
from shellcue.models.candidates import GeneratedCandidate, safe_suggestions
from shellcue.models.prompt_contract import PromptContractError, PromptInput, render_prompt

DTYPE_ENV = "SHELLCUE_NEURAL_DTYPE"
logger = logging.getLogger(__name__)


class NeuralPredictor:
    """Own one loaded local causal language model and its tokenizer."""

    def __init__(self, model: Any, tokenizer: Any, config: InferenceConfig, device: Any) -> None:
        self._model = model
        self._tokenizer = tokenizer
        self._config = config
        self._device = device
        self._newline_id = _newline_stop_id(tokenizer, config.newline_stop_id)

    @classmethod
    def from_artifact(cls, artifact: LoadedArtifact) -> NeuralPredictor:
        try:
            import torch
            import transformers
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "required neural dependencies are unavailable; reinstall shellcue"
            ) from exc
        transformers.utils.logging.set_verbosity_error()
        transformers.utils.logging.disable_progress_bar()
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                str(artifact.model_dir), use_fast=True, local_files_only=True
            )
            model = AutoModelForCausalLM.from_pretrained(
                str(artifact.model_dir),
                dtype=_resolve_dtype(torch),
                local_files_only=True,
            )
        except Exception as exc:
            raise RuntimeError(f"failed to load local neural model: {exc}") from exc
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        device = _place_model(model, torch, _resolve_device(torch))
        model.eval()
        return cls(model, tokenizer, artifact.inference, device)

    def suggest(
        self,
        request: SuggestionRequest,
        *,
        limit: int = 5,
        budget: DecodeBudget | None = None,
    ) -> tuple[Suggestion, ...]:
        config = _apply_budget(self._config, budget)
        try:
            prompt_ids, fragment = self._prompt(request, config)
        except PromptContractError:
            # The contract forbids invoking an alternative predictor when the
            # mandatory fields do not fit, so abstain rather than serve a
            # different prompt shape.
            return ()
        generated = self._generate(prompt_ids, config)
        suggestions = safe_suggestions(
            request.typed_prefix,
            generated,
            typed_fragment=fragment,
            limit=max(limit, len(generated)),
        )
        if suggestions or config.empty_heal_fallback != "no_heal_parse_valid":
            return suggestions[:limit]
        fallback = replace(config, beams=1, token_healing=False, healing=False)
        if fallback.beams == config.beams:
            # Healing no longer changes the rendered prompt, so once beams match
            # the retry would re-render identical bytes and repeat a
            # deterministic greedy decode. Abstain instead of paying 2x latency
            # for a provably identical result.
            return suggestions[:limit]
        prompt_ids, _ = self._prompt(request, fallback)
        fallback_generated = self._generate(prompt_ids, fallback)
        return safe_suggestions(
            request.typed_prefix,
            fallback_generated,
            limit=max(limit, len(fallback_generated)),
        )[:limit]

    def release_caches(self) -> None:
        try:
            import torch

            if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
                torch.mps.empty_cache()
            elif torch.cuda.is_available():
                torch.cuda.empty_cache()
        except (ImportError, RuntimeError):
            return

    def _encode(self, text: str) -> list[int]:
        return self._tokenizer(text, add_special_tokens=False)["input_ids"]

    def _prompt(self, request: SuggestionRequest, config: InferenceConfig) -> tuple[list[int], str]:
        """Render the v2 prompt contract; this is the runtime's only serializer.

        ``token_healing`` deliberately does not influence the rendered bytes.
        The contract forbids truncating the typed prefix, and the prompt now
        ends with the fixed ``completion_suffix:`` sentinel, so generation always
        resumes at a contract-owned token boundary and there is no BPE seam left
        for healing to repair.

        The budget is ``ctx_max`` alone, not ``ctx_max + cmd_max``. v2 has a
        single whole-prompt budget, and offline materialization uses
        ``min(prompt_max_tokens, sequence_max_tokens - generation_reserve)``,
        which is 512 at the shipped defaults and equals the shipped artifact's
        ``ctx_max``. Summing would retain history here that training would have
        dropped for the same input -- the same silent skew this renderer exists
        to remove. ``cmd_max`` no longer bounds anything: the contract never
        truncates the typed prefix.
        """

        rendered = render_prompt(
            PromptInput(
                source_kind=request.source_kind,
                typed_prefix=request.typed_prefix,
                cwd_hint=request.cwd_hint,
                recent_commands=request.recent_commands,
            ),
            encode=self._encode,
            max_tokens=config.ctx_max,
        )
        return list(rendered.token_ids), ""

    def _generate(
        self, prompt_ids: list[int], config: InferenceConfig
    ) -> tuple[GeneratedCandidate, ...]:
        import torch

        input_ids = torch.tensor([prompt_ids], dtype=torch.long, device=self._device)
        beams = max(1, config.beams)
        with torch.no_grad():
            output = self._model.generate(
                input_ids=input_ids,
                attention_mask=torch.ones_like(input_ids),
                num_beams=beams,
                num_return_sequences=beams,
                do_sample=False,
                early_stopping=beams > 1,
                max_new_tokens=config.max_decode_steps,
                eos_token_id=self._newline_id,
                pad_token_id=self._tokenizer.pad_token_id,
                return_dict_in_generate=True,
            )
        scores = getattr(output, "sequences_scores", None)
        score_values = scores.tolist() if scores is not None else []
        prompt_length = input_ids.shape[1]
        return tuple(
            GeneratedCandidate(
                text=self._tokenizer.decode(
                    sequence[prompt_length:], skip_special_tokens=True
                ).split("\n", 1)[0],
                score=float(score_values[index] if score_values else -index),
            )
            for index, sequence in enumerate(output.sequences[:beams])
        )


def _apply_budget(config: InferenceConfig, budget: DecodeBudget | None) -> InferenceConfig:
    if budget is None:
        return config
    beams = budget.beams if budget.beams is not None else config.beams
    steps = (
        budget.max_decode_steps if budget.max_decode_steps is not None else config.max_decode_steps
    )
    return replace(config, beams=beams, max_decode_steps=steps)


def _newline_stop_id(tokenizer: Any, configured: int | None) -> int:
    if configured is not None:
        return configured
    encoded = tokenizer("\n", add_special_tokens=False)["input_ids"]
    return encoded[-1] if encoded else tokenizer.eos_token_id


def _resolve_device(torch: Any) -> Any:
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _resolve_dtype(torch: Any) -> Any:
    value = os.environ.get(DTYPE_ENV, "float32").strip().lower()
    if value == "auto":
        return "auto"
    supported = {
        "float16": torch.float16,
        "fp16": torch.float16,
        "bfloat16": torch.bfloat16,
        "bf16": torch.bfloat16,
        "float32": torch.float32,
        "fp32": torch.float32,
    }
    if value not in supported:
        allowed = "auto, float16, bfloat16, float32"
        raise ValueError(f"{DTYPE_ENV} must be one of: {allowed}")
    return supported[value]


def _place_model(model: Any, torch: Any, device: Any) -> Any:
    try:
        model.to(device)
        return device
    except (RuntimeError, TypeError) as exc:
        cpu = torch.device("cpu")
        logger.warning("failed to place neural model on %s; using CPU: %s", device, exc)
        model.to(cpu)
        return cpu
