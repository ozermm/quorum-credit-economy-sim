"""
Agent-based simulation of the Quorum review-credit economy.

The model mirrors the rules deployed at jquorum.org: three reviewers per paper
plus one spare invitation, a four-day invitation window, a load cap of two
open assignments per reviewer, strict topical matching that widens on day 7
together with an open call for volunteers, a refunded withdrawal offer on
day 30, the published decision rules with at most three rounds, and credits
minted only for a reviewer's first review of a paper.

All behavioural parameters are assumptions, not estimates. The simulation is
used to compare design choices, not to forecast absolute volumes.

    python credit_economy_sim.py            # all scenarios, writes ../results
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SECTIONS = 6          # six editorial sections, arranged in a ring
REVIEWERS = 3
BUFFER = 1
INVITE_DAYS = 4
MAX_LOAD = 2
MAX_ROUNDS = 3
HORIZON = 730         # two years, in days


@dataclass(frozen=True)
class Params:
    name: str
    initial_scholars: int = 40
    arrivals_per_day: float = 0.40
    genesis_papers: int = 20
    genesis_window: int = 60
    mean_accept: float = 0.40        # mean probability of accepting an invitation
    ignore_prob: float = 0.20        # probability of never answering
    submit_hazard: float = 3 / 365   # daily chance a scholar with a credit submits
    max_open_own: int = 1            # own papers under review at the same time
    review_days_mean: float = 12.0
    rereview_days_mean: float = 6.0
    miss_prob: float = 0.05          # reviewer misses the deadline and is replaced
    escalation: bool = True          # day-7 widening and open call
    volunteer_rate: float = 0.004    # daily chance an eligible scholar volunteers
    withdraw_prob_day30: float = 0.5


@dataclass
class Paper:
    pid: int
    author: int
    section: int
    quality: float
    submitted: int
    genesis: bool
    status: str = "seeking"          # seeking | review | revising | accepted | rejected | withdrawn
    round: int = 1
    seek_start: int = 0
    widened: bool = False
    panel: set = field(default_factory=set)
    involved: set = field(default_factory=set)        # everyone ever invited or on the panel
    pending_invites: dict = field(default_factory=dict)  # reviewer -> (answer_day, answer)
    reviews_due: dict = field(default_factory=dict)      # reviewer -> day the review arrives (or -1 = missed at day X)
    missed: dict = field(default_factory=dict)           # reviewer -> removal day
    recs: dict = field(default_factory=dict)             # reviewer -> recommendation this round
    credited: set = field(default_factory=set)           # reviewers already paid for this paper
    full_panel_day: int | None = None
    first_decision_day: int | None = None
    final_day: int | None = None
    revision_back: int | None = None
    last_outcome: str = ""
    reached_day7: bool = False
    reached_day30: bool = False


def recommendation(q: float, rng) -> str:
    score = q + rng.normal(0, 0.18)
    if score > 0.78:
        return "ACCEPT"
    if score > 0.55:
        return "MINOR"
    if score > 0.32:
        return "MAJOR"
    return "REJECT"


def decide(recs: list[str], rnd: int) -> str:
    """The decision rules published by the journal (https://jquorum.org/about)."""
    n = len(recs)
    reject = recs.count("REJECT")
    major = recs.count("MAJOR")
    if reject * 2 > n:
        return "REJECT"
    if recs.count("ACCEPT") == n:
        return "ACCEPT"
    if rnd >= MAX_ROUNDS:
        return "ACCEPT" if reject == 0 and major == 0 else "REJECT"
    if reject or major:
        return "MAJOR"
    return "MINOR"


def run(p: Params, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    section: list[int] = []
    p_accept: list[float] = []
    credits: list[int] = []
    load: list[int] = []
    joined: list[int] = []
    reviews_done: list[int] = []
    open_own: list[int] = []

    a = 4.0
    b = a * (1 - p.mean_accept) / p.mean_accept

    def add_scholar(day: int) -> int:
        section.append(int(rng.integers(SECTIONS)))
        p_accept.append(float(rng.beta(a, b)))
        credits.append(0)
        load.append(0)
        joined.append(day)
        reviews_done.append(0)
        open_own.append(0)
        return len(section) - 1

    for _ in range(p.initial_scholars):
        add_scholar(0)

    papers: list[Paper] = []
    genesis_days = sorted(rng.integers(0, p.genesis_window, size=p.genesis_papers)) if p.genesis_papers else []
    genesis_authors = list(rng.choice(p.initial_scholars, size=min(p.genesis_papers, p.initial_scholars), replace=False))

    daily = {k: np.zeros(HORIZON) for k in ("members", "submitted", "published", "credits_held", "seeking")}
    minted = 0
    spent = 0

    def adjacent(s: int) -> set[int]:
        return {s, (s - 1) % SECTIONS, (s + 1) % SECTIONS}

    def submit(author: int, day: int, genesis: bool):
        nonlocal spent
        if not genesis:
            credits[author] -= 1
            spent += 1
        open_own[author] += 1
        papers.append(Paper(len(papers), author, section[author], float(rng.uniform(0.2, 1.0)), day, genesis, seek_start=day))

    def release(paper: Paper):
        for r in paper.panel:
            load[r] -= 1
        for r in list(paper.pending_invites):
            load[r] -= 1
        paper.panel.clear()
        paper.pending_invites.clear()
        open_own[paper.author] -= 1

    def start_round(paper: Paper, day: int):
        paper.recs = {}
        paper.status = "review"
        mean = p.review_days_mean if paper.round == 1 else p.rereview_days_mean
        for r in paper.panel:
            schedule_review(paper, r, day, mean)

    def schedule_review(paper: Paper, r: int, day: int, mean: float):
        if rng.random() < p.miss_prob:
            paper.missed[r] = day + int(mean * 1.8) + 5
        else:
            paper.reviews_due[r] = day + max(1, int(rng.lognormal(math.log(mean), 0.45)))

    for day in range(HORIZON):
        # 1. new scholars
        for _ in range(rng.poisson(p.arrivals_per_day)):
            add_scholar(day)

        # 2. genesis papers, then credit-funded papers
        while genesis_days and genesis_days[0] == day:
            genesis_days.pop(0)
            submit(int(genesis_authors.pop()), day, True)
        for s in range(len(section)):
            if credits[s] >= 1 and open_own[s] < p.max_open_own and rng.random() < p.submit_hazard:
                submit(s, day, False)

        for paper in papers:
            if paper.status in ("accepted", "rejected", "withdrawn"):
                continue

            # 3. missed deadlines: the reviewer is removed and replaced
            for r, removal in list(paper.missed.items()):
                if removal <= day:
                    del paper.missed[r]
                    paper.panel.discard(r)
                    load[r] -= 1
                    if paper.status == "review":
                        paper.status = "seeking"
                        paper.seek_start = day
                        paper.widened = False

            # 4. revisions coming back start the next round
            if paper.status == "revising" and paper.revision_back == day:
                paper.round += 1
                paper.quality = min(1.0, paper.quality + (0.14 if paper.last_outcome == "MAJOR" else 0.08))
                if len(paper.panel) >= REVIEWERS:
                    start_round(paper, day)
                else:
                    paper.status = "seeking"
                    paper.seek_start = day
                    paper.widened = False
                continue
            if paper.status == "revising":
                continue

            # 5. answers to invitations
            for r, (answer_day, answer) in list(paper.pending_invites.items()):
                if answer_day != day:
                    continue
                del paper.pending_invites[r]
                if answer == "accept" and len(paper.panel) < REVIEWERS and paper.status == "seeking":
                    paper.panel.add(r)
                else:
                    load[r] -= 1

            # 6. reviews arriving
            for r, due in list(paper.reviews_due.items()):
                if due != day:
                    continue
                del paper.reviews_due[r]
                if r not in paper.panel:
                    continue
                paper.recs[r] = recommendation(paper.quality, rng)
                reviews_done[r] += 1
                if r not in paper.credited:
                    paper.credited.add(r)
                    credits[r] += 1
                    minted += 1

            if paper.status == "seeking":
                waited = day - paper.seek_start
                if paper.round == 1 and waited >= 7:
                    paper.reached_day7 = True
                if p.escalation and waited >= 7:
                    paper.widened = True
                if paper.round == 1 and waited >= 30 and not paper.reached_day30:
                    paper.reached_day30 = True
                    if rng.random() < p.withdraw_prob_day30:
                        paper.status = "withdrawn"
                        paper.final_day = day
                        if not paper.genesis:
                            credits[paper.author] += 1   # refunded
                            spent -= 1
                        release(paper)
                        continue

                allowed = adjacent(paper.section) if paper.widened else {paper.section}
                eligible = [
                    s for s in range(len(section))
                    if section[s] in allowed and s != paper.author and s not in paper.involved and load[s] < MAX_LOAD
                ]

                # 7. volunteers from the open call
                if p.escalation and paper.widened:
                    for s in eligible:
                        if len(paper.panel) >= REVIEWERS:
                            break
                        if rng.random() < p.volunteer_rate:
                            paper.panel.add(s)
                            paper.involved.add(s)
                            load[s] += 1
                    eligible = [s for s in eligible if s not in paper.involved]

                # 8. top up invitations
                need = REVIEWERS - len(paper.panel) + BUFFER - len(paper.pending_invites)
                if need > 0 and eligible:
                    weights = np.array([1.0 / (1 + load[s]) for s in eligible])
                    pick = rng.choice(len(eligible), size=min(need, len(eligible)), replace=False, p=weights / weights.sum())
                    for i in pick:
                        s = eligible[int(i)]
                        u = rng.random()
                        if u < p_accept[s]:
                            answer, when = "accept", day + int(rng.integers(1, INVITE_DAYS + 1))
                        elif u < p_accept[s] + p.ignore_prob:
                            answer, when = "ignore", day + INVITE_DAYS
                        else:
                            answer, when = "decline", day + int(rng.integers(1, INVITE_DAYS + 1))
                        paper.pending_invites[s] = (when, answer)
                        paper.involved.add(s)
                        load[s] += 1

                # 9. panel complete: spares withdrawn, reviews begin
                if len(paper.panel) >= REVIEWERS:
                    for r in list(paper.pending_invites):
                        load[r] -= 1
                    paper.pending_invites.clear()
                    if paper.full_panel_day is None:
                        paper.full_panel_day = day
                    paper.status = "review"
                    mean = p.review_days_mean if paper.round == 1 else p.rereview_days_mean
                    for r in paper.panel:
                        if r not in paper.recs and r not in paper.reviews_due and r not in paper.missed:
                            schedule_review(paper, r, day, mean)

            # 10. decision when the whole panel has reported
            if paper.status == "review" and len(paper.recs) >= REVIEWERS:
                outcome = decide(list(paper.recs.values()), paper.round)
                if paper.first_decision_day is None:
                    paper.first_decision_day = day
                if outcome in ("ACCEPT", "REJECT"):
                    paper.status = "accepted" if outcome == "ACCEPT" else "rejected"
                    paper.final_day = day
                    release(paper)
                else:
                    paper.status = "revising"
                    paper.last_outcome = outcome
                    paper.revision_back = day + int(rng.integers(20, 45) if outcome == "MAJOR" else rng.integers(7, 21))

        daily["members"][day] = len(section)
        daily["submitted"][day] = len(papers)
        daily["published"][day] = sum(1 for x in papers if x.status == "accepted")
        daily["credits_held"][day] = sum(credits)
        daily["seeking"][day] = sum(1 for x in papers if x.status == "seeking")

    first_round = [x for x in papers if x.full_panel_day is not None]
    wait = [x.full_panel_day - x.submitted for x in first_round]
    # For distributions, include papers that never got a panel (as infinity),
    # and only papers submitted at least 60 days before the horizon so every
    # paper had a fair chance to be reviewed.
    eligible_for_cdf = [x for x in papers if x.submitted <= HORIZON - 60]
    waits_all = [(x.full_panel_day - x.submitted) if x.full_panel_day is not None else math.inf for x in eligible_for_cdf]
    never = float(np.mean([w == math.inf or w > 60 for w in waits_all])) if waits_all else float("nan")
    decided = [x for x in papers if x.first_decision_day is not None]
    reviews = np.array(sorted(reviews_done, reverse=True))
    active_reviewers = reviews[reviews > 0]
    top20 = active_reviewers[: max(1, int(round(len(active_reviewers) * 0.2)))].sum() / max(1, active_reviewers.sum())

    return {
        "members": len(section),
        "papers": len(papers),
        "genesis": sum(1 for x in papers if x.genesis),
        "accepted": sum(1 for x in papers if x.status == "accepted"),
        "rejected": sum(1 for x in papers if x.status == "rejected"),
        "withdrawn": sum(1 for x in papers if x.status == "withdrawn"),
        "wait_median": float(np.median(wait)) if wait else float("nan"),
        "wait_p90": float(np.percentile(wait, 90)) if wait else float("nan"),
        "share_day7": float(np.mean([x.reached_day7 for x in papers])) if papers else float("nan"),
        "share_day30": float(np.mean([x.reached_day30 for x in papers])) if papers else float("nan"),
        "decision_median": float(np.median([x.first_decision_day - x.submitted for x in decided])) if decided else float("nan"),
        "credits_per_member": sum(credits) / len(section),
        "minted": minted,
        "spent": spent,
        "top20_review_share": float(top20),
        "share_members_reviewed": float(np.mean(np.array(reviews_done) > 0)),
        "no_panel_60d": never,
        "waits": [w if w != math.inf else 1e9 for w in waits_all],
        "daily": {k: v.tolist() for k, v in daily.items()},
    }


SCENARIOS = [
    Params("Baseline"),
    Params("No genesis block", genesis_papers=0),
    Params("No escalation", escalation=False),
    Params("Low responsiveness", mean_accept=0.25),
    Params("Slow growth", arrivals_per_day=0.10),
    Params("Small community", initial_scholars=25, arrivals_per_day=0.05),
    Params("Small community, no escalation", initial_scholars=25, arrivals_per_day=0.05, escalation=False),
]

SUMMARY_KEYS = [
    "members", "papers", "genesis", "accepted", "rejected", "withdrawn", "wait_median", "wait_p90",
    "share_day7", "share_day30", "decision_median", "credits_per_member", "minted", "spent",
    "top20_review_share", "share_members_reviewed", "no_panel_60d",
]


def main(replications: int = 40, base_seed: int = 20260927):
    out = Path(__file__).resolve().parent.parent / "results"
    out.mkdir(exist_ok=True)
    summary_rows = []
    series = {}
    waits = {}
    for sc in SCENARIOS:
        runs = [run(sc, base_seed + r) for r in range(replications)]
        row = {"scenario": sc.name}
        for k in SUMMARY_KEYS:
            vals = np.array([rr[k] for rr in runs], dtype=float)
            row[k + "_mean"] = float(np.nanmean(vals)) if not np.all(np.isnan(vals)) else float("nan")
            row[k + "_sd"] = float(np.nanstd(vals)) if not np.all(np.isnan(vals)) else float("nan")
        summary_rows.append(row)
        series[sc.name] = {k: np.mean([rr["daily"][k] for rr in runs], axis=0).tolist() for k in runs[0]["daily"]}
        series[sc.name + "__p10"] = {k: np.percentile([rr["daily"][k] for rr in runs], 10, axis=0).tolist() for k in runs[0]["daily"]}
        series[sc.name + "__p90"] = {k: np.percentile([rr["daily"][k] for rr in runs], 90, axis=0).tolist() for k in runs[0]["daily"]}
        waits[sc.name] = [w for rr in runs for w in rr["waits"]]
        print(f"{sc.name:22s} papers {row['papers_mean']:6.1f}  accepted {row['accepted_mean']:5.1f}  "
              f"wait med {row['wait_median_mean']:5.1f} p90 {row['wait_p90_mean']:5.1f}  "
              f"day7 {row['share_day7_mean']:.2f} day30 {row['share_day30_mean']:.2f}  credits/member {row['credits_per_member_mean']:.2f}")

    with open(out / "summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        w.writeheader()
        w.writerows(summary_rows)
    with open(out / "series.json", "w") as f:
        json.dump(series, f)
    with open(out / "waits.json", "w") as f:
        json.dump(waits, f)
    with open(out / "params.json", "w") as f:
        json.dump({"replications": replications, "base_seed": base_seed, "horizon_days": HORIZON,
                   "scenarios": [sc.__dict__ for sc in SCENARIOS]}, f, indent=2)


if __name__ == "__main__":
    main()
