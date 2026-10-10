"""Structured concurrency (M8): CON-01..CON-22 (spec/11-concurrency.md), virtual clock."""

from __future__ import annotations

from runner import Result, run_source

from sayform.values import Problem


def kind(r: Result) -> str:
    assert isinstance(r.value, Problem), r
    return r.value.kind.name


LIB = """to delayed n d, needs tasks:
    sleep for d
    give back n

to missing d, needs tasks, may fail with not-found:
    sleep for d
    give back problem not-found

to invalid d, needs tasks, may fail with bad-input:
    sleep for d
    give back problem bad-input

to boom d, needs tasks:
    sleep for d
    give back 1 // 0
"""


def prog(body: str, fails: str = "", header: str = LIB) -> Result:
    main = "".join("    " + ln + "\n" for ln in body.splitlines())
    tail = f", may fail with {fails}" if fails else ""
    return run_source(
        f"edition 0\nneeds console and tasks\n\n{header}\nto main, needs console and tasks{tail}:\n{main}"
    )


def test_con_01_together_runs_all_children() -> None:
    r = prog('together:\n    show "a"\n    show "b"\n    show "c"\nshow "done"')
    assert r.out == ["a", "b", "c", "done"]


def test_con_02_all_of_list_in_source_order() -> None:
    r = prog("let xs be all of:\n    delayed(1, 3s)\n    delayed(2, 1s)\n    delayed(3, 2s)\nshow xs")
    assert r.out == ["[1, 2, 3]"]


def test_con_03_labelled_all_of_record() -> None:
    r = prog("let r be all of:\n    p: delayed(1, 2s)\n    q: delayed(2, 1s)\nshow (r's p + r's q)")
    assert r.out == ["3"]


def test_con_04_mixed_labels() -> None:
    assert prog("let r be all of:\n    p: delayed(1, 2s)\n    delayed(2, 1s)\nshow r").code == "SAY-E0130"


def test_con_05_first_of_first_success_others_cancelled() -> None:
    r = prog('let w be first of:\n    delayed("slow", 3s)\n    delayed("fast", 1s)\nshow w')
    assert r.out == ["fast"]


def test_con_06_first_of_all_fail_several() -> None:
    body = "let w be first of:\n    missing(1s)\n    invalid(2s)\nshow w"
    r = prog(body, "several")
    assert r.exit == 1 and kind(r) == "several"


def test_con_07_single_failure_unwrapped() -> None:
    body = "let xs be all of:\n    missing(1s)\n    delayed(2, 5s)\nshow xs"
    r = prog(body, "not-found")
    assert r.exit == 1 and kind(r) == "not-found"


def test_con_08_two_failures_several_in_source_order() -> None:
    body = (
        "to both, needs tasks, may fail with several:\n"
        "    let xs be all of:\n        missing(1s)\n        invalid(1s)\n"
        "    give back xs\n"
    )
    r = prog("let p be both()\nshow p's kind\nshow (p's data)['problems]", header=LIB + body)
    assert r.out == ["'several", "[problem not-found, problem bad-input]"]


def test_con_09_several_not_declared() -> None:
    body = "let xs be all of:\n    missing(1s)\n    invalid(1s)\nshow xs"
    assert prog(body, "not-found").code == "SAY-E0606"


def test_con_10_panic_in_child_repanics_with_trace() -> None:
    r = prog("together:\n    boom(1s)\n    delayed(1, 5s)")
    assert r.exit == 70 and r.code == "SAY-E0841" and "while running child (1) of `together` at L21" in r.trace


def test_con_11_within_timeout() -> None:
    r = prog('within 2 seconds:\n    sleep for 1 minute\n    show "never"\nshow "after"', "timed-out")
    assert r.exit == 1 and kind(r) == "timed-out" and r.out == []
    assert prog('within 2s:\n    sleep for 1s\nshow "in time"', "timed-out").out == ["in time"]


def test_con_12_nested_within_earliest_deadline() -> None:
    body = 'within 5s:\n    within 1s:\n        sleep for 3s\n    show "inner done"'
    r = prog(body, "timed-out")
    assert r.out == [] and kind(r) == "timed-out" and isinstance(r.value, Problem) and "1s" in r.value.message
    body = 'within 1s:\n    within 5s:\n        sleep for 3s\n    show "inner done"'
    r = prog(body, "timed-out")
    assert r.out == [] and kind(r) == "timed-out" and isinstance(r.value, Problem) and "1s" in r.value.message


def test_con_13_within_needs_time() -> None:
    assert prog("within 5:\n    show 1", "timed-out").code == "SAY-E0605"


def test_con_14_constructs_need_tasks() -> None:
    src = 'edition 0\nneeds console\n\nto main, needs console:\n    together:\n        show "a"\n        show "b"\n'
    assert run_source(src).code == "SAY-E0601"


def test_con_15_child_captures_changeable() -> None:
    assert prog("let n be 1, changeable\ntogether:\n    show n\n    show 2").code == "SAY-E0603"


def test_con_16_bare_let_child() -> None:
    assert prog("together:\n    let x be 1\n    show 2").code == "SAY-E0604"


def test_con_17_unbuffered_rendezvous_order() -> None:
    lib = LIB + (
        "to producer ch, needs console and tasks:\n    for each i in [1, 2]:\n"
        '        show "send {i}"\n        send i into ch\n        show "sent {i}"\n    close ch\n'
    )
    body = (
        'let ch be new-channel()\ntogether:\n    producer(ch)\n    for each x received from ch:\n        show "got {x}"'
    )
    assert prog(body, header=lib).out == ["send 1", "got 1", "sent 1", "send 2", "got 2", "sent 2"]


def test_con_18_buffered_channel() -> None:
    body = "let ch be new-channel with capacity 2\nsend 1 into ch\nsend 2 into ch\nshow receive from ch\nshow receive from ch"
    assert prog(body).out == ["1", "2"]


def test_con_19_receive_after_close_and_drain() -> None:
    body = "let ch be new-channel with capacity 1\nsend 1 into ch\nclose ch\nshow receive from ch\nshow receive from ch"
    assert prog(body).out == ["1", "nothing"]


def test_con_20_closed_channel_panics() -> None:
    assert prog("let ch be new-channel with capacity 1\nclose ch\nsend 1 into ch").code == "SAY-E0610"
    assert prog("let ch be new-channel()\nclose ch\nclose ch").code == "SAY-E0611"


def test_con_21_deadlock() -> None:
    r = prog("let ch be new-channel()\nsend 1 into ch")
    assert (r.code, r.exit) == ("SAY-E0612", 70) and "send on a channel" in r.what


def test_con_22_shuffle_tasks_deterministic() -> None:
    from sayform.evaluator import program
    from sayform.parser import parse

    body = "together:\n" + "".join(f'    show "{c}"\n' for c in "abcdef")
    src = "edition 0\nneeds console and tasks\n\nto main, needs console and tasks:\n" + "".join(
        "    " + ln + "\n" for ln in body.splitlines()
    )
    outs = []
    for seed in (7, 7, 8):
        got: list[str] = []
        program(parse(src), lambda t, end="\n", sink=got: sink.append(t), shuffle=seed)
        outs.append(got)
    assert outs[0] == outs[1] and sorted(outs[0]) == list("abcdef")


def test_each_at_the_same_time_input_order() -> None:
    r = prog("show (each n in [3, 1, 2] at the same time, delayed(n, 1s))")
    assert r.out == ["[3, 1, 2]"]
