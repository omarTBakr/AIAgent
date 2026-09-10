from utils.workflow_ids import WORKFLOW_ID_PREFIX, task_id_from, workflow_id_for


def test_workflow_id_is_the_prefixed_task_id():
    assert workflow_id_for("a1b2c3d4") == "process-pdf-a1b2c3d4"


def test_the_two_helpers_round_trip():
    assert task_id_from(workflow_id_for("a1b2c3d4")) == "a1b2c3d4"


def test_an_unprefixed_id_is_returned_as_is():
    assert task_id_from("a1b2c3d4") == "a1b2c3d4"


def test_the_prefix_is_used_rather_than_hardcoded():
    assert workflow_id_for("x").startswith(WORKFLOW_ID_PREFIX)
