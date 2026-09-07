from tools.observability.evaluation_metrics_server import render_metrics


def test_evaluation_metrics_are_derived_from_real_checked_in_csv() -> None:
    rendered = render_metrics("docs/evaluation/competition-ablation-v1/results/full.csv")
    assert 'gaitlogic_eval_false_global_block_rate{variant="F_FULL_GAITLOGIC"}' in rendered
    assert "gaitlogic_eval_fact_consistency" in rendered
    assert "96.38" not in rendered
