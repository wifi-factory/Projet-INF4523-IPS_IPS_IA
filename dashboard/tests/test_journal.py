from __future__ import annotations

import pandas as pd


def test_render_timeline_outputs_compact_escaped_html(monkeypatch) -> None:
    import dashboard.components.journal as journal

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        journal.st,
        "markdown",
        lambda body, unsafe_allow_html=False: captured.update(
            {"body": body, "unsafe_allow_html": unsafe_allow_html}
        ),
    )

    df = pd.DataFrame(
        [
            {
                "Heure": "22:27:56",
                "Niveau": "ERROR",
                "Type": "Runtime",
                "Message": "<unexpected> & stopped",
            }
        ]
    )

    journal.render_timeline(df)

    body = str(captured["body"])
    assert captured["unsafe_allow_html"] is True
    assert "<div class='timeline-stream'>" in body
    assert "&lt;unexpected&gt; &amp; stopped" in body
    assert "\n            <div class=" not in body
