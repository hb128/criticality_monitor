"""
HTML templates and rendering for Critical Mass websites.
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
    <title>Critical Mass {html.escape(city)}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.1.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; 
            line-height: 1.6; 
            color: #2c3e50;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        
        .container {{ 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 0 20px;
        }}
        
        /* Header */
        .hero {{ 
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 20px 0;
            text-align: center;
            border-radius: 0 0 20px 20px;
            margin-bottom: 20px;
        }}
        
        .hero h1 {{ 
            font-size: 2rem; 
            font-weight: 700; 
            color: #2c3e50;
            margin-bottom: 0;
        }}
        
        .hero .subtitle {{ 
            font-size: 1.2rem; 
            color: #7f8c8d;
            margin-bottom: 20px;
        }}
        
        .hero .current-stats {{ 
            display: flex; 
            justify-content: center; 
            gap: 40px; 
            flex-wrap: wrap;
        }}
        
        .stat-item {{ 
            text-align: center;
        }}
        
        .stat-value {{ 
            font-size: 2rem; 
            font-weight: 700; 
            color: #e74c3c;
        }}
        
        .stat-label {{ 
            font-size: 0.9rem; 
            color: #7f8c8d; 
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        /* Main content */
        .main-content {{ 
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 15px;
            margin-bottom: 20px;
        }}
        
        /* 2x2 Grid Layout for iPad Landscape */
        .content-grid {{ 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            grid-template-rows: 35vh 35vh;
            gap: 15px; 
            min-height: 70vh; /* Reduced for iPad 3 */
        }}
        
        .grid-item {{
            background: rgba(248, 249, 250, 0.8);
            border-radius: 15px;
            padding: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden; /* Prevent content from spilling out */
            display: flex;
            flex-direction: column;
        }}
        
        /* Chart section - Top Left */
        .chart-section {{ 
            
        }}
        
        .chart-section h2 {{ 
            margin-bottom: 10px; 
            color: #2c3e50;
            font-size: 1.1rem;
        }}
        
        #chart {{ 
            width: 100%; 
            height: 100%;
            min-height: 200px;
            border-radius: 10px;
            flex: 1; /* Take remaining space */
        }}
        
        /* Leaderboard - Top Right */
        .leaderboard {{
            
        }}
        
        .leaderboard h2 {{ 
            margin-bottom: 10px; 
            color: #2c3e50;
            font-size: 1.1rem;
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
        
        .rank {{ 
            font-weight: 700; 
            font-size: 0.85rem; 
            color: #e74c3c;
            min-width: 20px;
        }}
        
        .distance {{ 
            font-weight: 600; 
            color: #2c3e50;
            font-size: 0.8rem;
        }}
        
        .date {{ 
            font-size: 0.8rem; 
            color: #7f8c8d;
        }}
        
        /* Map section - Bottom Left */
        .map-section {{ 
            
        }}
        
        .map-section h2 {{ 
            margin-bottom: 10px; 
            color: #2c3e50;
            font-size: 1.1rem;
            flex-shrink: 0; /* Don't shrink the header */
        }}
        
        .map-container {{ 
            width: 100%; 
            flex: 1; /* Take all remaining space */
            border-radius: 10px; 
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            min-height: 180px;
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
            margin-bottom: 10px; 
            color: #2c3e50;
            font-size: 1.1rem;
            flex-shrink: 0; /* Don't shrink the header */
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: 1fr 1fr;
            gap: 8px;
            flex: 1; /* Take remaining space */
            min-height: 150px;
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
            font-size: 1.3rem;
            font-weight: 700;
            color: #e74c3c;
            margin-bottom: 3px;
            line-height: 1;
        }}
        
        .stat-card-label {{
            font-size: 0.7rem;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            line-height: 1;
        }}
        
        /* Responsive */
        @media (max-width: 1023px) {{
            .content-grid {{ 
                grid-template-columns: 1fr; 
                grid-template-rows: auto auto auto auto;
                min-height: auto;
            }}
            
            .grid-item {{
                height: 40vh;
                min-height: 300px;
            }}
            
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
                font-size: 1.5rem;
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
    <div class="container">
        <!-- Hero Section -->
        <section class="hero">
            <h1>Critical Mass {html.escape(city)}</h1>
        </section>

        <!-- Main Content - 2x2 Grid -->
        <section class="main-content">
            <div class="content-grid">
                <!-- Top Left: Chart Section -->
                <div class="chart-section grid-item">
                    <h2>📈 Distance Over Time</h2>
                    <div id="chart"></div>
                </div>

                <!-- Top Right: Leaderboard -->
                <div class="leaderboard grid-item">
                    <h2>🏆 Longest Routes</h2>
                    <div id="leaderboard-list"></div>
                </div>
                
                <!-- Bottom Left: Map Section -->
                <div class="map-section grid-item">
                    <h2>🗺️ Latest Route</h2>
                    <div class="map-container">
                        <iframe id="latest-map" src="" title="Latest Critical Mass Route"></iframe>
                    </div>
                </div>
                
                <!-- Bottom Right: Stats Section -->
                <div class="stats-section grid-item">
                    <h2>📊 Statistics</h2>
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
                        <div class="stat-card">
                            <div class="stat-card-value">{current_stats['latest_date']}</div>
                            <div class="stat-card-label">Latest datapoint</div>
                        </div>
                    </div>
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
            const trace = {{
                x: DATA.plot.x,
                y: DATA.plot.y,
                type: 'scattergl',
                mode: 'lines+markers',
                name: 'Route Length',
                line: {{ color: '#e74c3c', width: 3 }},
                marker: {{ color: '#e74c3c', size: 6 }},
                hovertemplate: '<b>%{{y:.0f}}m</b><br>%{{x}}<extra></extra>'
            }};

            const layout = {{
                xaxis: {{ title: 'Date' }},
                yaxis: {{ title: 'Distance (meters)' }},
                margin: {{ l: 60, r: 20, t: 20, b: 60 }},
                plot_bgcolor: 'rgba(0,0,0,0)',
                paper_bgcolor: 'rgba(0,0,0,0)',
                font: {{ family: 'Segoe UI, system-ui, sans-serif' }}
            }};

            Plotly.newPlot('chart', [trace], layout, {{ responsive: true }});

            // Handle chart clicks
            document.getElementById('chart').on('plotly_click', function(data) {{
                const pointIndex = data.points[0].pointIndex;
                const mapUrl = DATA.plot.links[pointIndex];
                if (mapUrl) {{
                    window.open(mapUrl, '_blank');
                }}
            }});
            
            // Handle chart hover - show map of hovered datapoint
            document.getElementById('chart').on('plotly_hover', function(data) {{
                const pointIndex = data.points[0].pointIndex;
                const mapUrl = DATA.plot.links[pointIndex];
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
                item.innerHTML = `
                    <div class="rank">#${{record.rank}}</div>
                    <div>
                        <div class="distance">${{record.length_m.toFixed(0)}}m</div>
                        <div class="date">${{record.date}}</div>
                    </div>
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
