"""Substitution / augmentation classification, Eq. (7), and Proposition 4.

Each production episode is assigned a mode

    Z_p in {SUBSTITUTION, AUGMENTATION, NEW_TASK, SAFETY_REPLACEMENT}

with a substitution score ``S_p = Pr(dH_p < 0 | A_p, R_p, X_p)`` and a
complementary augmentation score. Entity-level indices ``S_i`` and ``A_aug_i``
are value-weighted averages of episode scores under that assignment, and they
feed the rate function directly.

**This classifier is rule-based, not learned.** It applies published thresholds
to observed changes in labour input and wages. It has no training data, no
parameters fitted to outcomes, and no confusion matrix estimated from labelled
episodes. Saying so matters: the manuscript's replication checklist asks for
"the classifier, its training data description, and its confusion matrix at each
injected error rate", and a rule-based classifier has the first and third of
those only in the sense implemented here -- the confusion matrix is the one
*induced by injected error*, not one measured against ground truth in the world.
Estimating a real confusion matrix requires episode-level panel data the testbed
does not contain.

Controlled error injection at rate ``epsilon`` flips a classified mode to a
different mode with probability ``epsilon``, which is exactly the perturbation
Proposition 4 bounds:

    |E[r_i] - r_i*| <= epsilon (alpha + theta)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .aeap import TASK_CLASSES

__all__ = ["MODES", "classify", "inject_error", "confusion_matrix",
           "episode_scores", "ClassificationResult"]

MODES = TASK_CLASSES  # ("substitution", "augmentation", "new_task", "safety_replacement")
_MODE_INDEX = {m: i for i, m in enumerate(MODES)}


@dataclass
class ClassificationResult:
    modes: np.ndarray             # object array of mode names
    substitution_score: np.ndarray
    augmentation_score: np.ndarray
    true_modes: np.ndarray | None = None

    @property
    def error_rate(self) -> float:
        if self.true_modes is None:
            return 0.0
        return float(np.mean(self.modes != self.true_modes))


def episode_scores(delta_labour, delta_wage, is_new_task=None,
                   is_hazardous=None) -> tuple[np.ndarray, np.ndarray]:
    """Substitution and augmentation scores from observed episode outcomes.

    ``delta_labour`` is the proportional change in human labour input on the
    episode and ``delta_wage`` the proportional change in the wage of the
    workers involved. Both are mapped monotonically into [0, 1]: labour falling
    is evidence of substitution, wages rising is evidence of augmentation.
    """
    dl = np.asarray(delta_labour, dtype=float)
    dw = np.asarray(delta_wage, dtype=float)
    sub = np.clip(-dl, 0.0, 1.0)
    aug = np.clip(dw, 0.0, 1.0)
    return sub, aug


def classify(delta_labour, delta_wage, is_new_task=None, is_hazardous=None,
             substitution_threshold: float = 0.05,
             augmentation_threshold: float = 0.05) -> ClassificationResult:
    """Assign a mode to every episode by published rule.

    Order of precedence: a hazardous task displaced by a machine is a safety
    replacement whatever else it looks like; an episode with no prior human
    incumbent is a new task; otherwise the labour and wage changes decide
    between substitution and augmentation, with ties resolving to augmentation
    because the rate function treats augmentation as the lenient case and the
    burden of showing substitution should sit with the assessor.
    """
    sub, aug = episode_scores(delta_labour, delta_wage)
    n = sub.size
    new_task = np.zeros(n, dtype=bool) if is_new_task is None \
        else np.asarray(is_new_task, dtype=bool)
    hazardous = np.zeros(n, dtype=bool) if is_hazardous is None \
        else np.asarray(is_hazardous, dtype=bool)

    modes = np.empty(n, dtype=object)
    modes[:] = "augmentation"
    is_sub = (sub > substitution_threshold) & (sub >= aug)
    modes[is_sub] = "substitution"
    modes[(aug > augmentation_threshold) & ~is_sub] = "augmentation"
    modes[new_task] = "new_task"
    modes[hazardous] = "safety_replacement"
    return ClassificationResult(modes=modes, substitution_score=sub,
                                augmentation_score=aug, true_modes=modes.copy())


def inject_error(result: ClassificationResult, epsilon: float,
                 rng: np.random.Generator | int | None = None
                 ) -> ClassificationResult:
    """Flip each episode's mode to a different mode with probability epsilon.

    This is the perturbation Proposition 4 bounds. It is applied to the mode
    *and* to the scores, because a misclassified episode enters the entity index
    at the wrong end of [0, 1]; bounding only the mode would understate the
    error the proposition is about.
    """
    if not 0.0 <= epsilon <= 1.0:
        raise ValueError(f"classification error rate must lie in [0, 1], got {epsilon}")
    if epsilon == 0.0:
        return ClassificationResult(modes=result.modes.copy(),
                                    substitution_score=result.substitution_score.copy(),
                                    augmentation_score=result.augmentation_score.copy(),
                                    true_modes=result.modes.copy())
    if not isinstance(rng, np.random.Generator):
        rng = np.random.default_rng(rng)

    n = result.modes.size
    flip = rng.random(n) < epsilon
    modes = result.modes.copy()
    sub = result.substitution_score.copy()
    aug = result.augmentation_score.copy()

    for i in np.flatnonzero(flip):
        alternatives = [m for m in MODES if m != modes[i]]
        modes[i] = alternatives[int(rng.integers(len(alternatives)))]
        if modes[i] == "substitution":
            sub[i], aug[i] = 1.0, 0.0
        elif modes[i] == "augmentation":
            sub[i], aug[i] = 0.0, 1.0
        else:
            sub[i], aug[i] = 0.0, 0.0

    return ClassificationResult(modes=modes, substitution_score=sub,
                                augmentation_score=aug,
                                true_modes=result.modes.copy())


def confusion_matrix(result: ClassificationResult) -> np.ndarray:
    """Rows are true modes, columns observed. Requires ``true_modes``."""
    if result.true_modes is None:
        raise ValueError("no ground truth recorded; confusion matrix undefined")
    k = len(MODES)
    out = np.zeros((k, k), dtype=int)
    for true, obs in zip(result.true_modes, result.modes, strict=False):
        out[_MODE_INDEX[true], _MODE_INDEX[obs]] += 1
    return out
