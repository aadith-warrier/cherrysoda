import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from src.graph.registry import build_graph
from src.models.base import truncate_at_stop
from src.verify.base import INVALID

def affected_subgraph(graph, bad_ids) -> list:
    children = {}
    for e in graph.edges:
        children.setdefault(e.src, []).append(e.dst)
    seen, stack = set(bad_ids), list(bad_ids)
    while stack:
        for c in children.get(stack.pop(), []):
            if c not in seen:
                seen.add(c)
                stack.append(c)
    return [n.node_id for n in graph.nodes if n.node_id in seen and n.kind != "problem"]

def token_char_spans(tokenizer, ids: list):
    full = tokenizer.decode(ids, skip_special_tokens=True)
    lead = len(full) - len(full.lstrip())
    text = full.strip()
    spans, prev = [], 0
    for i in range(len(ids)):
        piece = tokenizer.decode(ids[: i + 1], skip_special_tokens=True).rstrip("�")  # half a UTF-8 char
        end = max(prev, len(piece))
        s, e = min(max(prev - lead, 0), len(text)), min(max(end - lead, 0), len(text))
        spans.append((s, e))
        prev = end
    return text, spans


def positions_overlapping(spans: list, char_ranges: list) -> list:
    out = []
    for i, (s, e) in enumerate(spans):
        if e > s and any(s < b and e > a for a, b in char_ranges):
            out.append(i)
    return out

@dataclass
class RemaskConfig:
    mode: str = "graph"
    max_rounds: int = 3
    steps_per_round: Optional[int] = None
    temperature: Optional[float] = None
    confidence_eos_eot_inf: bool = True
    stop_if_unchanged: bool = True
    schedule: bool = False
    tokens_per_unit: int = 1
    
    def __post_init__(self):
        if self.mode not in ("graph", "full"):
            raise ValueError(f"mode must be 'graph' or 'full', got {self.mode!r}")
        if self.schedule and self.mode != "graph":
            raise ValueError("schedule: true only makes sense with mode: graph")


@dataclass
class Inspection:
    text: str
    n_tokens: int
    graph: object
    verdicts: dict
    bad: list
    seconds: float = 0.0

    @property
    def n_steps(self) -> int:
        return sum(1 for n in self.graph.nodes if n.kind in ("calc", "claim"))

    @property
    def flag_types(self) -> dict:
        return dict(Counter(self.verdicts[b].error_type or "unspecified" for b in self.bad))


@dataclass
class RoundLog:
    round: int
    flagged: list
    affected: list
    n_remasked: int
    remask_ratio: float
    affected_ratio: float
    nfe: int
    flagged_after: int
    changed: bool


@dataclass
class RemaskResult:
    draft_text: str
    final_text: str
    draft_token_ids: list
    final_token_ids: list
    nfe_draft: int
    nfe_total: int
    wall_time_sec: float
    flags_before: int
    flags_after: int
    rounds: list = field(default_factory=list)
    skipped_reason: str = ""
    n_steps: int = 0
    parse_warnings: int = 0
    flag_types: dict = field(default_factory=dict)
    tokens_draft: int = 0
    tokens_final: int = 0
    tokens_regenerated: int = 0
    sec_generate: float = 0.0
    sec_refine: float = 0.0
    sec_parse_verify: float = 0.0

    @property
    def consistent_before(self) -> bool:
        return self.flags_before == 0

    @property
    def consistent_after(self) -> bool:
        return self.flags_after == 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("draft_token_ids"), d.pop("final_token_ids")
        d["rounds"] = [asdict(r) if hasattr(r, "__dataclass_fields__") else r for r in self.rounds]
        return d


class GraphRemasker:
    def __init__(self, model, verify_fn: Callable, cfg: RemaskConfig = None, graph_fn: Callable = build_graph):
        self.model, self.verify_fn, self.cfg, self.graph_fn = model, verify_fn, cfg or RemaskConfig(), graph_fn

    def _deterministic(self) -> bool:
        t = self.cfg.temperature
        if t is None:
            t = ((getattr(self.model, "config", None) or {}).get("generation") or {}).get("temperature", 0.0)
        return not t

    def inspect(self, example: dict, token_ids: list) -> Inspection:
        t0 = time.perf_counter()
        answer_ids = truncate_at_stop(token_ids, self.model.stop_token_ids)
        text, _ = token_char_spans(self.model.tokenizer, answer_ids)
        record = {
            "example_id": example["example_id"],
            "dataset": example.get("metadata", {}).get("dataset") or example.get("dataset"),
            "prompt": example["prompt"],
            "generation": text,
        }
        graph = self.graph_fn(record)
        verdicts = self.verify_fn(graph)
        bad = [n.node_id for n in graph.nodes if n.node_id in verdicts and verdicts[n.node_id].status == INVALID]
        return Inspection(text, len(answer_ids), graph, verdicts, bad, time.perf_counter() - t0)

    def plan(self, state: Inspection, token_ids: list):
        """(positions to remask, allow_end_from, affected step ids)."""
        stop = self.model.stop_token_ids
        L = state.n_tokens
        if self.cfg.mode == "full":
            return list(range(len(token_ids))), 0, [n.node_id for n in state.graph.nodes if n.kind != "problem"]

        affected = affected_subgraph(state.graph, state.bad)
        _, spans = token_char_spans(self.model.tokenizer, token_ids[:L])
        in_affected = set(affected)
        ranges = [(n.char_start, n.char_end) for n in state.graph.nodes if n.node_id in in_affected]
        content = positions_overlapping(spans, ranges)
        if not content:
            return [], 0, affected

        in_content = set(content)
        kept = [i for i in range(L) if i not in in_content and token_ids[i] not in stop and spans[i][1] > spans[i][0]]
        last_kept = max(kept) if kept else -1
        tail_free = max(content) > last_kept
        tail = list(range(L, len(token_ids))) if tail_free else []
        allow_end_from = last_kept + 1 if tail_free else len(token_ids) + 1
        return sorted(set(content) | set(tail)), allow_end_from, affected

    def run(self, example: dict, gen_cfg: dict, draft=None) -> RemaskResult:
        if draft is None:
            from baselines.vanilla import run as run_generate
            draft = run_generate(self.model, example, gen_cfg)
        if draft.token_ids is None:
            raise ValueError("the model wrapper's generate() must return token_ids")
        ids = list(draft.token_ids)
        nfe, wall = draft.num_forward_passes, draft.wall_time_sec
        sec_refine = 0.0
        state = self.inspect(example, ids)
        first, rounds, skipped, parse_secs = state, [], "", []
        if draft.generated_text and draft.generated_text != first.text:
            skipped = "decoded token ids differ from the wrapper's generated_text"
            state = type(state)(state.text, state.n_tokens, state.graph, state.verdicts, [])

        for r in range(1, self.cfg.max_rounds + 1):
            if not state.bad:
                break
            positions, allow_end_from, affected = self.plan(state, ids)
            if not positions:
                skipped = "flagged steps could not be mapped to token positions"
                break
            select_fn = None
            if self.cfg.schedule:
                from src.methods.scheduler import DependencyPlan
                _, spans = token_char_spans(self.model.tokenizer, ids[: state.n_tokens])
                select_fn = DependencyPlan(state.graph, spans, state.n_tokens, len(ids), self.cfg.tokens_per_unit).select
            res = self.model.refine(
                example["prompt"], ids, positions,
                num_denoising_steps=self.cfg.steps_per_round,
                temperature=self.cfg.temperature,
                allow_end_from=allow_end_from,
                confidence_eos_eot_inf=self.cfg.confidence_eos_eot_inf,
                select_fn=select_fn,
            )
            nfe += res.num_forward_passes
            wall += res.wall_time_sec
            sec_refine += res.wall_time_sec
            content_n = sum(1 for p in positions if p < state.n_tokens)
            new_ids = list(res.token_ids)
            new_state = self.inspect(example, new_ids)
            changed = new_state.text != state.text
            n_steps = max(1, state.n_steps)
            rounds.append(RoundLog(
                round=r, flagged=list(state.bad), affected=list(affected), n_remasked=content_n,
                remask_ratio=content_n / max(1, state.n_tokens),
                affected_ratio=len([a for a in affected if state.graph.node(a).kind in ("calc", "claim")]) / n_steps,
                nfe=res.num_forward_passes, flagged_after=len(new_state.bad), changed=changed,
            ))
            ids, state = new_ids, new_state
            parse_secs.append(new_state.seconds)
            if not changed and self.cfg.stop_if_unchanged and self._deterministic():
                break

        return RemaskResult(
            draft_text=first.text, final_text=state.text,
            draft_token_ids=list(draft.token_ids), final_token_ids=ids,
            nfe_draft=draft.num_forward_passes, nfe_total=nfe,
            wall_time_sec=wall,
            flags_before=len(first.bad), flags_after=len(state.bad),
            rounds=rounds, skipped_reason=skipped,
            n_steps=first.n_steps, parse_warnings=len(first.graph.parse_warnings), flag_types=first.flag_types,
            tokens_draft=first.n_tokens, tokens_final=state.n_tokens,
            tokens_regenerated=sum(r.n_remasked for r in rounds),
            sec_generate=draft.wall_time_sec, sec_refine=sec_refine,
            sec_parse_verify=first.seconds + sum(parse_secs),
        )
