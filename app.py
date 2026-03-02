from flask import Flask, render_template_string, request
import pandas as pd
import urllib.parse
import re
import io

app = Flask(__name__)

# =========================================
# PERSONALIZED MESSAGE TEMPLATE
# =========================================
MESSAGE_TEMPLATE = """Namaskar,

I came across *{name}* in {city} on Google Maps.

Many restaurants are getting extra customers by showing their menu online with a simple website + QR code on tables.

I can create a demo website for *{name}* with a menu, photos, WhatsApp ordering, and Google Maps location.

Would you like to see it?

– Vedant"""

# =========================================
# MAIN ROUTE (Handles both GET and POST)
# =========================================
@app.route("/", methods=["GET", "POST"])
def home():
    clients = []
    error = None

    if request.method == "POST":
        # Check if the post request has the file part
        if 'file' not in request.files:
            error = "No file uploaded."
        else:
            file = request.files['file']
            if file.filename == '':
                error = "No file selected."
            elif file and file.filename.endswith('.csv'):
                try:
                    # Read the uploaded file directly into pandas
                    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
                    df = pd.read_csv(stream, header=None)
                    
                    # Force assign columns assuming the standard format
                    df.columns = [
                        "Business Name", "Client Name", "City", "Phone", 
                        "Date", "Salesperson", "Service", "Status", "Amount"
                    ]
                    df.fillna("", inplace=True)

                    # Process the rows
                    for _, row in df.iterrows():
                        name = str(row["Business Name"]).strip()
                        city = str(row["City"]).strip()
                        raw_phone = str(row["Phone"])
                        status = str(row["Status"]).strip()

                        # Data Cleaning: Keep only digits
                        phone = re.sub(r'\D', '', raw_phone)
                        
                        # Strip out '91' if it was accidentally included
                        if phone.startswith('91') and len(phone) > 10:
                            phone = phone[2:]

                        # Skip rows that don't have the minimum required data
                        if not name or not phone:
                            continue 

                        # Create personalized message
                        message = MESSAGE_TEMPLATE.format(name=name, city=city)
                        encoded_msg = urllib.parse.quote(message)
                        wa_link = f"https://wa.me/91{phone}?text={encoded_msg}"

                        clients.append({
                            "name": name,
                            "city": city,
                            "phone": phone,
                            "status": status,
                            "wa_link": wa_link,
                            "raw_message": message
                        })
                except Exception as e:
                    error = f"Error processing file: {str(e)}"
            else:
                error = "Please upload a valid CSV file."

    return render_template_string(TEMPLATE, clients=clients, error=error)

# =========================================
# HTML TEMPLATE (Upload Form + Dashboard)
# =========================================
TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>Client Outreach Hub</title>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f6f8; padding: 20px; color: #333; margin: 0; }
    h2 { text-align: center; color: #2c3e50; margin-bottom: 20px; }
    
    .container { max-width: 520px; margin: 0 auto; }
    
    .card { background: white; padding: 20px; margin-bottom: 15px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    
    /* Upload Section Styles */
    .upload-box { text-align: center; padding: 40px 20px; border: 2px dashed #cbd5e1; border-radius: 12px; background: #f8fafc; }
    input[type="file"] { margin: 20px 0; max-width: 100%; }
    .btn-upload { background: #3b82f6; color: white; border: none; padding: 12px 24px; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; width: 100%; box-sizing: border-box;}
    .btn-upload:hover { background: #2563eb; }
    .error { color: #dc2626; text-align: center; background: #fee2e2; padding: 10px; border-radius: 6px; margin-bottom: 15px; }

    /* Dashboard Styles */
    .search-container { margin-bottom: 20px; display: flex; gap: 10px; }
    #searchInput { flex: 1; padding: 12px; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; box-sizing: border-box; }
    .btn-reset { background: #ef4444; color: white; border: none; padding: 12px; border-radius: 8px; cursor: pointer; font-weight: bold; text-decoration: none; display: flex; align-items: center; justify-content: center; }
    
    h3 { margin-top: 0; color: #2c3e50; }
    p { margin: 8px 0; color: #555; }
    
    .status-badge { display: inline-block; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; background: #e0e0e0; color: #333; }
    .status-pending { background: #fff3cd; color: #856404; }
    .status-contacted { background: #d4edda; color: #155724; }
    
    .btn-group { display: flex; gap: 10px; margin-top: 15px; }
    button { border: none; padding: 12px 18px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: bold; flex: 1; transition: background 0.2s; }
    
    .btn-wa { background: #25D366; color: white; display: flex; justify-content: center; align-items: center; width: 100%;}
    .btn-wa:hover { background: #1ebe5d; }
    
    .btn-copy { background: #e2e8f0; color: #475569; }
    .btn-copy:hover { background: #cbd5e1; }
    
    a { text-decoration: none; display: flex; flex: 1; }
</style>
</head>

<body>

<div class="container">
    <h2>📋 Client Outreach Hub</h2>

    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}

    {% if not clients %}
        <div class="card upload-box">
            <h3>Upload Clients CSV</h3>
            <p style="font-size: 14px;">Ensure columns are in order: Business Name, Client Name, City, Phone...</p>
            <form method="POST" enctype="multipart/form-data">
                <input type="file" name="file" accept=".csv" required>
                <button type="submit" class="btn-upload">Upload & Process</button>
            </form>
        </div>
    {% else %}
        <div class="search-container">
            <input type="text" id="searchInput" onkeyup="filterClients()" placeholder="Search by name, city, or status...">
            <a href="/" class="btn-reset">↺ New File</a>
        </div>

        <div id="clientList">
            {% for c in clients %}
            <div class="card client-card">
                <h3>{{c.name}}</h3>
                <p>📍 {{c.city}}</p>
                <p>📞 {{c.phone}}</p>
                
                <p>Status: <span class="status-badge 
                    {% if 'pending' in c.status|lower %}status-pending{% endif %}
                    {% if 'contacted' in c.status|lower %}status-contacted{% endif %}
                    ">{{c.status}}</span>
                </p>

                <div class="btn-group">
                    <a href="{{c.wa_link}}" target="_blank">
                        <button class="btn-wa">Send WhatsApp</button>
                    </a>
                    <button class="btn-copy" onclick="copyToClipboard(this, `{{c.raw_message}}`)">Copy Text</button>
                </div>
            </div>
            {% endfor %}
        </div>
    {% endif %}
</div>

<script>
function filterClients() {
    let input = document.getElementById('searchInput').value.toLowerCase();
    let cards = document.getElementsByClassName('client-card');

    for (let i = 0; i < cards.length; i++) {
        let textContent = cards[i].innerText.toLowerCase();
        if (textContent.includes(input)) {
            cards[i].style.display = "";
        } else {
            cards[i].style.display = "none";
        }
    }
}

function copyToClipboard(btnElement, text) {
    navigator.clipboard.writeText(text).then(function() {
        let originalText = btnElement.innerText;
        btnElement.innerText = "Copied!";
        btnElement.style.background = "#d4edda";
        btnElement.style.color = "#155724";
        
        setTimeout(function() {
            btnElement.innerText = originalText;
            btnElement.style.background = "#e2e8f0";
            btnElement.style.color = "#475569";
        }, 2000);
    }, function(err) {
        alert('Could not copy text: ' + err);
    });
}
</script>

</body>
</html>
"""

# =========================================
# RUN SERVER
# =========================================
if __name__ == "__main__":
    # Host '0.0.0.0' allows you to access this from your mobile browser
    # if your phone is on the same WiFi network as your computer.

    app.run(host='0.0.0.0', port=5000, debug=True)
