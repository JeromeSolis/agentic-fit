from agentic_fit.tasks_meta import SUMMARIES


def test_summaries_keyed_by_seven_categories():
    expected = {"cli_parsing", "data_validation", "date_handling",
                "http_client", "retrying", "templating", "yaml_config"}
    assert set(SUMMARIES) == expected
    assert all(isinstance(v, str) and v for v in SUMMARIES.values())
