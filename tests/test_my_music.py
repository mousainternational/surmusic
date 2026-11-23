def test_my_music_page_is_open_indexable_and_in_the_sitemap(client):
    r = client.get("/my-music")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Free music" in html and 'id="mm-auto"' in html
    assert "noindex" not in html.split("</head>")[0]
    assert "<video" not in html and html.count('id="pl-audio"') == 1       # one player only: the radio player bar
    assert "FAQPage" in html and "BreadcrumbList" in html
    assert "/my-music" in client.get("/sitemap.xml").get_data(as_text=True)


def test_my_music_is_linked_from_every_page_and_the_script_is_served(client):
    about = client.get("/about").get_data(as_text=True)
    assert 'href="/my-music"' in about
    assert 'id="mm-open"' in about and 'id="mm-panel"' in about and 'id="mm-files"' in about and 'id="mm-c-shuffle"' in about and 'id="mm-c-repeat"' in about and 'id="mm-c-speed"' in about and 'for="mm-files"' in about and 'id="mm-add"' in about and 'for="mm-files"' in about     # the whole feature sits in the player bar of every page
    js = client.get("/static/js/my-music.js")
    assert js.status_code == 200 and b"createObjectURL" in js.data
    assert b"fetch(" not in js.data and b"XMLHttpRequest" not in js.data      # files never leave the device
    pj = client.get("/static/js/player.js").data
    assert b"window.SurPlayer" in pj and b"station.local" in pj               # own files play in the radio player bar
