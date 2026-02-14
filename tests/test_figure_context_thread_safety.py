from __future__ import annotations

import queue
import threading

from gu_toolkit import Figure
from gu_toolkit.figure_context import _use_figure, current_figure


def test_current_figure_is_isolated_per_thread() -> None:
    fig_main = Figure()
    fig_thread = Figure()
    q: queue.Queue[object] = queue.Queue()

    def _worker() -> None:
        with _use_figure(fig_thread):
            q.put(current_figure())

    with _use_figure(fig_main):
        t = threading.Thread(target=_worker)
        t.start()
        t.join()
        worker_current = q.get(timeout=1)
        assert worker_current is fig_thread
        assert current_figure() is fig_main
