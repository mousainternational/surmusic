import re


def test_long_admin_lists_scroll_inside_their_card(client):
    css = client.get("/static/css/site.css").get_data(as_text=True)
    rule = " ".join(re.findall(r"\.bars-list \{[^}]*\}", css))
    assert "max-height" in rule and "overflow-y: auto" in rule


def test_statistics_copy_is_saved_at_least_every_hour_without_a_fast_store():
    src = open("app/persist.py", encoding="utf-8").read()
    assert '"30" if _kv_on() else "60"' in src
