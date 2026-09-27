# Quorum credit economy simulation

Agent-based simulation of the review-credit economy used by [Quorum: An Open Journal of Information Technology](https://jquorum.org), a journal that is free for readers and authors and uses peer review as its currency: every first complete review of a manuscript earns one credit, and one credit pays for one submission.

This repository contains the code, parameters, random seeds and complete outputs behind the simulation study in:

> Ozer, M. (2026). Paying for publication with peer review: Design and simulation of a fee-free, credit-based open access journal for information technology. *arXiv preprint* (link to be added).

## What the model represents

The simulation steps through two years (730 days) of journal operation and follows the rules deployed at jquorum.org:

- three reviewers per paper plus one spare invitation, a four-day invitation window, and at most two open assignments per reviewer
- strict topical matching on day 0, widened to related areas on day 7 together with an open call for volunteers
- a refunded withdrawal offer on day 30 if the panel is still incomplete
- the journal's published decision rules, with at most three review rounds
- credits minted only for a reviewer's first review of a paper; re-reviews earn none
- a genesis block of 20 invited papers submitted without credits in the first 60 days

Scholars belong to one of six editorial sections arranged in a ring. Strict matching uses the paper's own section, and broad matching adds the two neighbouring sections. All behavioural parameters (acceptance and response rates, submission rate, review times, volunteer rate) are assumptions, not estimates. The model is meant for comparing design choices, not for forecasting absolute volumes. See `results/params.json` for every parameter of every scenario.

## Scenarios

| Scenario | Change from the baseline |
|---|---|
| Baseline | 40 initial scholars, 0.40 arrivals per day, genesis block and escalation on |
| No genesis block | no genesis papers |
| No escalation | no day-7 widening and no open call |
| Low responsiveness | mean invitation acceptance 0.25 instead of 0.40 |
| Slow growth | 0.10 arrivals per day |
| Small community | 25 initial scholars, 0.05 arrivals per day |
| Small community, no escalation | as above, without escalation |

Each scenario is replicated 40 times with seeds `20260927 + r` for `r = 0 … 39`.

## Main results (means of 40 replications, after two years)

| Scenario | Members | Papers | Published | Median days to full panel | 90th pct. days | No panel within 60 days | Unspent credits per member |
|---|---|---|---|---|---|---|---|
| Baseline | 330 | 603 | 318 | 7.0 | 10.2 | 0.0% | 3.7 |
| No genesis block | 336 | 0 | 0 | n/a | n/a | n/a | 0.0 |
| No escalation | 335 | 560 | 290 | 7.1 | 13.7 | 1.3% | 3.3 |
| Low responsiveness | 330 | 587 | 310 | 8.3 | 13.5 | 0.1% | 3.6 |
| Slow growth | 113 | 269 | 149 | 7.5 | 13.2 | 0.1% | 5.0 |
| Small community | 60 | 154 | 83 | 9.8 | 17.8 | 4.6% | 5.3 |
| Small community, no escalation | 61 | 81 | 25 | 7.3 | 187.7 | 48.8% | 1.7 |

Median and 90th-percentile waits are computed over papers that obtained a full panel. The "no panel within 60 days" column counts papers submitted at least 60 days before the end of the horizon that had not obtained a full panel 60 days after submission.

## Reproduce

Requires Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cd simulation
python credit_economy_sim.py      # runs all scenarios, writes ../results (about one minute)
python make_figures.py            # writes ../figures
```

The run is deterministic for a given NumPy version, so the files in `results/` should be reproduced exactly.

## Files

| Path | Contents |
|---|---|
| `simulation/credit_economy_sim.py` | the model and the scenario definitions |
| `simulation/make_figures.py` | the five figures used in the paper |
| `results/summary.csv` | mean and standard deviation of every metric per scenario |
| `results/series.json` | daily mean, 10th and 90th percentile of members, submissions, publications, credits and waiting papers |
| `results/waits.json` | days to a full panel for every eligible paper, all replications pooled (1e9 marks papers that never obtained a panel) |
| `results/params.json` | all parameters, seeds and the horizon |
| `figures/` | figures 1 to 5 of the paper |

## License

Code: MIT License (see `LICENSE`). Results and figures: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Citation

If you use this code or its results, please cite the paper above. Citation metadata is in `CITATION.cff`.
