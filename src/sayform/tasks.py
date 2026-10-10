"""Structured concurrency (spec/11-concurrency.md): the deterministic single-threaded scheduler,
task groups for `together` / `all of` / `first of` / `within` / `map-concurrent`, cooperative
cancellation at checkpoints, D6 error aggregation, and channels."""

from __future__ import annotations

import heapq
import random
import time
from collections import deque
from collections.abc import Callable, Generator
from decimal import Decimal
from typing import Any

from .diagnostics import SayError, panic
from .values import MapV, Problem, Sym

Gen = Generator[Any, Any, Any]
PARK = object()  # yielded by a task that waits until something wakes it


class Cancelled(BaseException):
    """Cancellation unwinding; not a problem value, so `try` / `or else` cannot observe it."""


class Task:
    def __init__(self, gen: Gen, parent: Task | None, group: Group | None, seq: int, label: str) -> None:
        self.gen, self.parent, self.group, self.seq, self.label = gen, parent, group, seq, label
        self.children: list[Task] = []
        self.cancelled = self.unwinding = self.done = self.fresh = False
        self.inbox: Any = None
        self.value: Any = None
        self.error: BaseException | None = None
        self.waits = ""
        self.waitno = 0


class Group:
    """The children of one construct; wakes its parent once every child has finished."""

    def __init__(self, sched: Scheduler, mode: str, parent: Task, limit: int | None = None) -> None:
        self.sched, self.mode, self.parent, self.limit = sched, mode, parent, limit
        self.tasks: list[Task] = []
        self.pending: deque[tuple[Gen, str]] = deque()
        self.running = 0
        self.failing = False
        self.winner: Task | None = None

    def add(self, gen: Gen, label: str) -> None:
        if self.limit is not None and self.running >= self.limit:
            self.pending.append((gen, label))
            return
        self.running += 1
        self.tasks.append(self.sched.spawn(gen, self.parent, self, label))

    def child_done(self, t: Task) -> None:
        self.running -= 1
        failed = t.error is not None or (isinstance(t.value, tuple) and t.value[0] == "fail")
        if self.mode == "first" and not failed and t.value is not None and self.winner is None:
            self.winner = t
            self.stop()
        elif failed and not self.failing and (self.mode in ("all", "together") or t.error is not None):
            self.failing = True
            self.stop()
        while self.pending and (self.limit is None or self.running < self.limit):
            self.add(*self.pending.popleft())
        if self.running == 0 and not self.pending:
            self.sched.wake(self.parent, fresh=False)

    def stop(self) -> None:
        self.pending.clear()
        for x in self.tasks:
            self.sched.cancel(x)

    def join(self) -> Gen:
        if self.running or self.pending:
            yield self.sched.park("its children (join)")

    def outcome(self, construct: str, line: int) -> Any:
        """Panics re-raise; one problem passes unwrapped, two or more become `several` (D6)."""
        for i, t in enumerate(self.tasks):
            if isinstance(t.error, SayError):
                t.error.diag.trace.append(f"while running child ({t.label or i + 1}) of `{construct}` at L{line}")
                raise t.error
            if t.error is not None:
                raise t.error
        if self.winner is not None:
            return self.winner.value[1]
        problems = [t.value[1] for t in self.tasks if isinstance(t.value, tuple) and t.value[0] == "fail"]
        if problems or self.mode == "first":
            if len(problems) == 1:
                return Failure(problems[0])
            return Failure(
                Problem(Sym("several"), f"{len(problems)} children failed", MapV({Sym("problems"): tuple(problems)}))
            )
        return [t.value[1] for t in self.tasks]


class Failure:
    def __init__(self, problem: Problem) -> None:
        self.problem = problem


class Scheduler:
    """FIFO ready deque, min-heap of timers keyed by (deadline, sequence), per-channel FIFO wait
    queues; children start in source order and run round-robin between checkpoints."""

    def __init__(self, real: bool = False, seed: int | None = None) -> None:
        self.ready: deque[Task] = deque()
        self.timers: list[tuple[Decimal, int, Callable[[], bool], Callable[[], None]]] = []
        self.blocked: dict[Task, None] = {}
        self.now = Decimal(0)
        self.seq = 0
        self.real = real
        self.rng = random.Random(seed) if seed is not None else None
        self.current: Task | None = None

    def spawn(self, gen: Gen, parent: Task | None, group: Group | None = None, label: str = "") -> Task:
        self.seq += 1
        t = Task(gen, parent, group, self.seq, label)
        if parent is not None:
            parent.children.append(t)
        self.ready.append(t)
        return t

    def park(self, reason: str) -> object:
        assert self.current is not None
        self.current.waits = reason
        self.current.waitno += 1
        return PARK

    def wake(self, t: Task, value: Any = None, fresh: bool = True) -> None:
        """Resume a parked task. A `fresh` wake completed its wait, so a pending cancellation
        takes effect at its next checkpoint rather than this one."""
        if t in self.blocked:
            del self.blocked[t]
            t.inbox, t.waits, t.fresh = value, "", fresh
            self.ready.append(t)

    def cancel(self, t: Task) -> None:
        if t.done or t.cancelled:
            return
        t.cancelled = True
        for c in t.children:
            self.cancel(c)
        if t.waits and "join" not in t.waits:
            self.wake(t, fresh=False)

    def timer(self, seconds: Decimal, alive: Callable[[], bool], action: Callable[[], None]) -> None:
        self.seq += 1
        heapq.heappush(self.timers, (self.now + seconds, self.seq, alive, action))

    def loop(self, gen: Gen) -> Any:
        main = self.spawn(gen, None)
        while not main.done:
            if self.ready:
                i = self.rng.randrange(len(self.ready)) if self.rng else 0
                t = self.ready[i]
                del self.ready[i]
                self.step(t)
            elif self.timers:
                deadline, _, alive, action = heapq.heappop(self.timers)
                if not alive():
                    continue
                if self.real and deadline > self.now:
                    time.sleep(float(deadline - self.now))
                self.now = max(self.now, deadline)
                action()
                while self.timers and self.timers[0][0] <= self.now:
                    _, _, alive, action = heapq.heappop(self.timers)
                    if alive():
                        action()
            else:
                waits = "; ".join(f"task {t.seq} waits on {t.waits}" for t in self.blocked)
                raise panic("E0612", list=waits or "the main task")
        if main.error is not None:
            raise main.error
        return main.value

    def step(self, t: Task) -> None:
        self.current = t
        try:
            if t.cancelled and not t.unwinding and not t.fresh:
                t.unwinding = True
                req = t.gen.throw(Cancelled())
            else:
                v, t.inbox, t.fresh = t.inbox, None, False
                req = t.gen.send(v)
        except StopIteration as s:
            return self.finish(t, s.value, None)
        except Cancelled:
            return self.finish(t, None, None)
        except BaseException as e:  # noqa: BLE001 - every failure is collected by the group
            if t.group is None and not isinstance(e, Exception):
                raise
            return self.finish(t, None, e)
        if req is PARK:
            self.blocked[t] = None
        else:
            self.ready.append(t)

    def finish(self, t: Task, value: Any, error: BaseException | None) -> None:
        t.done, t.value, t.error = True, value, error
        self.blocked.pop(t, None)
        if t.group is not None:
            t.group.child_done(t)


def seconds(q: Any) -> Decimal | None:
    from .values import Quantity

    if not isinstance(q, Quantity):
        return None
    return Decimal(q.ms) / 1000


# ---- channels -------------------------------------------------------------------------------
class Channel:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.buf: deque[Any] = deque()
        self.closed = False
        self.sendq: deque[tuple[Task, int, Any]] = deque()
        self.recvq: deque[tuple[Task, int]] = deque()

    def get_field(self, name: str) -> Any:
        if name in ("sender", "receiver"):
            return End(self, name)
        return Problem(Sym("no-such-field"), f"a channel has no field `{name}`")


class End:
    def __init__(self, ch: Channel, way: str) -> None:
        self.ch, self.way = ch, way


class Received:
    def __init__(self, ch: Channel) -> None:
        self.ch = ch


def live(s: Scheduler, t: Task, n: int) -> bool:
    return t in s.blocked and t.waitno == n


def send(s: Scheduler, ch: Channel, v: Any) -> Gen:
    if ch.closed:
        raise panic("E0610")
    while ch.recvq:
        r, n = ch.recvq.popleft()
        if live(s, r, n):
            s.wake(r, ("value", v))
            yield
            return None
    if len(ch.buf) < ch.capacity:
        ch.buf.append(v)
        yield
        return None
    me = s.current
    assert me is not None
    req = s.park("send on a channel")
    ch.sendq.append((me, me.waitno, v))
    if (yield req) == "closed":
        raise panic("E0610")
    return None


def receive(s: Scheduler, ch: Channel) -> Gen:
    """Returns ("value", v), or None once the channel is closed and drained."""
    if ch.buf:
        v = ch.buf.popleft()
        while ch.sendq:
            w, n, sv = ch.sendq.popleft()
            if live(s, w, n):
                ch.buf.append(sv)
                s.wake(w)
                break
        yield
        return ("value", v)
    while ch.sendq:
        w, n, sv = ch.sendq.popleft()
        if live(s, w, n):
            s.wake(w)
            yield
            return ("value", sv)
    if ch.closed:
        yield
        return None
    me = s.current
    assert me is not None
    req = s.park("receive from a channel")
    ch.recvq.append((me, me.waitno))
    return (yield req)


def close(s: Scheduler, ch: Channel) -> None:
    if ch.closed:
        raise panic("E0611")
    ch.closed = True
    for r, n in ch.recvq:
        if live(s, r, n):
            s.wake(r, None)
    for w, n, _ in ch.sendq:
        if live(s, w, n):
            s.wake(w, "closed")
    ch.recvq.clear()
    ch.sendq.clear()
