# Predictive health benchmark

This is an actual trained logistic model evaluated against an explainable rules baseline. All training and test data are synthetic. It does not establish real GPU prediction accuracy.

## Input and target

Features are memory-warning trend, temperature, link-retry trend and load. Each row represents a non-overlapping six-hour observation window. Features are generated first, then a noisy future interruption is sampled. The label asks whether an interruption occurs within the next six hours. Warning time is the sampled interval from the observation to that future failure.

No source incident ID, failure timestamp, future counter, ground-truth cause, or post-failure measurement enters the feature vector. This is an offline benchmark; it does not simulate alert suppression or repeated real-world incident association.

## Split and fitting

- Train: Aurora/Borealis, days 0–6, 1,120 snapshots.
- Validation: the same providers, days 7–9, 480 snapshots.
- Test: Cirrus, days 14–18, 400 snapshots, entirely disjoint devices.

Mean and scale are fit on training only. Gradient descent fits regularized logistic coefficients on training labels. Threshold selection maximizes validation F1 across a declared grid. The third provider's test labels are used only in the final score.

Report precision, recall, ROC AUC, TP/FP/FN/TN, false alerts per 1,000 observed operating hours and median warning time for true positives. AUC handles tied scores with average ranks. Undefined metrics remain null. The baseline alerts on authored memory, temperature and retry thresholds.

A strong score on this generator does not demonstrate calibrated failure probability. Production validation needs real outcome labels, missing-data behavior, fleet and time splits, drift checks, alert costs, cluster correlation and customer acceptance. Both false positives and missed interruptions remain visible in the recorded report.
