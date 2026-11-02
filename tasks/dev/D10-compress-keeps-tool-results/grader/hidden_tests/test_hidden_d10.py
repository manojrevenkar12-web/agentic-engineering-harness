from mrp.cache import compress

LONG = "This is a long turn about the quarterly numbers. " * 40


def convo(n_before: int, tools: int) -> list[dict]:
    msgs = [{"role": "system", "content": "You are helpful."}]
    for i in range(n_before):
        msgs.append({"role": "user" if i % 2 == 0 else "assistant", "content": f"{i}. {LONG}"})
    msgs.append({"role": "assistant", "content": "", "tool_calls": [{"id": f"c{k}", "type": "function"} for k in range(tools)]})
    for k in range(tools):
        msgs.append({"role": "tool", "tool_call_id": f"c{k}", "content": f"result {k} " + LONG})
    msgs.append({"role": "user", "content": "And now?"})
    return msgs


def check_pairs(out: list[dict]) -> None:
    for i, m in enumerate(out):
        if m["role"] == "tool":
            j = i
            while out[j]["role"] == "tool":
                j -= 1
            assert out[j]["role"] == "assistant" and out[j].get("tool_calls"), "a tool result lost its call"


def test_a_cut_inside_tool_results_keeps_the_call():
    msgs = convo(10, 3)  # the last four turns start at the first tool result
    out, saved = compress(msgs, budget_tokens=500)
    assert saved > 0
    check_pairs(out)
    assert sum(m["role"] == "tool" for m in out) == 3


def test_a_cut_right_after_the_call_keeps_all_results():
    msgs = convo(10, 4)
    out, _ = compress(msgs, budget_tokens=500)
    check_pairs(out)
    assert sum(m["role"] == "tool" for m in out) == 4


def test_system_first_and_digest_unchanged():
    msgs = convo(10, 3)
    out, _ = compress(msgs, budget_tokens=500)
    assert out[0] == msgs[0]
    assert out[1]["role"] == "system" and "condensed" in out[1]["content"]
    assert out[-1] == msgs[-1]


def test_without_tools_behaviour_is_unchanged():
    msgs = [{"role": "system", "content": "s"}] + [{"role": "user" if i % 2 == 0 else "assistant", "content": LONG} for i in range(12)]
    out, _ = compress(msgs, budget_tokens=500)
    assert out[2:] == msgs[-4:]


def test_many_system_messages_and_few_turns_keep_every_turn():
    msgs = [{"role": "system", "content": f"rule {i}. " + LONG} for i in range(4)] + [
        {"role": "user", "content": LONG},
        {"role": "assistant", "content": LONG},
    ]
    out, _ = compress(msgs, budget_tokens=500)
    assert [m for m in out if m["role"] != "system"] == msgs[4:]
