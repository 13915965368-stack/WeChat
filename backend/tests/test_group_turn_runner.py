from app.services.group_turn_runner import run_single_group_agent_turn


def test_run_single_group_agent_turn_is_callable():
    assert callable(run_single_group_agent_turn)
