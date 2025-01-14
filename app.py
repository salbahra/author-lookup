from flask import Flask, request, render_template_string
from Bio import Entrez
from Bio import Medline
from collections import defaultdict
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<html>
<head>
    <title>Author Publication Analysis</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 40px;
        }
        h1, h2 {
            margin-bottom: 20px;
        }
        form {
            margin-bottom: 40px;
        }
        table {
            border-collapse: collapse;
            margin-bottom: 40px;
        }
        table, th, td {
            border: 1px solid #ccc;
            padding: 8px;
        }
        th {
            background: #f2f2f2;
        }
        .input-section {
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <h1>Author Publication Analysis</h1>
    <form method="POST">
        <div class="input-section">
            <label for="author_name">Author Name (e.g., "Smith, John"):</label><br>
            <input type="text" name="author_name" id="author_name" required>
        </div>
        <div class="input-section">
            <label for="email">Optional Email for NCBI Entrez:</label><br>
            <input type="email" name="email" id="email">
        </div>
        <input type="submit" value="Search">
    </form>
    {% if results %}
    <h2>Results for {{ author_name }}</h2>
    <p>Total Publications Found: {{ total_pubs }}</p>
    <h3>Year-by-Year Breakdown</h3>
    <table>
        <tr>
            <th>Year</th>
            <th>Total</th>
            <th>First Author</th>
            <th>Middle Author</th>
            <th>Last Author</th>
            <th>Fraction as First Author</th>
            <th>Fraction as Last Author</th>
        </tr>
        {% for year, data in results.items() %}
        <tr>
            <td>{{ year }}</td>
            <td>{{ data.total }}</td>
            <td>{{ data.first }}</td>
            <td>{{ data.middle }}</td>
            <td>{{ data.last }}</td>
            <td>{{ data.first_fraction }}</td>
            <td>{{ data.last_fraction }}</td>
        </tr>
        {% endfor %}
    </table>
    <p><em>Note:</em> Fractions are calculated as count/total papers for that year.</p>
    {% endif %}
</body>
</html>
"""

def match_author(record_author, target_last, target_initials):
    parts = record_author.split()
    if len(parts) < 2:
        return False
    last_name = parts[0]
    initials = "".join(parts[1:])
    return (last_name.lower() == target_last.lower()) and initials.lower().startswith(target_initials.lower())

def parse_author_name(author_name):
    if ',' in author_name:
        last, first = author_name.split(',', 1)
        last = last.strip()
        first = first.strip()
        initials = ''.join([part[0] for part in first.split() if part]) 
    else:
        parts = author_name.split()
        if len(parts) == 1:
            last = parts[0]
            initials = ""
        else:
            last = parts[-1]
            first_parts = parts[:-1]
            initials = ''.join([p[0] for p in first_parts])
    return last, initials

def get_pubmed_ids_for_author(author_name, email):
    Entrez.email = email
    target_last, target_initials = parse_author_name(author_name)
    if target_initials:
        query = f'{target_last} {target_initials}[Author]'
    else:
        query = f'{target_last}[Author]'

    handle = Entrez.esearch(db="pubmed", term=query, retmax=100000)
    record = Entrez.read(handle)
    handle.close()
    pmid_list = record.get("IdList", [])
    return pmid_list, target_last, target_initials

def get_author_positions_by_year(pmid_list, target_last, target_initials, email):
    Entrez.email = email
    year_data = defaultdict(lambda: {"first":0, "middle":0, "last":0})

    BATCH_SIZE = 200
    for start in range(0, len(pmid_list), BATCH_SIZE):
        batch = pmid_list[start:start+BATCH_SIZE]
        handle = Entrez.efetch(db="pubmed", id=batch, rettype="medline", retmode="text")
        records = Medline.parse(handle)
        
        for record in records:
            if 'AU' not in record:
                continue
            authors = record['AU']

            # Extract year from DP (Date of Publication)
            dp = record.get('DP', '')
            pub_year = "Unknown"
            if len(dp) >= 4 and dp[:4].isdigit():
                pub_year = dp[:4]

            found_positions = [i for i, a in enumerate(authors) 
                               if match_author(a, target_last, target_initials)]
            
            for pos in found_positions:
                if pos == 0:
                    year_data[pub_year]["first"] += 1
                elif pos == len(authors)-1:
                    year_data[pub_year]["last"] += 1
                else:
                    year_data[pub_year]["middle"] += 1
        handle.close()
    
    return year_data

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        author_name = request.form.get("author_name", "").strip()
        email = request.form.get("email", "").strip()
        if not email:
            email = "your_email@example.com"  # fallback email

        pmid_list, target_last, target_initials = get_pubmed_ids_for_author(author_name, email)
        year_data = get_author_positions_by_year(pmid_list, target_last, target_initials, email)
        total_pubs = len(pmid_list)

        # Prepare results for rendering
        results = {}
        for year in sorted(year_data.keys()):
            data = year_data[year]
            total = data["first"] + data["middle"] + data["last"]
            first_fraction = f"{data['first']/total:.2f}" if total > 0 else "N/A"
            last_fraction = f"{data['last']/total:.2f}" if total > 0 else "N/A"
            results[year] = {
                "first": data["first"],
                "middle": data["middle"],
                "last": data["last"],
                "total": total,
                "first_fraction": first_fraction,
                "last_fraction": last_fraction
            }

        return render_template_string(HTML_TEMPLATE, 
                                      author_name=author_name,
                                      total_pubs=total_pubs,
                                      results=results)
    else:
        return render_template_string(HTML_TEMPLATE, results=None)

if __name__ == "__main__":
    # Run the Flask app
    app.run(host="0.0.0.0", port=os.environ.get('PORT', 5000), debug=True)
