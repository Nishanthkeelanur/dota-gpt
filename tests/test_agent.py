"""Tests for the tool-calling loop.

Driven by a scripted fake model, so these cover the control flow -- including
the enforcement rules -- without Ollama running. The live model is exercised
by hand and by the Step 5 test set, not here.
"""

import pytest

from src.agent.client import ask
from src.agent.prompt import NOT_SURE, is_meta
from src.agent.tools_spec import REGISTRY, TOOL_SCHEMAS, execute


class FakeModel:
    """Returns scripted replies in order and records what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, model, messages, tools):
        self.calls.append(list(messages))
        if not self.replies:
            raise AssertionError("fake model ran out of scripted replies")
        return self.replies.pop(0)


def tool_call(_tool, **arguments):
    """_tool is positional-ish on purpose: several tools take a kwarg called
    "name", which would collide with a parameter of that name here."""
    return {"message": {"content": "", "tool_calls": [
        {"function": {"name": _tool, "arguments": arguments}}
    ]}}


def text(content):
    return {"message": {"content": content, "tool_calls": []}}


# --- the happy path --------------------------------------------------------


def test_tool_result_is_executed_and_fed_back():
    fake = FakeModel(
        tool_call("pierces_spell_immunity", ability="Black Hole"),
        text("Yes, it pierces. (commit 5c0242df)"),
    )
    r = ask("Does Black Hole go through BKB?", chat_fn=fake)

    assert r["tools_used"] == 1
    assert r["refused"] is False
    assert r["trace"][0]["tool"] == "pierces_spell_immunity"
    assert r["trace"][0]["result"]["matches"][0]["value"] == "yes"

    # the real result must have been handed back to the model
    final_messages = fake.calls[-1]
    tool_messages = [m for m in final_messages if m["role"] == "tool"]
    assert len(tool_messages) == 1
    assert "dotaconstants" in tool_messages[0]["content"]


def test_multiple_laps_are_supported():
    fake = FakeModel(
        tool_call("applies_dispel", name="Euls"),
        tool_call("is_dispellable", ability="Ice Path"),
        text("No -- basic beats nothing here."),
    )
    r = ask("Does Euls dispel Ice Path?", chat_fn=fake)
    assert r["tools_used"] == 2
    assert [s["tool"] for s in r["trace"]] == ["applies_dispel", "is_dispellable"]


# --- enforcement: no tool call means no answer -----------------------------


def test_answering_without_a_tool_triggers_one_retry():
    fake = FakeModel(
        text("Yes, Black Hole pierces BKB."),           # from memory -- rejected
        tool_call("pierces_spell_immunity", ability="Black Hole"),
        text("Yes, it pierces, per the patch data."),
    )
    r = ask("Does Black Hole go through BKB?", chat_fn=fake)

    assert r["refused"] is False
    assert r["retried"] is True
    assert r["tools_used"] == 1

    # the reminder must actually have been sent
    second_prompt = fake.calls[1]
    assert any("not allowed" in m.get("content", "") for m in second_prompt)


def test_refuses_if_it_skips_tools_twice():
    fake = FakeModel(
        text("Yes, obviously."),
        text("I am certain it does."),
    )
    r = ask("Does Black Hole go through BKB?", chat_fn=fake)

    assert r["refused"] is True
    assert r["answer"] == NOT_SURE
    assert r["tools_used"] == 0
    assert "without consulting any tool" in r["reason"]


def test_meta_questions_need_no_tool():
    fake = FakeModel(text("I answer Dota interaction questions from patch data."))
    r = ask("What can you do?", chat_fn=fake)
    assert r["refused"] is False
    assert r["tools_used"] == 0


@pytest.mark.parametrize(
    "question,expected",
    [
        ("what can you do", True),
        ("Who are you?", True),
        ("Does Black Hole pierce BKB?", False),
        ("help", True),
    ],
)
def test_is_meta(question, expected):
    assert is_meta(question) is expected


def test_runaway_loop_is_capped():
    fake = FakeModel(*[tool_call("get_ability", name="Black Hole") for _ in range(10)])
    r = ask("Tell me everything", chat_fn=fake, max_iterations=3)
    assert r["refused"] is True
    assert "within 3 iterations" in r["reason"]
    assert r["tools_used"] == 3


# --- bad model output becomes data, never a crash --------------------------


def test_unknown_tool_name_is_reported_not_raised():
    fake = FakeModel(
        tool_call("summon_greevil", ability="Black Hole"),
        text("That tool does not exist."),
    )
    r = ask("Do something odd", chat_fn=fake)
    assert "No such tool" in r["trace"][0]["result"]["error"]


def test_bad_arguments_are_reported_not_raised():
    fake = FakeModel(
        tool_call("pierces_spell_immunity", wrong_kwarg="Black Hole"),
        text("I could not look that up."),
    )
    r = ask("Does it pierce?", chat_fn=fake)
    assert "Bad arguments" in r["trace"][0]["result"]["error"]


def test_hallucinated_ability_returns_not_found():
    fake = FakeModel(
        tool_call("pierces_spell_immunity", ability="Chrono Sphere of Doom"),
        text("I am not sure -- no such ability in the data."),
    )
    r = ask("Does Chrono Sphere of Doom pierce BKB?", chat_fn=fake)
    assert r["trace"][0]["result"]["found"] is False


# --- schema hygiene --------------------------------------------------------


def test_every_schema_has_a_registered_callable():
    names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    assert names == set(REGISTRY)


def test_schemas_are_well_formed():
    for schema in TOOL_SCHEMAS:
        fn = schema["function"]
        assert schema["type"] == "function"
        assert fn["description"].strip(), f"{fn['name']} needs a description"
        params = fn["parameters"]
        assert params["type"] == "object"
        for name in params["required"]:
            assert name in params["properties"], f"{fn['name']}: {name} undeclared"


def test_registry_callables_accept_their_declared_arguments():
    """A schema whose parameter names do not match the function signature
    would fail only at runtime, against the live model."""
    for schema in TOOL_SCHEMAS:
        fn = schema["function"]
        args = {name: "Black Hole" for name in fn["parameters"]["required"]}
        result = execute(fn["name"], args)
        assert "Bad arguments" not in str(result.get("error", ""))
