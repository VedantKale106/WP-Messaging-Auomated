from flask import Flask, render_template_string, request
import pandas as pd
import urllib.parse
import re
import io
import requests
from datetime import datetime

app = Flask(__name__)

# =========================================
# CONFIGURATION & HARDCODED DATA
# =========================================
HARDCODED_SHEET_URL = "https://docs.google.com/spreadsheets/d/1WP8A4up-SjQ-xcWLxapd0ejcnWEAU7Dk2FoKiRuos4Q/export?format=csv"

# =========================================
# CATEGORY-SPECIFIC MESSAGE TEMPLATES
# =========================================
MESSAGE_TEMPLATES = {
    "Hotel": """Namaskar,
I came across *{name}* in {city} on Google Maps.
Many restaurants are getting extra customers by showing their menu online with a simple website + QR code on tables.
I can create a demo website for *{name}* with a menu, photos, and WhatsApp ordering.
Would you like to see it?
– Vedant""",

    "Lodging": """Namaskar,
I saw *{name}* in {city} on Google Maps. 
I help hotels and resorts get more direct bookings by creating professional websites that showcase rooms, amenities, and location clearly.
I can build a premium digital profile for *{name}*.
Are you interested in a quick demo?
– Vedant""",

    "Hospital": """Namaskar,
I came across *{name}* in {city}. 
I specialize in creating digital profiles for clinics and hospitals so patients can easily find your services, timing, and location online.
I can set up a professional website for *{name}*.
Would you like to see how it looks?
– Vedant""",

    "Shop": """Namaskar,
I saw your shop *{name}* in {city}. 
I help local businesses reach more customers by creating a digital product catalog and a professional website.
I can create a demo for *{name}* to show your products online.
Would you like to see it?
– Vedant""",

    "Default": """Namaskar,
I came across *{name}* in {city} on Google Maps.
I help local businesses grow their online presence with professional websites and Google Maps optimization.
I've prepared a demo for *{name}*.
Would you like to see it?
– Vedant"""
}

def process_dataframe(df):
    """Helper to process the dataframe into the grouped dictionary format"""
    df.columns = [c.strip() for c in df.columns]
    
    # DO NOT use fillna("-") on the whole dataframe if you have numeric columns
    # Instead, fillna for specific text columns or use an empty string
    df = df.fillna("")

    client_list = []
    stats = {
        "Total": 0, 
        "Completed": 0, 
        "Pending": 0, 
        "NotInterested": 0,
        "TotalRevenue": 0.0,
        "ConversionRate": 0.0
    }
    salespeople = set()

    for _, row in df.iterrows():
        status = str(row.get("Status", "Pending")).strip()
        # Force amount to string before cleaning to avoid float64 errors
        amount_val = str(row.get("Amount", "0")).strip()
        
        # Parse amount for revenue
        try:
            # If the value is just "-" or empty, set to 0
            if amount_val in ["-", ""]:
                clean_amt = 0.0
            else:
                # Remove currency symbols, commas, etc.
                clean_amt = float(re.sub(r'[^\d.]', '', amount_val))
        except (ValueError, TypeError):
            clean_amt = 0.0

        stats["Total"] += 1
        
        is_not_interested = status.lower() == "not interested"
        
        if status.lower() == "completed":
            stats["Completed"] += 1
            stats["TotalRevenue"] += clean_amt
        elif is_not_interested:
            stats["NotInterested"] += 1
            continue
        else:
            stats["Pending"] += 1
        
        referred_by = str(row.get("Reffered By", "-")).strip()
        if referred_by and referred_by != "-":
            salespeople.add(referred_by)

        # Rest of your processing logic...
        name = str(row.get("Business Name", "")).strip()
        city = str(row.get("Location", "")).strip()
        raw_phone = str(row.get("Phone", ""))
        date_str = str(row.get("Date", "Unknown")).strip()
        category = str(row.get("Category", "Business")).strip()
        client_name = str(row.get("Client Name", "-")).strip()
        service = str(row.get("Service", "-")).strip()

        # Phone Cleaning
        phone = re.sub(r'\D', '', raw_phone)
        if phone.startswith('91') and len(phone) > 10:
            phone = phone[2:]
        
        if not name or not phone:
            continue

        # Date Parsing
        try:
            clean_date_str = date_str.split(' ')[0]
            dt_obj = pd.to_datetime(clean_date_str, dayfirst=True)
            sort_key = dt_obj.strftime('%Y-%m-%d')
            display_date = dt_obj.strftime('%d %b %Y')
        except:
            sort_key = "0000-00-00"
            display_date = date_str

        template_key = "Default"
        for key in MESSAGE_TEMPLATES.keys():
            if key.lower() in category.lower():
                template_key = key
                break
        
        message = MESSAGE_TEMPLATES[template_key].format(name=name, city=city)
        encoded_msg = urllib.parse.quote(message)
        maps_link = f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(name + ' ' + city)}"

        client_list.append({
            "name": name,
            "client_name": client_name,
            "city": city,
            "phone": phone,
            "status": status,
            "category": category,
            "referred_by": referred_by,
            "service": service,
            "amount": amount_val if amount_val not in ["", "0"] else "0",
            "wa_link": f"https://wa.me/91{phone}?text={encoded_msg}",
            "call_link": f"tel:+91{phone}",
            "maps_link": maps_link,
            "raw_message": message,
            "date": display_date,
            "sort_key": sort_key
        })

    if stats["Total"] > 0:
        stats["ConversionRate"] = round((stats["Completed"] / stats["Total"]) * 100, 1)

    client_list.sort(key=lambda x: x['sort_key'], reverse=True)

    grouped = {}
    for client in client_list:
        d = client['date']
        if d not in grouped:
            grouped[d] = []
        grouped[d].append(client)
    
    return grouped, stats, sorted(list(salespeople))

# =========================================
# MAIN ROUTE
# =========================================
@app.route("/", methods=["GET", "POST"])
def home():
    grouped_clients = {}
    stats = {"Total": 0, "Completed": 0, "Pending": 0, "NotInterested": 0, "TotalRevenue": 0.0, "ConversionRate": 0.0}
    salespeople = []
    error = None
    
    try:
        response = requests.get(HARDCODED_SHEET_URL, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        grouped_clients, stats, salespeople = process_dataframe(df)
    except Exception as e:
        error = f"Failed to sync with Google Sheets: {str(e)}"

    return render_template_string(TEMPLATE, grouped_clients=grouped_clients, stats=stats, salespeople=salespeople, error=error)

# =========================================
# MODERN BLACK & GOLD TEMPLATE
# =========================================
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Vedant | Outreach Hub</title>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<style>
    :root {
        --bg-black: #0a0a0a;
        --card-black: #161616;
        --gold-primary: #d4af37;
        --gold-secondary: #f1c40f;
        --gold-gradient: linear-gradient(135deg, #d4af37 0%, #f1c40f 100%);
        --text-white: #e0e0e0;
        --text-muted: #a0a0a0;
        --border-gold: rgba(212, 175, 55, 0.3);
        --status-completed: #2ecc71;
        --status-rejected: #ff4d4d;
    }

    body { 
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; 
        background: var(--bg-black); 
        padding: 0; 
        color: var(--text-white); 
        margin: 0; 
        line-height: 1.6;
    }

    .header {
        background: var(--card-black);
        padding: 20px;
        text-align: center;
        border-bottom: 2px solid var(--gold-primary);
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }

    .header h2 {
        margin: 0;
        font-size: 20px;
        letter-spacing: 2px;
        text-transform: uppercase;
        background: var(--gold-gradient);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }

    .dashboard {
        padding: 20px;
        background: #111;
        border-bottom: 1px solid #222;
    }

    .stats-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 15px;
    }

    .stat-card {
        background: #1a1a1a;
        padding: 12px;
        border-radius: 10px;
        border: 1px solid #333;
        text-align: center;
    }

    .stat-value { display: block; font-size: 20px; font-weight: 800; color: var(--gold-primary); }
    .stat-label { font-size: 9px; text-transform: uppercase; color: var(--text-muted); letter-spacing: 1px; }

    .revenue-summary {
        margin-top: 15px;
        display: flex;
        justify-content: space-between;
        background: rgba(212, 175, 55, 0.1);
        padding: 10px 15px;
        border-radius: 8px;
        border: 1px solid var(--border-gold);
    }
    
    .rev-item span { font-size: 11px; color: var(--text-muted); text-transform: uppercase; }
    .rev-item b { display: block; font-size: 16px; color: var(--gold-secondary); }

    .container { max-width: 500px; margin: 0 auto; padding: 15px; }
    
    .filter-section {
        position: sticky;
        top: 0;
        z-index: 100;
        background: var(--bg-black);
        padding: 10px 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .search-row { display: flex; gap: 8px; }

    #searchInput, #salespersonFilter {
        padding: 12px 15px;
        border: 1px solid var(--border-gold);
        border-radius: 25px;
        background: var(--card-black);
        color: white;
        font-size: 14px;
        outline: none;
    }

    #searchInput { flex: 1; }
    #salespersonFilter { width: 120px; }

    .btn-sync {
        background: var(--gold-gradient);
        color: #000;
        border: none;
        padding: 8px 15px;
        border-radius: 20px;
        font-weight: bold;
        text-decoration: none;
        font-size: 12px;
        text-align: center;
    }

    .date-header { 
        padding: 10px 0; 
        margin: 25px 0 10px 0; 
        font-size: 11px; 
        font-weight: bold; 
        color: var(--gold-primary);
        text-transform: uppercase;
        letter-spacing: 2px;
        border-bottom: 1px solid var(--border-gold);
        display: flex;
        justify-content: space-between;
    }

    .client-card { 
        background: var(--card-black); 
        padding: 18px; 
        margin-bottom: 15px; 
        border-radius: 14px; 
        border: 1px solid var(--border-gold);
        position: relative;
    }

    .client-title { 
        margin: 0 0 5px 0; 
        font-size: 18px; 
        color: var(--gold-secondary); 
        font-weight: 700;
        padding-right: 80px;
    }

    .category-label {
        position: absolute;
        top: 18px;
        right: 18px;
        font-size: 9px;
        text-transform: uppercase;
        color: var(--gold-primary);
        border: 1px solid var(--gold-primary);
        padding: 2px 6px;
        border-radius: 4px;
    }

    .client-info-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin: 8px 0;
    }

    .client-info { 
        font-size: 13px; 
        color: var(--text-muted); 
        display: flex; 
        align-items: center; 
        gap: 6px; 
    }

    .info-label { color: var(--gold-primary); font-weight: 600; font-size: 10px; text-transform: uppercase; display: block; margin-bottom: 1px;}
    
    .status-badge { 
        display: inline-block; 
        padding: 3px 10px; 
        border-radius: 4px; 
        font-size: 10px; 
        font-weight: bold; 
        background: rgba(212, 175, 55, 0.05); 
        color: var(--text-white);
        margin-top: 8px;
        border: 1px solid var(--border-gold);
    }

    .status-completed {
        background: rgba(46, 204, 113, 0.1) !important;
        color: #2ecc71 !important;
        border-color: #2ecc71 !important;
    }

    .btn-group { 
        display: grid; 
        grid-template-columns: 1fr 1fr; 
        gap: 8px; 
        margin-top: 18px; 
    }

    .btn-action { 
        border: none; 
        padding: 10px; 
        border-radius: 8px; 
        cursor: pointer; 
        font-size: 13px; 
        font-weight: 600; 
        display: flex; 
        align-items: center; 
        justify-content: center; 
        gap: 6px; 
        text-decoration: none; 
    }
    
    .btn-wa { 
        background: var(--gold-gradient); 
        color: #000; 
        grid-column: span 2; 
        padding: 12px;
        font-size: 14px;
    }
    
    .btn-call { 
        background: transparent; 
        color: var(--gold-primary); 
        border: 1px solid var(--gold-primary);
    }

    .btn-maps {
        background: #222;
        color: #4285F4;
        border: 1px solid #4285F4;
    }
    
    .btn-copy { 
        background: #2a2a2a; 
        color: var(--text-white); 
    }

    .error { color: #ff4d4d; padding: 10px; text-align: center; font-size: 13px; border: 1px solid #ff4d4d; border-radius: 8px; margin-bottom: 15px; }

    .icon { width: 12px; height: 12px; fill: currentColor; }
</style>
</head>
<body>

<div class="header">
    <h2>Outreach Hub</h2>
</div>

<div class="dashboard">
    <div class="stats-grid">
        <div class="stat-card">
            <span class="stat-value">{{ stats.Total }}</span>
            <span class="stat-label">Total Leads</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" style="color: #2ecc71;">{{ stats.Completed }}</span>
            <span class="stat-label">Completed</span>
        </div>
        <div class="stat-card">
            <span class="stat-value" style="color: #ff4d4d;">{{ stats.NotInterested }}</span>
            <span class="stat-label">Not Interested</span>
        </div>
    </div>
    
    <div class="revenue-summary">
        <div class="rev-item">
            <span>Conversion Rate</span>
            <b>{{ stats.ConversionRate }}%</b>
        </div>
        <div class="rev-item" style="text-align: right;">
            <span>Total Revenue</span>
            <b>₹{{ "{:,.2f}".format(stats.TotalRevenue) }}</b>
        </div>
    </div>
</div>

<div class="container">

    {% if error %}
        <div class="error">⚠️ {{ error }}</div>
    {% endif %}

    <div class="filter-section">
        <div class="search-row">
            <input type="text" id="searchInput" onkeyup="filterClients()" placeholder="Search leads...">
            <select id="salespersonFilter" onchange="filterClients()">
                <option value="">All Staff</option>
                {% for person in salespeople %}
                    <option value="{{ person }}">{{ person }}</option>
                {% endfor %}
            </select>
        </div>
        <a href="/" class="btn-sync">Sync Google Sheets</a>
    </div>

    <div id="clientList">
        {% for date, clients in grouped_clients.items() %}
            <div class="date-group">
                <div class="date-header">
                    <span>{{ date }}</span>
                    <span>{{ clients|length }} Active</span>
                </div>
                {% for c in clients %}
                <div class="card client-card" data-salesperson="{{ c.referred_by }}">
                    <span class="category-label">{{c.category}}</span>
                    <h3 class="client-title">{{c.name}}</h3>
                    
                    <div class="client-info" style="margin-bottom: 10px;">
                        <span class="info-label">Contact</span>
                        <span style="color: var(--text-white);">{{c.client_name}} • {{c.phone}}</span>
                    </div>

                    <div class="client-info-grid">
                        <div class="client-info">
                            <svg class="icon" viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>
                            {{c.city}}
                        </div>
                        <div class="client-info">
                            <span class="info-label">By:</span> {{c.referred_by}}
                        </div>
                    </div>

                    <div class="client-info-grid" style="border-top: 1px solid #222; padding-top: 8px; margin-top: 8px;">
                        <div>
                            <span class="info-label">Service</span>
                            <span class="client-info">{{c.service}}</span>
                        </div>
                        <div style="text-align: right;">
                            <span class="info-label">Amount</span>
                            <span style="color: var(--gold-secondary); font-weight: bold;">₹{{c.amount}}</span>
                        </div>
                    </div>

                    <span class="status-badge {% if c.status.lower() == 'completed' %}status-completed{% endif %}">{{c.status}}</span>

                    <div class="btn-group">
                        <a href="{{c.wa_link}}" target="_blank" class="btn-action btn-wa">
                            <span>WhatsApp Pitch</span>
                        </a>
                        <a href="{{c.call_link}}" class="btn-action btn-call">
                            <span>Call</span>
                        </a>
                        <a href="{{c.maps_link}}" target="_blank" class="btn-action btn-maps">
                            <span>Maps</span>
                        </a>
                        <button class="btn-action btn-copy" onclick="copyToClipboard(this, `{{c.raw_message}}`)">
                            <span>Copy</span>
                        </button>
                    </div>
                </div>
                {% endfor %}
            </div>
        {% endfor %}
    </div>
</div>

<script>
function filterClients() {
    let searchInput = document.getElementById('searchInput').value.toLowerCase();
    let staffFilter = document.getElementById('salespersonFilter').value.toLowerCase();
    let cards = document.getElementsByClassName('client-card');
    let groups = document.getElementsByClassName('date-group');

    for (let i = 0; i < cards.length; i++) {
        let cardText = cards[i].innerText.toLowerCase();
        let cardSalesperson = cards[i].getAttribute('data-salesperson').toLowerCase();
        
        let matchesSearch = cardText.includes(searchInput);
        let matchesStaff = staffFilter === "" || cardSalesperson === staffFilter;

        cards[i].style.display = (matchesSearch && matchesStaff) ? "" : "none";
    }

    for (let g = 0; g < groups.length; g++) {
        let visibleCards = groups[g].querySelectorAll('.client-card[style=""]');
        groups[g].style.display = visibleCards.length > 0 ? "" : "none";
    }
}

function copyToClipboard(btn, text) {
    const originalContent = btn.innerHTML;
    navigator.clipboard.writeText(text).then(() => {
        btn.innerHTML = "<span>Copied!</span>";
        btn.style.background = "#d4af37";
        setTimeout(() => {
            btn.innerHTML = originalContent;
            btn.style.background = "#2a2a2a";
        }, 1500);
    });
}
</script>

</body>
</html>
"""

if __name__ == "__main__":

    app.run(host='0.0.0.0', port=5000, debug=True)
