
from calendar import month
import os
import socket
import datetime

from data_parser import download_and_parse_all, list_github_xlsx
from env_utils import detect_environment, ensure_packages, make_secret_getter
from pipeline import _github_headers
REQUIRED_PACKAGES = {
    "requests":  "requests",
    "pandas":    "pandas",
    "pymysql":   "pymysql",
    "clts_pcp":  "clts_pcp",
    "crate":     "crate",
    "openpyxl":  "openpyxl",
    "pymongo":   "pymongo",
    "certifi":   "certifi",
    "dotenv":    "python-dotenv",
    
}
ensure_packages(REQUIRED_PACKAGES)#Isto instala as packages todas necessárias
ENV        = detect_environment()
get_secret = make_secret_getter(ENV)
print(f"Ambiente: {ENV}")


import requests

hostname = socket.gethostname()
try:
    ip = requests.get("https://api.ipify.org", timeout=5).text
except Exception:
    ip = "unknown"

user = get_secret("USER")

if ENV == "flask":
    import __main__
    script  = os.path.basename(getattr(__main__, "__file__", "app.py"))
    channel = os.path.basename(os.path.dirname(os.path.abspath(script)))
else:
    try:
        import ipynbname# type: ignore tou com um problema,no render aparece also colab_noteboke no collab tbm
        script = ipynbname.name()
    except Exception:
        script = "colab_notebook"
    channel = f"{user} Fronius"

context = f"{hostname} ({ip}) | {user} | {channel} | {script}"
print("context:", context)

import config 
import clts_pcp as clts  # type: ignore




if ENV == "google_colab":
    from pipeline import run_pipeline
    config.TSTART = clts.getts()
    result = run_pipeline(ENV, get_secret, user, context)
    print("\nPipeline concluído:", result)
else:
    from flask import Flask, jsonify, render_template_string,request
    app = Flask(__name__)
    UI_HTML = """
      <!DOCTYPE html>
      <html lang="pt">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Fronius</title>
        <style>
          *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

          :root {
            --bg:      #f1f5f9;  
            --surface: #ffffff;
            --border:  #cbd5e1;  
            --accent:  #0c55e8;  
            --accent2: #102cc9;  
            --text:    #0f172a;  
            --muted:   #64748b; 
            --ok:      #16a34a; 
            --err:     #dc2626;  
            --warn:    #d97706;  
            --log:     #f8fafc;  
          }

          body {
            background: var(--bg);
            color: var(--text);
            font-family: 'Inter', monospace;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 2rem 1rem;
          }

          header {
            width: 100%;
            max-width: 950px;
            margin-bottom: 2.5rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 1.2rem;
            display: flex;
            align-items: baseline;
            gap: 1rem;
          }
          header h1 { font-size: 1.4rem; color: var(--accent); letter-spacing: .08em; font-weight: bold; }
          header span { font-size: .75rem; color: var(--muted); }

          .card {
            width: 100%;
            max-width: 950px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05); 
          }

          .card h2 {
            font-size: .8rem;
            text-transform: uppercase;
            letter-spacing: .1em;
            color: var(--muted);
            margin-bottom: 1rem;
          }

          .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: .75rem;
          }
          .info-item label { font-size: .7rem; color: var(--muted); display: block; margin-bottom: 0.15rem; }
          .info-item span  { font-size: .85rem; color: var(--text); font-weight: 500; }

          button#runBtn {
            display: block;
            width: 100%;
            max-width: 950px;
            padding: 1rem;
            background: var(--accent);
            color: #ffffff; 
            font-family: inherit;
            font-size: 1rem;
            font-weight: bold;
            letter-spacing: .08em;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: background .2s, transform .1s;
            margin-bottom: 1.5rem;
            box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
          }
          button#runBtn:hover   { background: var(--accent2); }
          button#runBtn:active  { transform: scale(.98); }
          button#runBtn:disabled {
            background: var(--border);
            color: var(--muted);
            cursor: not-allowed;
            box-shadow: none;
          }

          #statusBadge {
            display: inline-block;
            padding: .35rem .85rem;
            border-radius: 4px;
            font-size: .75rem;
            font-weight: bold;
            letter-spacing: .06em;
            margin-bottom: 1rem;
          }
          .badge-idle    { background: var(--border);  color: var(--text); }
          .badge-running { background: var(--warn);    color: #fff; } 
          .badge-ok      { background: var(--ok);      color: #fff; } 
          .badge-error   { background: var(--err);     color: #fff; }

          #log {
            width: 100%;
            max-width: 950px;
            background: var(--log);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem 1.2rem;
            font-size: .78rem;
            line-height: 1.7;
            white-space: pre-wrap;
            word-break: break-all;
            min-height: 200px;
            max-height: 500px;
            overflow-y: auto;
            color: var(--text);
            display: none;
          }
          #log .line-ok   { color: var(--ok); font-weight: bold; }
          #log .line-err  { color: var(--err); font-weight: bold; }
          #log .line-warn { color: var(--warn); font-weight: bold; }
          #log .line-info { color: var(--accent); }

          .summary-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
            margin-top: .5rem;
          }
          .stat { text-align: center; }
          .stat .val  { font-size: 1.8rem; font-weight: bold; color: var(--accent); }
          .stat .lbl  { font-size: .7rem; color: var(--muted); margin-top: .2rem; }
        </style>
      </head>
      <body>

        <header>
          <h1>Fronius</h1>
          <span id="ctxSpan">{{ context }}</span>
        </header>

        <div class="card">
          <h2>Configuration</h2>
          <div class="info-grid">
            <div class="info-item">
              <label>Environment</label>
              <span>{{ env }}</span>
            </div>
          <div class="info-item">
              <label>Create summaries?</label>
              <span>{{ create_summary }}</span>
            </div>

            <div class="info-item">
              <label>Insert mode</label>
              <span>{{ insert_mode }}</span>
            </div>

            <div class="info-item">
              <label>Times range</label>
              <span>{{ ts_filter }}</span>
            </div>
            <div class="info-item">
              <label>Repository</label>
              <span>{{ github_repo }}</span>
            </div>
          </div>
        </div>

        <button id="runBtn" onclick="runPipeline()">Run Pipeline</button>

        <div class="card" id="summaryCard" style="display:none">
          <h2>Results</h2>
          <div class="summary-grid">
            <div class="stat ok">
              <div class="val" id="sInserted">-</div>
              <div class="lbl">Inserted</div>
            </div>
            <div class="stat skip">
              <div class="val" id="sSkipped">-</div>
              <div class="lbl">Duplicated</div>
            </div>
            <div class="stat error">
              <div class="val" id="sErrors">-</div>
              <div class="lbl">Errors</div>
            </div>
          </div>
        </div>

        <span id="statusBadge" class="badge-idle">Idle</span>
        <div id="log">Nothing to show :)</div>

        <script>
          function setStatus(label, cls) {
            const b = document.getElementById('statusBadge');
            b.textContent = label;
            b.className   = cls;
          }

          function appendLog(lines) {
            const el = document.getElementById('log');
            el.style.display='block';
            lines.forEach(line => {
              const div = document.createElement('div');
              const low = line.toLowerCase();
              if (low.includes('✅') || low.includes('ok') || low.includes('inserido'))
                div.className = 'line-ok';
              else if (low.includes('❌') || low.includes('erro') || low.includes('error'))
                div.className = 'line-err';
              else if ( low.includes('duplica') || low.includes('skipped'))
                div.className = 'line-warn';
              else if (low.includes('ligand') || low.includes('parse') || low.includes('github'))
                div.className = 'line-info';
              div.textContent = line;
              el.appendChild(div);
            });
            el.scrollTop = el.scrollHeight;
          }

          async function runPipeline() {
            const btn = document.getElementById('runBtn');
            const log = document.getElementById('log');

            btn.disabled = true;
            log.innerHTML = '';
            document.getElementById('summaryCard').style.display = 'none';
            setStatus('Running', 'badge-running');

            const payload = {};
            try {
              const resp = await fetch('/run', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
              });

              const data = await resp.json();

              if (data.log) appendLog(data.log);

              if (data.status === 'ok') {
                setStatus('Done', 'badge-ok');
                document.getElementById('summaryCard').style.display = 'block';

                document.getElementById('sInserted').textContent = data.inserted ?? '-';
                document.getElementById('sSkipped').textContent  = data.skipped ?? '-';
                document.getElementById('sErrors').textContent   = data.errors ?? '-';

              } else {
                setStatus('Error ❌', 'badge-error');
                appendLog([`Error: ${data.error ?? 'unknown'}`]);
              }

            } catch (e) {
              setStatus('Error ❌', 'badge-error');
              appendLog([`Network error: ${e.message}`]);

            } finally {
              btn.disabled = false;
            }
          }
        </script>
      </body>
      </html>
      """

    @app.route("/")
    def index():
        from config import INSERT_MODE, TIMESTAMP_FILTER, GITHUB,CREATE_SUMMARY
        return render_template_string(
            UI_HTML,
            context=context,
            env=ENV,
            insert_mode=INSERT_MODE,
            create_summary=CREATE_SUMMARY,
            ts_filter=(f"{TIMESTAMP_FILTER[0].strftime('%Y-%m-%d')} until {TIMESTAMP_FILTER[1].strftime('%Y-%m-%d')}"if TIMESTAMP_FILTER else "None"),
            github_repo=f"{GITHUB['owner']}/{GITHUB['repo']}/{GITHUB['folder']}",
        )
    
    @app.route("/run", methods=["POST"])#ESTE É O ENDPOINT DO RENDER 

    def run_endpoint():
        import io
        import sys
        from pipeline import run_pipeline
        data = request.get_json() or {}

        
        timestamp_filter = data.get("timestamp_filter", None)

        # string para dt
        if timestamp_filter and len(timestamp_filter) == 2:
            start, end = timestamp_filter

            timestamp_filter = (
                datetime.datetime.fromisoformat(start) if start else None,
                datetime.datetime.fromisoformat(end) if end else None,
            )

            # se ambos vazios ent None
            if timestamp_filter == (None, None):
                timestamp_filter = None
           

        buf = io.StringIO()
        old_out = sys.stdout
        sys.stdout = buf
        config.TSTART = clts.getts()
   
        try:
            result = run_pipeline( ENV, get_secret, user, context )
            sys.stdout = old_out
            log_lines = buf.getvalue().splitlines()

            return jsonify({
                "status": "ok",
                "inserted": result.inserted,
                "skipped": result.skipped,
                "errors": result.errors,
                "log": log_lines,
            })

        except Exception as e:
            sys.stdout = old_out
            return jsonify({
                "status": "error",
                "error": str(e),
                "log": buf.getvalue().splitlines(),
            }), 500 
    @app.route('/api',methods=['GET'])
    
    def api( ):
        import config
        import clts_pcp as clts
        from data_parser import list_github_xlsx
        config.TSTART = clts.getts()
        response=dict()
        meta=request.args.get('meta',default='').lower()
        file_list=request.args.get('filelist',default="").lower()
        selected_day=request.args.get('day',default="").strip()
        
        try:
          headers_github = _github_headers(get_secret, user)
          df_normal, df_rectifier, df_specific = download_and_parse_all(headers_github)
          
          if selected_day:
            try:
              parsed_date = datetime.datetime.strptime(selected_day, "%Y%m%d").date()
              anot=df_normal[df_normal["_tstamp"].dt.date == parsed_date]
             
            
              if anot.empty:
                   response["selected_date"]={"selected_day":f"Não existem dados sobre {parsed_date} nos ficheiros"}
              else:
                response["selected_date"]={"selected_day":anot.to_dict(orient="records")}
            except ValueError:
                response["selected_date"]={"error":"O campo \'day\' deve ter o formato YYYYMMDD"}
          response["data"] ={ "normal_size":len(df_normal),"recifier_size":len(df_rectifier),"specific_size":len(df_specific),"normal":df_normal.to_dict(orient="records"),"rectifier":df_rectifier.to_dict(orient="records"),"specific":df_specific.to_dict(orient="records")}
          if meta=="on":
              tmp={"theme":"Fronius","license":"A definir","description":"Dataframes proveninentes da pipeline FROINUS","update_frequency":"A definir","acess_rights":"A definir","ip":ip,"contact_point":"A definir","contact_email":"A definir","DBS implementadas": "crate,tidb,mongo","source":config.GITHUB}
              response["meta"]=tmp
          if file_list=="on":
              tmp=list_github_xlsx(headers_github)
              response["nr_files"]=len(tmp)
              response["file_list"]=tmp
          response["times"]=clts.listtimes()#nao sei se faz sentido
          return jsonify(response)
        except Exception as e:
            print(e)
            return jsonify({"error":str(e)}),500


    

    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
#rever