"""A measured logistic baseline with a held-out provider and later-time test set."""

import numpy as np
from scipy.special import expit
from scipy.stats import rankdata

FEATURES = ["memory_warning_trend", "temperature_c", "link_retry_trend", "load"]


def snapshots(seed: int = 2026) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for provider in ("csp-aurora", "csp-borealis", "csp-cirrus"):
        days = range(0, 10) if provider != "csp-cirrus" else range(14, 19)
        for device in range(80):
            for day in days:
                features = [
                    float(rng.gamma(1.2, 1)),
                    float(rng.normal(70, 8)),
                    float(rng.gamma(1, 1)),
                    float(rng.uniform(0.2, 1)),
                ]
                latent = (
                    -6
                    + 0.9 * features[0]
                    + 0.10 * (features[1] - 65)
                    + 0.7 * features[2]
                    + features[3]
                )
                failed = bool(rng.random() < expit(latent))
                rows.append(
                    dict(
                        provider=provider,
                        device=f"{provider}-{device}",
                        day=day,
                        features=features,
                        failure_within_6h=failed,
                        failure_delay_hours=float(rng.uniform(0.5, 6)) if failed else None,
                    )
                )
    return rows


def score(y, probabilities, threshold, delays):
    alerts = probabilities >= threshold
    tp, fp = int(np.sum(alerts & y)), int(np.sum(alerts & ~y))
    fn, tn = int(np.sum(~alerts & y)), int(np.sum(~alerts & ~y))
    positives, negatives = int(y.sum()), int((~y).sum())
    auc = (
        (rankdata(probabilities)[y].sum() - positives * (positives + 1) / 2)
        / (positives * negatives)
        if positives and negatives
        else None
    )
    lead = [
        delay
        for delay, predicted, actual in zip(delays, alerts, y, strict=True)
        if predicted and actual
    ]
    return dict(
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=tp / (tp + fp) if tp + fp else None,
        recall=tp / (tp + fn) if tp + fn else None,
        roc_auc=float(auc) if auc is not None else None,
        false_alerts_per_1000_operating_hours=fp / (len(y) * 6) * 1000,
        median_warning_hours=float(np.median(lead)) if lead else None,
        observed_hours=len(y) * 6,
        threshold=float(threshold),
    )


def evaluate_prediction(seed: int = 2026) -> dict:
    data = snapshots(seed)
    train = [r for r in data if r["provider"] != "csp-cirrus" and r["day"] < 7]
    validation = [r for r in data if r["provider"] != "csp-cirrus" and r["day"] >= 7]
    test = [r for r in data if r["provider"] == "csp-cirrus"]
    x = np.array([r["features"] for r in train])
    y = np.array([r["failure_within_6h"] for r in train], dtype=float)
    mean, scale = x.mean(axis=0), x.std(axis=0)
    design = np.column_stack([np.ones(len(x)), (x - mean) / scale])
    weights = np.zeros(design.shape[1])
    for _ in range(800):
        penalty = 0.005 * weights
        penalty[0] = 0
        weights -= 0.15 * (design.T @ (expit(design @ weights) - y) / len(y) + penalty)

    def predict(rows):
        features = np.array([r["features"] for r in rows])
        return expit(np.column_stack([np.ones(len(rows)), (features - mean) / scale]) @ weights)

    val_y = np.array([r["failure_within_6h"] for r in validation])
    val_p = predict(validation)
    candidates = []
    for threshold in np.linspace(0.05, 0.8, 31):
        metrics = score(val_y, val_p, threshold, [r["failure_delay_hours"] for r in validation])
        p, r = metrics["precision"] or 0, metrics["recall"] or 0
        candidates.append((2 * p * r / (p + r) if p + r else 0, float(threshold)))
    threshold = max(candidates)[1]
    test_y = np.array([r["failure_within_6h"] for r in test])
    delays = [r["failure_delay_hours"] for r in test]
    rules = np.array(
        [
            float(r["features"][0] >= 3 or r["features"][1] >= 84 or r["features"][2] >= 3)
            for r in test
        ]
    )
    train_ids, test_ids = {r["device"] for r in train}, {r["device"] for r in test}
    return dict(
        origin="synthetic",
        seed=seed,
        features=FEATURES,
        split=dict(
            train=len(train),
            validation=len(validation),
            test=len(test),
            train_days=[0, 6],
            validation_days=[7, 9],
            test_days=[14, 18],
            held_out_provider="csp-cirrus",
            device_overlap=len(train_ids & test_ids),
        ),
        preprocessing="Mean/scale fit on training only; threshold maximizes validation F1; test untouched",
        logistic=score(test_y, predict(test), threshold, delays),
        rules=score(test_y, rules, 0.5, delays),
        coefficients=dict(zip(["intercept", *FEATURES], weights.tolist(), strict=True)),
        limits="Independent synthetic snapshot benchmark; no real failure prediction or calibrated production-risk claim",
    )
