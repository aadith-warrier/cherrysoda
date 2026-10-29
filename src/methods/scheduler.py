
from dataclasses import asdict, dataclass, field
from typing import Optional

from src.graph.registry import build_graph
from src.methods.graph_remask import GraphRemasker, RemaskConfig, positions_overlapping, token_char_spans

SCAFFOLD = "__scaffold__"


@dataclass
class ScheduleConfig:
    tokens_per_unit: int = 1
    temperature: Optional[float] = None


class DependencyPlan:
    def __init__(self, graph, spans: list, answer_len: int, total_len: int, tokens_per_unit: int = 1):
        step_ids = [n.node_id for n in graph.nodes if n.kind != "problem"]
        self.parents = {s: [] for s in step_ids}
        for e in graph.edges:
            if e.dst in self.parents and e.src in self.parents:
                self.parents[e.dst].append(e.src)
        self.pos, taken = {}, set()
        for n in graph.nodes:
            if n.kind == "problem":
                continue
            own = [p for p in positions_overlapping(spans, [(n.char_start, n.char_end)]) if p not in taken]
            self.pos[n.node_id] = set(own)
            taken.update(own)
        self.order = step_ids
        self.scaffold = set(range(answer_len)) - taken
        self.tail = set(range(answer_len, total_len))
        self.k = max(1, tokens_per_unit)
        self.commits_per_pass = []
        self.units_per_pass = []

    def levels(self) -> dict:
        depth = {}
        for s in self.order:
            depth[s] = 1 + max((depth[p] for p in self.parents[s]), default=-1)
        return depth

    def select(self, remaining: list, conf: list) -> list:
        rem, c = set(remaining), dict(zip(remaining, conf))
        done = lambda s: not (self.pos[s] & rem)
        units = [self.pos[s] & rem for s in self.order
                 if self.pos[s] & rem and all(done(p) for p in self.parents[s])]
        if self.scaffold & rem:
            units.append(self.scaffold & rem)
        if not units:
            chosen = sorted(self.tail & rem) or [remaining[0]]
            self.units_per_pass.append(1)
        else:
            chosen = []
            for u in units:
                chosen += sorted(u, key=lambda p: c[p], reverse=True)[: self.k]
            self.units_per_pass.append(len(units))
        self.commits_per_pass.append(len(chosen))
        return chosen


@dataclass
class ScheduleResult:
    draft_text: str
    final_text: str
    draft_token_ids: list
    final_token_ids: list
    nfe_draft: int
    nfe_schedule: int
    nfe_total: int
    wall_time_sec: float
    flags_before: int
    flags_after: int
    n_steps: int = 0
    n_levels: int = 0
    tokens_per_pass: float = 0.0
    skipped_reason: str = ""
    parse_warnings: int = 0
    flag_types: dict = field(default_factory=dict)
    tokens_draft: int = 0
    tokens_final: int = 0
    tokens_regenerated: int = 0
    sec_generate: float = 0.0
    sec_refine: float = 0.0
    sec_parse_verify: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("draft_token_ids"), d.pop("final_token_ids")
        return d


class ScheduledDecoder:
    def __init__(self, model, verify_fn, cfg: ScheduleConfig = None, graph_fn=build_graph):
        self.model, self.cfg = model, cfg or ScheduleConfig()
        self.inspector = GraphRemasker(model, verify_fn, RemaskConfig(), graph_fn)

    def run(self, example: dict, gen_cfg: dict, draft=None) -> ScheduleResult:
        if draft is None:
            from baselines.vanilla import run as run_generate
            draft = run_generate(self.model, example, gen_cfg)
        if draft.token_ids is None:
            raise ValueError("the model wrapper's generate() must return token_ids")
        ids = list(draft.token_ids)
        state = self.inspector.inspect(example, ids)
        base = dict(draft_text=state.text, draft_token_ids=ids, nfe_draft=draft.num_forward_passes,
                    flags_before=len(state.bad), n_steps=state.n_steps, parse_warnings=len(state.graph.parse_warnings),
                    flag_types=state.flag_types, tokens_draft=state.n_tokens, tokens_final=state.n_tokens,
                    sec_generate=draft.wall_time_sec)

        def unchanged(reason):
            return ScheduleResult(final_text=state.text, final_token_ids=ids, nfe_schedule=0, sec_parse_verify=state.seconds,
                                  nfe_total=draft.num_forward_passes, wall_time_sec=draft.wall_time_sec,
                                  flags_after=len(state.bad), skipped_reason=reason, **base)

        if state.n_steps == 0:
            return unchanged("no reasoning steps found in the draft")
        if draft.generated_text and draft.generated_text != state.text:
            return unchanged("decoded token ids differ from the wrapper's generated_text")

        _, spans = token_char_spans(self.model.tokenizer, ids[: state.n_tokens])
        plan = DependencyPlan(state.graph, spans, state.n_tokens, len(ids), self.cfg.tokens_per_unit)
        res = self.model.refine(
            example["prompt"], ids, list(range(len(ids))),
            temperature=self.cfg.temperature, allow_end_from=state.n_tokens,
            confidence_eos_eot_inf=True, select_fn=plan.select,
        )
        new_ids = list(res.token_ids)
        after = self.inspector.inspect(example, new_ids)
        body = plan.commits_per_pass[:-1] if len(plan.commits_per_pass) > 1 else plan.commits_per_pass
        return ScheduleResult(
            final_text=after.text, final_token_ids=new_ids, nfe_schedule=res.num_forward_passes,
            nfe_total=draft.num_forward_passes + res.num_forward_passes,
            wall_time_sec=draft.wall_time_sec + res.wall_time_sec, flags_after=len(after.bad),
            n_levels=1 + max(plan.levels().values(), default=0),
            tokens_per_pass=sum(body) / max(1, len(body)),
            tokens_regenerated=len(ids), sec_refine=res.wall_time_sec, sec_parse_verify=state.seconds + after.seconds,
            **{**base, "tokens_final": after.n_tokens},
        )
