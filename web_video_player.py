import http.server
import socketserver
import webbrowser
import json
import random
from pathlib import Path
from threading import Thread
import time

# HTML template for the video ad player
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hisar Bakery Video Ad Player</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            background: linear-gradient(45deg, #ff6b6b, #feca57);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .main-container {
            display: flex;
            gap: 30px;
            max-width: 1400px;
            width: 100%;
        }
        
        .ad-display {
            flex: 2;
            background: #0f3460;
            border-radius: 20px;
            padding: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        
        .ad-image-container {
            width: 100%;
            height: 600px;
            background: #1a1a2e;
            border-radius: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            position: relative;
        }
        
        .ad-image {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            border-radius: 10px;
        }
        
        .placeholder {
            text-align: center;
            color: #666;
        }
        
        .placeholder-icon {
            font-size: 4em;
            margin-bottom: 20px;
        }
        
        .info-panel {
            flex: 1;
            background: #16213e;
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            height: fit-content;
        }
        
        .info-panel h2 {
            color: #e94560;
            margin-bottom: 20px;
            font-size: 1.5em;
            border-bottom: 2px solid #e94560;
            padding-bottom: 10px;
        }
        
        .info-item {
            margin-bottom: 15px;
            padding: 10px;
            background: #0f3460;
            border-radius: 10px;
        }
        
        .info-label {
            font-size: 0.9em;
            color: #aaa;
            margin-bottom: 5px;
        }
        
        .info-value {
            font-size: 1.1em;
            font-weight: bold;
            color: #fff;
        }
        
        .controls {
            margin-top: 30px;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            justify-content: center;
        }
        
        .btn {
            padding: 15px 30px;
            font-size: 1.1em;
            font-weight: bold;
            border: none;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .btn-primary {
            background: linear-gradient(45deg, #e94560, #ff6b6b);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(233, 69, 96, 0.4);
        }
        
        .btn-secondary {
            background: linear-gradient(45deg, #0f3460, #16213e);
            color: white;
            border: 2px solid #e94560;
        }
        
        .btn-secondary:hover {
            background: #e94560;
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .speed-control {
            display: flex;
            align-items: center;
            gap: 15px;
            background: #0f3460;
            padding: 15px 25px;
            border-radius: 50px;
        }
        
        .speed-control label {
            font-weight: bold;
        }
        
        .speed-slider {
            width: 150px;
            height: 6px;
            -webkit-appearance: none;
            background: #1a1a2e;
            border-radius: 3px;
            outline: none;
        }
        
        .speed-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            background: #e94560;
            border-radius: 50%;
            cursor: pointer;
        }
        
        .stats {
            margin-top: 20px;
            text-align: center;
            padding: 15px;
            background: #0f3460;
            border-radius: 15px;
        }
        
        .stats h3 {
            color: #e94560;
            margin-bottom: 10px;
        }
        
        .status-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #0f3460;
            padding: 15px;
            text-align: center;
            font-size: 0.9em;
        }
        
        .category-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .cat-sweets { background: #ff6b6b; }
        .cat-cakes { background: #4ecdc4; }
        .cat-bread { background: #d4a373; }
        .cat-namkeen { background: #f4a261; }
        .cat-custom { background: #2a9d8f; }
        
        @media (max-width: 900px) {
            .main-container {
                flex-direction: column;
            }
            .ad-image-container {
                height: 400px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧁 Hisar Bakery Video Ad Player</h1>
        <p>Personalized Advertisement Display System</p>
    </div>
    
    <div class="main-container">
        <div class="ad-display">
            <div class="ad-image-container" id="adContainer">
                <div class="placeholder">
                    <div class="placeholder-icon">🎬</div>
                    <h2>Welcome to Video Ad Player</h2>
                    <p>Click "Random Ad" to start or "Auto Play" for slideshow</p>
                </div>
            </div>
        </div>
        
        <div class="info-panel">
            <h2>Ad Information</h2>
            
            <div class="info-item">
                <div class="info-label">Ad ID</div>
                <div class="info-value" id="adId">-</div>
            </div>
            
            <div class="info-item">
                <div class="info-label">District</div>
                <div class="info-value" id="district">-</div>
            </div>
            
            <div class="info-item">
                <div class="info-label">Category</div>
                <div class="info-value" id="category">-</div>
            </div>
            
            <div class="info-item">
                <div class="info-label">Target Audience</div>
                <div class="info-value" id="occupation">-</div>
            </div>
            
            <div class="info-item">
                <div class="info-label">Message</div>
                <div class="info-value" id="message" style="font-size: 0.9em; line-height: 1.4;">-</div>
            </div>
            
            <div class="stats">
                <h3>📊 Statistics</h3>
                <p>Total Ads: <strong id="totalAds">0</strong></p>
                <p>Played: <strong id="playedCount">0</strong></p>
            </div>
        </div>
    </div>
    
    <div class="controls">
        <button class="btn btn-primary" id="randomBtn" onclick="showRandomAd()">
            🎲 Random Ad
        </button>
        <button class="btn btn-secondary" id="playBtn" onclick="toggleAutoPlay()">
            ▶️ Auto Play
        </button>
        <button class="btn btn-secondary" id="stopBtn" onclick="stopAutoPlay()" disabled>
            ⏹️ Stop
        </button>
        
        <div class="speed-control">
            <label>Speed:</label>
            <input type="range" class="speed-slider" id="speedSlider" min="1" max="10" value="3" onchange="updateSpeed(this.value)">
            <span id="speedValue">3s</span>
        </div>
    </div>
    
    <div class="status-bar" id="statusBar">
        Ready to play ads • Loaded <span id="statusTotal">0</span> advertisements
    </div>

    <script>
        // Ad data will be injected here
        const ads = AD_DATA_PLACEHOLDER;
        
        let currentAd = null;
        let autoPlayInterval = null;
        let playedAds = new Set();
        let delay = 3000;
        
        // Category color mapping
        const categoryColors = {
            'Traditional Sweets': 'cat-sweets',
            'Cakes & Pastries': 'cat-cakes',
            'Bread & Buns': 'cat-bread',
            'Namkeen': 'cat-namkeen',
            'Custom Orders': 'cat-custom'
        };
        
        function updateStats() {
            document.getElementById('totalAds').textContent = ads.length;
            document.getElementById('playedCount').textContent = playedAds.size;
            document.getElementById('statusTotal').textContent = ads.length;
        }
        
        function showRandomAd() {
            if (ads.length === 0) {
                alert('No ads loaded! Please generate visual ads first.');
                return;
            }
            
            // Pick random ad
            const randomIndex = Math.floor(Math.random() * ads.length);
            currentAd = ads[randomIndex];
            
            // Update image
            const container = document.getElementById('adContainer');
            container.innerHTML = `<img src="${currentAd.image_path}" class="ad-image" alt="Ad ${currentAd.id}">`;
            
            // Update info
            document.getElementById('adId').textContent = currentAd.id;
            document.getElementById('district').textContent = currentAd.district;
            
            const category = currentAd.preference;
            const categoryEl = document.getElementById('category');
            categoryEl.innerHTML = `<span class="category-badge ${categoryColors[category] || 'cat-custom'}">${category}</span>`;
            
            document.getElementById('occupation').textContent = currentAd.meta.persona.occupation;
            document.getElementById('message').textContent = currentAd.meta.ad_text;
            
            // Update status
            document.getElementById('statusBar').innerHTML = 
                `Now Playing: <strong>${currentAd.id}</strong> | District: ${currentAd.district} | Type: ${category}`;
            
            // Track played
            playedAds.add(currentAd.id);
            updateStats();
        }
        
        function toggleAutoPlay() {
            if (autoPlayInterval) {
                stopAutoPlay();
                return;
            }
            
            document.getElementById('playBtn').innerHTML = '⏸️ Pause';
            document.getElementById('stopBtn').disabled = false;
            document.getElementById('randomBtn').disabled = true;
            
            showRandomAd();
            
            autoPlayInterval = setInterval(() => {
                showRandomAd();
            }, delay);
        }
        
        function stopAutoPlay() {
            if (autoPlayInterval) {
                clearInterval(autoPlayInterval);
                autoPlayInterval = null;
            }
            
            document.getElementById('playBtn').innerHTML = '▶️ Auto Play';
            document.getElementById('stopBtn').disabled = true;
            document.getElementById('randomBtn').disabled = false;
            document.getElementById('statusBar').textContent = 'Auto-play stopped. Ready.';
        }
        
        function updateSpeed(value) {
            delay = (11 - parseInt(value)) * 1000; // 1=10s, 10=1s
            document.getElementById('speedValue').textContent = (delay / 1000) + 's';
            
            // Restart if playing
            if (autoPlayInterval) {
                clearInterval(autoPlayInterval);
                autoPlayInterval = setInterval(() => {
                    showRandomAd();
                }, delay);
            }
        }
        
        // Initialize
        updateStats();
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space') {
                e.preventDefault();
                toggleAutoPlay();
            } else if (e.code === 'ArrowRight') {
                showRandomAd();
            } else if (e.code === 'Escape') {
                stopAutoPlay();
            }
        });
    </script>
</body>
</html>
"""

class AdPlayerServer:
    def __init__(self, port=8000):
        self.port = port
        self.ads = []
        self.load_ads()
        
    def load_ads(self):
        """Load ads from generated files"""
        visual_dir = Path('generated_visual_ads')
        
        if not visual_dir.exists():
            print("❌ Error: No visual ads found!")
            print("Please run: python visual_ad_generator.py")
            return
        
        meta_file = visual_dir / 'batch_metadata.json'
        if meta_file.exists():
            with open(meta_file, 'r') as f:
                batch_data = json.load(f)
            
            for item in batch_data:
                meta_file = visual_dir / f"ad_{item['id']}_meta.json"
                if meta_file.exists():
                    with open(meta_file, 'r') as f:
                        meta = json.load(f)
                    
                    square_path = visual_dir / item['files']['square']
                    if square_path.exists():
                        self.ads.append({
                            'id': item['id'],
                            'meta': meta,
                            'image_path': str(square_path).replace('\\', '/'),
                            'district': item['district'],
                            'preference': item['preference']
                        })
        
        print(f"✅ Loaded {len(self.ads)} ads")
    
    def generate_html(self):
        """Generate HTML with embedded ad data"""
        ads_json = json.dumps(self.ads)
        html = HTML_TEMPLATE.replace('AD_DATA_PLACEHOLDER', ads_json)
        return html
    
    def run(self):
        """Start the server and open browser"""
        if not self.ads:
            print("❌ No ads to display!")
            return
        
        # Create HTML file
        html_content = self.generate_html()
        with open('ad_player.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Simple HTTP server handler
        class Handler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(html_content.encode())
                elif self.path.startswith('/generated_visual_ads/'):
                    # Serve image files
                    try:
                        file_path = Path(self.path[1:])  # Remove leading /
                        if file_path.exists():
                            self.send_response(200)
                            self.send_header('Content-type', 'image/jpeg')
                            self.end_headers()
                            with open(file_path, 'rb') as f:
                                self.wfile.write(f.read())
                        else:
                            self.send_error(404)
                    except:
                        self.send_error(500)
                else:
                    super().do_GET()
        
        # Start server
        with socketserver.TCPServer(("", self.port), Handler) as httpd:
            url = f"http://localhost:{self.port}"
            print(f"\n🌐 Starting server at {url}")
            print("🎬 Opening browser...")
            
            # Open browser
            webbrowser.open(url)
            
            print("\n✅ Video Ad Player is running!")
            print("📱 Features:")
            print("   • Click 'Random Ad' to see individual ads")
            print("   • Click 'Auto Play' for slideshow (adjust speed)")
            print("   • Keyboard: Space=Play/Pause, Right Arrow=Next, Esc=Stop")
            print("\n⚠️  Press CTRL+C to stop the server")
            print("=" * 60)
            
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\n\n🛑 Server stopped")

def main():
    print("=" * 60)
    print("  🎬 HISAR BAKERY VIDEO AD PLAYER (Web Version)")
    print("=" * 60)
    print()
    print("This version runs in your web browser - more reliable!")
    print()
    
    player = AdPlayerServer(port=8000)
    
    if player.ads:
        player.run()
    else:
        print("\n❌ Failed to load ads")
        print("Make sure you have generated visual ads first:")
        print("   python visual_ad_generator.py")

if __name__ == "__main__":
    main()