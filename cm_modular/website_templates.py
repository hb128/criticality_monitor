"""
HTML templates and rendering for Criticality Monitor websites.
"""
from __future__ import annotations

import html
import json


def render_enhanced_html(
    city: str,
    recent_data: dict,
    leaderboard_data: dict,
    current_stats: dict,
    plot_data: dict,
) -> str:
    """Render the enhanced HTML page."""
    
    data_json = json.dumps({
        'recent': recent_data,
        'leaderboard': leaderboard_data,
        'stats': current_stats,
        'plot': plot_data,
    }).replace("</", "<\\/")
    
    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>	Criticality monitor {html.escape(city)}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.1.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; 
            line-height: 1.6; 
            color: #2c3e50;
            background: #f8f9fa;
            min-height: 100vh;
        }}
        
        .container {{ 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 0 15px;
        }}
                
        /* Main content */
        .main-content {{ 
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 10px;
            margin-bottom: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        /* 2x2 Grid Layout for iPad Landscape */
        .content-grid {{ 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            grid-template-rows: 42vh 42vh;
            gap: 10px; 
            min-height: 84vh; /* Stretch to fill more vertical space */
        }}
        
        .grid-item {{
            background: rgba(248, 249, 250, 0.8);
            border-radius: 12px;
            padding: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden; /* Prevent content from spilling out */
            display: flex;
            flex-direction: column;
        }}
        
        /* Chart section - Top Left */
        .chart-section {{ 
            
        }}
        
        .chart-section h2 {{ 
            margin-bottom: 8px; 
            color: #2c3e50;
            font-size: 1.0rem;
        }}
        
        #chart {{ 
            width: 100%; 
            height: 100%;
            min-height: 220px;
            border-radius: 8px;
            flex: 1; /* Take remaining space */
        }}
        
        /* Leaderboard - Top Right */
        .leaderboard {{
            
        }}
        
        .leaderboard h2 {{ 
            margin-bottom: 8px; 
            color: #2c3e50;
            font-size: 1.0rem;
            flex-shrink: 0; /* Don't shrink the header */
        }}
        
        #leaderboard-list {{
            flex: 1; /* Take remaining space */
            overflow-y: auto;
            max-height: 100%;
        }}
        
        .leaderboard-item {{ 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            padding: 6px; 
            margin-bottom: 6px; 
            background: white; 
            border-radius: 6px;
            transition: transform 0.2s;
            font-size: 0.8rem;
        }}
        
        .leaderboard-item:hover {{ 
            transform: translateY(-1px); 
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
    .rank {{ font-weight: 700; font-size: 0.85rem; min-width: 20px; }}
        
    .distance {{ font-weight: 600; font-size: 0.8rem; }}
        
    .city-name {{ font-weight: 700; font-size: 0.75rem; text-transform: capitalize; }}
        
        .date {{ 
            font-size: 0.8rem; 
            color: #7f8c8d;
        }}
        
        /* Map section - Bottom Left */
        .map-section {{ 
            
        }}
        
        .map-section h2 {{ 
            margin-bottom: 8px; 
            color: #2c3e50;
            font-size: 1.0rem;
            flex-shrink: 0; /* Don't shrink the header */
        }}
        
        .map-container {{ 
            width: 100%; 
            flex: 1; /* Take all remaining space */
            border-radius: 8px; 
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            min-height: 200px;
        }}
        
        #latest-map {{ 
            width: 100%; 
            height: 100%; 
            border: none;
        }}
        
        /* Stats section - Bottom Right */
        .stats-section {{
            
        }}
        
        .stats-section h2 {{ 
            margin-bottom: 8px; 
            color: #2c3e50;
            font-size: 1.0rem;
            flex-shrink: 0; /* Don't shrink the header */
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: 1fr 1fr;
            gap: 6px;
            flex: 1; /* Take remaining space */
            min-height: 160px;
        }}
        
        .stat-card {{
            background: white;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            display: flex;
            flex-direction: column;
            justify-content: center;
            min-height: 60px;
        }}
        
        .stat-card-value {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #e74c3c;
            margin-bottom: 3px;
            line-height: 1;
        }}
        
        .stat-card-label {{
            font-size: 1.0rem;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            line-height: 1;
        }}
        
        /* Responsive */
        @media (max-width: 768px) {{
            .container {{ padding: 0 15px; }}
            .stats-grid {{
                grid-template-columns: 1fr 1fr;
                min-height: 120px;
            }}
        }}
        
        @media (max-width: 768px) {{
            .hero h1 {{ 
                font-size: 2rem;
            }}
            
            .hero .current-stats {{ 
                gap: 20px;
            }}
            
            .container {{ 
                padding: 0 15px;
            }}
            
            .grid-item {{
                height: 40vh;
                min-height: 300px;
            }}
            
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            .stat-card-value {{
                font-size: 2.0rem;
            }}
        }}
        
        /* Animation */
        .main-content {{ 
            animation: fadeInUp 0.6s ease-out;
        }}
        
        @keyframes fadeInUp {{
            from {{ 
                opacity: 0; 
                transform: translateY(30px);
            }}
            to {{ 
                opacity: 1; 
                transform: translateY(0);
            }}
        }}
    </style>
</head>
<body>
    <div class="container" style="margin-top:8px;">
        <!-- Title removed intentionally -->

        <!-- Main Content - 2x2 Grid -->
        <section class="main-content">
            <div class="content-grid">
                <!-- Top Left: Chart Section -->
                <div class="chart-section grid-item">
                    <div id="chart"></div>
                </div>

                
                <!-- Top Right: Stats Section -->
                <div class="stats-section grid-item">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-card-value" id="total-distance">{current_stats['latest_length']:.0f}m</div>
                            <div class="stat-card-label">Current Length</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-card-value" id="number-points">{current_stats['n_filtered']:d}</div>
                            <div class="stat-card-label">Mass Trackers</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-card-value">{current_stats['max_length']:.0f}m</div>
                            <div class="stat-card-label">Max Length</div>
                        </div>
                    </div>
                </div>

                <!-- Bottom Left: Map Section -->
                <div class="map-section grid-item">
                    <h2>Latest Route</h2>
                    <div class="map-container">
                        <iframe id="latest-map" src="" title="Latest Criticality Monitor Route"></iframe>
                    </div>
                </div>
                
                <!-- Bottom Right: Leaderboard -->
                <div class="leaderboard grid-item">
                    <h2>Leaderboard</h2>
                    <div id="leaderboard-list"></div>
                </div>
                
            </div>
        </section>
    </div>

    <script id="payload" type="application/json">{data_json}</script>
    <script>
        let DATA = null;
        try {{
            const el = document.getElementById('payload');
            DATA = JSON.parse(el.textContent);
        }} catch (e) {{
            console.error('Failed to parse embedded data', e);
            DATA = {{ plot: {{ x: [], y: [], links: [] }}, leaderboard: {{ records: [] }} }};
        }}

        // Initialize chart
        if (DATA.plot && DATA.plot.x.length > 0) {{
            // Group data by city
            const cityData = {{}};
            const colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e'];
            let colorIndex = 0;
            
            // Group points by city
            for (let i = 0; i < DATA.plot.x.length; i++) {{
                const city = DATA.plot.cities ? DATA.plot.cities[i] : 'Unknown';
                if (!cityData[city]) {{
                    cityData[city] = {{
                        x: [],
                        y: [],
                        links: [],
                        color: colors[colorIndex % colors.length]
                    }};
                    colorIndex++;
                }}
                cityData[city].x.push(DATA.plot.x[i]);
                cityData[city].y.push(DATA.plot.y[i]);
                if (DATA.plot.links && DATA.plot.links[i]) {{
                    cityData[city].links.push(DATA.plot.links[i]);
                }} else {{
                    cityData[city].links.push('');
                }}
            }}

            // Create traces for each city
            const traces = Object.keys(cityData).map(city => ({{
                x: cityData[city].x,
                y: cityData[city].y,
                type: 'scattergl',
                mode: 'lines+markers',
                name: city,
                line: {{ color: cityData[city].color, width: 3 }},
                marker: {{ color: cityData[city].color, size: 6 }},
                hovertemplate: '<b>%{{y:.0f}}m</b><br>%{{x}}<br>' + city + '<extra></extra>',
                customdata: cityData[city].links
            }}));

            // Expose city -> color mapping globally for leaderboard styling
            window.CITY_COLORS = {{}};
            Object.keys(cityData).forEach(c => {{ window.CITY_COLORS[c] = cityData[c].color; }});

            const layout = {{
                xaxis: {{ title: 'Date' }},
                yaxis: {{ title: 'Distance (meters)' }},
                margin: {{ l: 60, r: 20, t: 40, b: 60 }},
                plot_bgcolor: 'rgba(0,0,0,0)',
                paper_bgcolor: 'rgba(0,0,0,0)',
                font: {{ family: 'Segoe UI, system-ui, sans-serif' }},
                showlegend: true,
                legend: {{
                    x: 0,
                    xanchor: 'left',
                    y: 1,
                    yanchor: 'top',
                    bgcolor: 'rgba(255,255,255,0.8)',
                    bordercolor: 'rgba(0,0,0,0.1)',
                    borderwidth: 1
                }}
            }};

            Plotly.newPlot('chart', traces, layout, {{ responsive: true }});

            // Handle chart clicks
            document.getElementById('chart').on('plotly_click', function(data) {{
                // Each point's customdata is already the full map URL string
                const mapUrl = data.points[0].customdata;
                if (mapUrl) {{
                    window.open(mapUrl, '_blank');
                }}
            }});
            
            // Handle chart hover - show map of hovered datapoint
            document.getElementById('chart').on('plotly_hover', function(data) {{
                const mapUrl = data.points[0].customdata;
                const mapFrame = document.getElementById('latest-map');
                if (mapUrl && mapFrame) {{
                    mapFrame.src = mapUrl;
                }}
            }});
        }}

        // Build leaderboard
        const leaderboardContainer = document.getElementById('leaderboard-list');
        let maxDistance = 0;
        if (DATA.leaderboard && DATA.leaderboard.records) {{
            DATA.leaderboard.records.forEach(record => {{
                const item = document.createElement('div');
                item.className = 'leaderboard-item';
                const cityColor = (window.CITY_COLORS && window.CITY_COLORS[record.city]) || '#3498db';
                
                // City leaderboard
                item.innerHTML = `
                    <div class="rank" style="color:${{cityColor}}">#${{record.rank}}</div>
                    <div class="city-name" style="color:${{cityColor}}">${{record.city}}</div>
                    <div class="distance" style="color:${{cityColor}}">${{record.length_m.toFixed(0)}}m</div>
                `;
                leaderboardContainer.appendChild(item);
                
                // Track max distance
                if (record.length_m > maxDistance) {{
                    maxDistance = record.length_m;
                }}
            }});
        }}
        
        // Update max distance display
        const maxDistanceElement = document.getElementById('max-distance');
        if (maxDistanceElement) {{
            maxDistanceElement.textContent = maxDistance.toFixed(0) + 'm';
        }}

        // Load latest map
        const mapFrame = document.getElementById('latest-map');
        if (DATA.plot && DATA.plot.links && DATA.plot.links.length > 0) {{
            const latestMapUrl = DATA.plot.links[DATA.plot.links.length - 1];
            if (latestMapUrl) {{
                mapFrame.src = latestMapUrl;
            }}
        }}
    </script>
</body>
</html>"""
