from django_dev_helpers import live_reload


def test_boot_id_is_stable_nonempty():
    assert isinstance(live_reload.BOOT_ID, str)
    assert live_reload.BOOT_ID
    assert live_reload.BOOT_ID == live_reload.BOOT_ID


def test_registry_tracks_connections():
    live_reload._reset()
    assert live_reload.count() == 0
    a = live_reload.register()
    b = live_reload.register()
    assert live_reload.count() == 2
    live_reload.unregister(a)
    assert live_reload.count() == 1
    live_reload.unregister(b)
    assert live_reload.count() == 0


def test_unregister_unknown_is_noop():
    live_reload._reset()
    live_reload.unregister(999)
    assert live_reload.count() == 0


def test_inject_inserts_script_before_body():
    html = "<html><body>hi</body></html>"
    out = live_reload.inject(html)
    assert "EventSource" in out
    assert out.index("EventSource") < out.rindex("</body>")


def test_inject_noop_without_body():
    html = "<p>no body tag</p>"
    assert live_reload.inject(html) == html


def test_inject_uses_last_body_case_insensitive():
    html = "<BODY>x</BODY>"
    out = live_reload.inject(html)
    assert "EventSource" in out
    assert out.rindex("EventSource") < out.rindex("</BODY>")
