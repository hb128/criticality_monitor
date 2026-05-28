from cm_modular.website_templates import render_enhanced_html

MINIMAL_LEADERBOARD = {
    "records": [{"rank": 1, "city": "Hamburg", "length_m": 12000.0, "date": "01.06.2024", "participants": 80}]
}
MINIMAL_STATS = {
    "n_filtered": 80,
    "latest_length": 12000.0,
    "latest_date": "01.06.2024 - 20:00",
    "max_length": 12000.0,
}
MINIMAL_PLOT_DATA = {
    "x": ["2024-06-01T22:00:00+02:00"],
    "y": [12000.0],
    "links": ["hamburg/2024-06-01T20:00:00Z.html"],
    "cities": ["Hamburg"],
}

def test_render_enhanced_html_returns_valid_html():
    html = render_enhanced_html(
        city="hamburg",
        leaderboard_data=MINIMAL_LEADERBOARD,
        current_stats=MINIMAL_STATS,
        plot_data=MINIMAL_PLOT_DATA,
    )
    assert html.startswith("<!DOCTYPE html")
    assert "application/json" in html
    assert "scattergl" in html
    assert len(html) > 1000