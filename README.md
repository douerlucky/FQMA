<div align="center">
  <h1>FQMA</h1>
  <p><strong>Ontology-based Federated Query Multi-Agent Framework</strong></p>

  <p>
    <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
    <img alt="Paradigm" src="https://img.shields.io/badge/Paradigm-OBDA-0F766E">
    <img alt="Architecture" src="https://img.shields.io/badge/Architecture-Multi--Agent-2563EB">
    <img alt="Databases" src="https://img.shields.io/badge/Backends-MySQL%20%7C%20PostgreSQL%20%7C%20Neo4j-16A34A">
    <img alt="Status" src="https://img.shields.io/badge/Status-Research%20Prototype-F59E0B">
  </p>

  <p>
    FQMA supports natural language federated querying over heterogeneous data sources under the OBDA paradigm.
  </p>
</div>

---

## Overview

FQMA is a research prototype for **dependency-aware federated query answering** across heterogeneous databases. It takes a natural language question, decomposes it into subqueries, generates ontology-aware SPARQL, performs semantic checking and repair, routes each subquery to the appropriate backend, and finally aggregates the returned results.

FQMA is designed around four cooperative agents and is evaluated on two benchmarks: **RODI-C** and **GMQA**. The reported results are **91.7% FEX on RODI-C** and **90.1% FEX on GMQA**.

### Key Features

- Natural language to federated query workflow
- Ontology-guided SPARQL generation
- Iterative semantic repair with rule-based validation
- Dynamic routing across heterogeneous backends (MySQL, PostgreSQL, Neo4j)
- Result aggregation in both table and text form
- Extensible architecture for new domains and adapters

---

## Framework at a Glance

FQMA is a four-agent framework consisting of:

1. **Query Planning and Generation Agent**
2. **Semantic Query Repair Agent**
3. **Query Routing and Adaptation Agent**
4. **Result Aggregation Agent**

### Workflow

```text
Natural Language Query
        |
        v
Query Planning
        |
        v
SPARQL Generation
        |
        v
Semantic Validation and Repair
        |
        v
Subquery Routing and Adaptation
        |
        +--> Neo4j
        +--> MySQL
        +--> PostgreSQL
        |
        v
Result Aggregation
```

---

## Repository Structure

```text
.
├── Datasets/                   # Dataset import scripts and raw data
│   ├── GMQA/                   # GMQA raw SQL and Cypher files
│   ├── RODI-Conf/              # RODI-C raw SQL and Cypher files
│   ├── import_GMQA.py          # ⚙️ One-click GMQA import script (requires configuration)
│   └── import_RODI.py          # ⚙️ One-click RODI import script (requires configuration)
│
├── FQMA/                       # Core implementation
│   ├── agents/                 # Multi-agent implementations
│   ├── data/                   # Ontology and TTL mapping files (runtime)
│   ├── frontend/               # Web interface (Vue/Vite)
│   ├── scripts/                # Utility scripts
│   ├── Tools/                  # Query conversion helpers
│   ├── QAsets/                 # Benchmark question sets
│   ├── app.py                  # Flask web application entry
│   ├── main.py                 # CLI entry point
│   ├── config.py               # ⚙️ Main configuration file (requires configuration)
│   ├── ReAct.py                # Single-agent / ReAct baseline
│   ├── no_repair.py            # Repair ablation variant
│   ├── exp_framework_modified.py  # Experiment evaluation script
│   ├── requirements.txt        # Python dependencies
│   ├── start.sh                # One-click launcher (macOS / Linux)
│   └── start.bat               # One-click launcher (Windows)
│
├── OntologyFiles/
│   ├── GMQA_ontology.owl
│   └── rodi_ontology.owl
│
├── QuestionSet/
│   ├── RODI-C-cross-2-database.json
│   ├── RODI-C-cross-3-database.json
│   └── GMQA.json
│
└── TTLFiles/
    ├── gutmdisorder.ttl
    ├── kegg.ttl
    ├── newgutmgene.ttl
    ├── pgmkg.ttl
    ├── relationship.ttl
    ├── rodi_mysql.ttl
    ├── rodi_neo4j.ttl
    └── rodi_postgre.ttl
```

---

## Datasets and Knowledge Resources

### RODI-C

RODI-C is a reconstructed heterogeneous federated benchmark derived from the Conference-native scenario of the RODI benchmark. It contains **237 natural language questions** over MySQL, PostgreSQL, and Neo4j.

### GMQA

GMQA is a self-constructed benchmark for gut microbiota federated querying. It comprises **320 complex natural language questions** spanning multiple biological resources and four task categories.

### Included Ontologies and Mappings

The repository includes ontology files for both RODI and GMQA, along with mapping files in TTL format for sources such as GutMDisorder, KEGG, GutMGene, PGMKG, and RODI backends. The paper reports **35 mapping rules for RODI-C** and **51 mapping rules for GMQA**.

---

## Reported Results

| Dataset | FEX   | SEX   |
|---------|------:|------:|
| RODI-C  | 91.7% | 95.2% |
| GMQA    | 90.1% | 91.1% |

---

## Prerequisites

Before proceeding, make sure the following software is installed and running on your machine:

| Software | Version | Notes |
|----------|---------|-------|
| Python | **3.12** | Required. The start scripts enforce this version. |
| Node.js | 18 LTS or later | Required for the web frontend. |
| MySQL | 8.0+ | Must be running before import. |
| PostgreSQL | 14+ | Must be running before import. |
| Neo4j | 5.x | Must be running before import. |

> **Java is not required** unless you plan to use Ontop for SPARQL-to-SQL rewriting outside of this codebase.

---

## Installation and Setup

The installation and display video are available here:

https://github.com/user-attachments/assets/35296116-0364-4c31-b310-2454760cacd1

The setup process has **two stages**:

1. **Import the datasets** — run the import scripts inside `Datasets/`
2. **Configure and launch the FQMA application** — configure `FQMA/config.py` and run the start script inside `FQMA/`

---

### Stage 1 — Import Datasets

#### Step 1.1 — Clone the repository

```bash
git clone https://github.com/douerlucky/FQMA.git
cd FQMA
```

#### Step 1.2 — Open the `Datasets` folder

<div align="center">
<img width="40%" alt="image1" src="https://github.com/user-attachments/assets/43ae2c6d-ec63-4ea0-9128-a595c0ab092e" />
<img width="40%" alt="image2" src="https://github.com/user-attachments/assets/28b06b62-9053-4185-8579-d22e321beed2" />
</div>

Navigate into the `Datasets/` directory. You will find:




```
Datasets/
├── GMQA/              ← raw data files for GMQA
├── RODI-Conf/         ← raw data files for RODI-C
├── import_GMQA.py     ← configure this
└── import_RODI.py     ← configure this
```

#### Step 1.3 — Configure database credentials in both import scripts

Open **`import_GMQA.py`** and **`import_RODI.py`** in any text editor and fill in your local database credentials at the top of each file. **Both files must be configured.**

<div align="center">
<img width="40%" alt="image" src="https://github.com/user-attachments/assets/4d980970-5920-4521-b074-2a3a2f935f30" />
<img width="40%" alt="image" src="https://github.com/user-attachments/assets/d925607b-fceb-4c87-9b61-4e2b6601b7f3" />
</div>

```python
# ── MySQL ──────────────────────────────────────────
MYSQL_HOST     = "localhost"       # keep as-is unless MySQL runs on another host
MYSQL_PORT     = 3306              # default MySQL port
MYSQL_USER     = "root"            # ← replace with your MySQL username
MYSQL_PASSWORD = "your_password"   # ← replace with your MySQL password

# ── PostgreSQL ─────────────────────────────────────
PG_HOST     = "localhost"
PG_PORT     = 5432
PG_USER     = "postgres"           # ← replace with your PostgreSQL username
PG_PASSWORD = "your_password"      # ← replace with your PostgreSQL password

# ── Neo4j ──────────────────────────────────────────
NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"           # ← replace with your Neo4j username
NEO4J_PASSWORD = "your_password"   # ← replace with your Neo4j password
```

> ⚠️ **Important:** Make the same changes to both `import_GMQA.py` and `import_RODI.py`. The credentials fields are identical in both files.

#### Step 1.4 — Run the import scripts

<div align="center">
  <img width="50%" alt="image" src="https://github.com/user-attachments/assets/f4fbd3c7-1d66-40bf-b946-783a0faa9684" />
</div>



Open a terminal **inside the `Datasets/` directory** and run:

```bash
python import_GMQA.py
python import_RODI.py
```

Each script will automatically create the required databases and import all tables/nodes. You will see a summary at the end showing which imports succeeded (✅) or failed (❌).

#### Step 1.5 — Verify the imported databases

After both scripts complete, confirm the following databases exist and have data:

| Backend    | Expected databases |
|------------|-------------------|
| MySQL      | `gutmdisorder`, `newgutmgene` (with `relationship` tables), `rodiConference` |
| PostgreSQL | `kegg`, `rodiConference` |
| Neo4j      | nodes and relationships visible in the Neo4j Browser |

<div align="center">
  <img width="25%" alt="image" src="https://github.com/user-attachments/assets/073f6124-944b-4f11-8be7-ede6ed19d61f" />
  <img width="25%" alt="image" src="https://github.com/user-attachments/assets/1fa1acf2-e9cf-40c2-a7df-fc9064216d4a" />
</div>

---

### Stage 2 — Configure and Launch FQMA

#### Step 2.1 — Open `FQMA/config.py`

<div align="center">
  <img width="40%" alt="image" src="https://github.com/user-attachments/assets/f69b449d-e27e-4ab0-8775-b4cf47329ae3" />
<img width="40%" alt="image" src="https://github.com/user-attachments/assets/b2c8b847-c716-4bd9-859d-4a5d91f7ca9a" />
</div>

Navigate into the `FQMA/` directory and open `config.py`. There are two sections you **must** configure.

**2.1a — Database credentials** (same values you used in the import scripts):

<div align="center">
<img width="50%" alt="image" src="https://github.com/user-attachments/assets/47b0cc9c-2390-4a12-9dff-8208a2565e75" />
</div>

```python
# MySQL
MySQL_user = 'root'           # ← your MySQL username
MySQL_pwd  = 'your_password'  # ← your MySQL password

# PostgreSQL
Postgre_user = 'postgres'     # ← your PostgreSQL username
Postgre_pwd  = 'your_password'# ← your PostgreSQL password

# Neo4j
Neo4j_user = 'neo4j'          # ← your Neo4j username
Neo4j_pwd  = 'your_password'  # ← your Neo4j password
```

**2.1b — LLM API key**

<div align="center">
  <img width="50%" alt="image" src="https://github.com/user-attachments/assets/aed2d20d-3ac3-4a70-a7f9-8ecbc07a8a35" />
</div>


Find the `MODEL_TYPE` setting and set it to the LLM provider you want to use. Then fill in the corresponding API key in the matching block below:

```python
MODEL_TYPE = "deepseek"  # options: "deepseek", "qwen", "gpt", "llama", "zhipu", "ollama"
```

For example, if using DeepSeek:

```python
elif MODEL_TYPE == "deepseek":
    os.environ['DEEPSEEK_API_KEY'] = 'sk-your-deepseek-api-key-here'  # ← your key
    model = ChatOpenAI(
        model="deepseek-chat",
        api_key=os.environ.get('DEEPSEEK_API_KEY'),
        base_url="https://api.deepseek.com/v1"
    )
```

Replace `'sk-your-deepseek-api-key-here'` with your actual key. The same pattern applies to all other providers (qwen, gpt, llama, zhipu).

**2.1c — Select the active dataset** (optional at first run):

```python
CURRENT_DATASET = "RODI"  # switch to "GMQA" to query the gut microbiota benchmark
```

---

#### Step 2.2 — Launch the application

<div align="center">
<img width="50%" alt="image" src="https://github.com/user-attachments/assets/463b065e-57fc-4fdb-bcd3-eca3898e0b82" />
</div>

Open a terminal **inside the `FQMA/` directory** and follow the instructions for your operating system.

---

## Launching on macOS

<div align="center">
<img width="50%" alt="image" src="https://github.com/user-attachments/assets/865def32-6d91-441a-888d-62a2afdba9c7" />
</div>

> ⚠️ **macOS-only prerequisite:** The FQMA web backend runs on port **5000**. On macOS Monterey and later, the system **AirPlay Receiver** service also occupies port 5000 by default, which will prevent the backend from starting.
>
> Before launching, go to **System Settings → General → AirDrop & Handoff** and **turn off "AirPlay Receiver"**.

<div align="center">
  <img width="50%" alt="image" src="https://github.com/user-attachments/assets/9ada0c84-6a4f-40b2-badf-93063c397350" />
</div>

```bash
# Inside the FQMA/ directory:
chmod +x start.sh
./start.sh
```

When prompted, choose your startup mode:

```
[1] Start Web Application (frontend + backend)
[2] Interactive command-line query (runs main.py directly)
```

The script will:

1. Verify Python 3.12 is available
2. Create a `.venv` virtual environment (first run only)
3. Install all dependencies from `requirements.txt` (first run only)
4. Check for Node.js and install frontend dependencies (first run only, ~2–5 min)
5. Start the Flask backend on port **5000**
6. Start the Vite frontend on port **5173**
7. Automatically open `http://localhost:5173` in your browser

To stop all services, press **Ctrl+C** in the terminal.

---

## Launching on Windows

Double-click `start.bat` inside the `FQMA/` folder, **or** run it from a Command Prompt:

```cmd
cd FQMA
start.bat
```

When prompted, choose your startup mode:

```
[1] Start Web Application (frontend + backend)
[2] Interactive command-line query (runs main.py directly)
```

The script will:

1. Verify Python 3.12 is available (checks `py -3.12`, `python3.12`, and `python`)
2. Create a `.venv` virtual environment (first run only)
3. Install all dependencies from `requirements.txt` (first run only)
4. Check for Node.js and install frontend dependencies (first run only, ~2–5 min)
5. Open a **FQMA-Backend** window running Flask on port **5000**
6. Open a **FQMA-Frontend** window running Vite on port **5173**
7. Automatically open `http://localhost:5173` in your browser

To stop all services, close the **FQMA-Backend** and **FQMA-Frontend** terminal windows.

> 💡 If Python 3.12 is not found, download it from [https://www.python.org/downloads/](https://www.python.org/downloads/) and make sure to check **"Add Python to PATH"** during installation.

---

## Command-line Usage (Both Platforms)

If the web interface is unavailable, you can query directly from the command line.

**Interactive mode** (loop — enter questions one at a time):

```bash
python main.py --interactive
# or shorthand:
python main.py -i
```

**Single question mode**:

```bash
python main.py --question "Find all authors who presented papers at the Benguela conference and return their names."
```

**Exit interactive mode** by typing `exit` or pressing Enter on an empty line.

---

## Reproducing Experiments

```bash
# Inside FQMA/:
python exp_framework_modified.py
```

Adjust `TEST_MODE`, `SELECTED_QUESTION_IDS`, and `CURRENT_DATASET` in `config.py` to control which questions are evaluated.

---

## Example Use Case

<div align="center">
<img width="50%" alt="image" src="https://github.com/user-attachments/assets/8635caef-750a-486c-bdc5-3e96d95dfb5b" />
</div>

> Query the member IDs of the committee with ID 1000, and obtain the corresponding email addresses as well as the first and last names of these members.

FQMA handles this by:

1. Decomposing the question into dependent subqueries
2. Generating ontology-aware SPARQL for each subquery
3. Repairing any semantic issues through iterative validation
4. Routing subqueries to Neo4j, MySQL, and PostgreSQL respectively
5. Aggregating the results into a unified answer table

---

## Configuration Reference

A summary of every value you need to set before running FQMA:

| File | Variable | Description |
|------|----------|-------------|
| `Datasets/import_GMQA.py` | `MYSQL_USER` / `MYSQL_PASSWORD` | MySQL credentials for dataset import |
| `Datasets/import_GMQA.py` | `PG_USER` / `PG_PASSWORD` | PostgreSQL credentials for dataset import |
| `Datasets/import_GMQA.py` | `NEO4J_USER` / `NEO4J_PASSWORD` | Neo4j credentials for dataset import |
| `Datasets/import_RODI.py` | Same fields as above | Must be configured separately |
| `FQMA/config.py` | `MySQL_user` / `MySQL_pwd` | MySQL credentials for query execution |
| `FQMA/config.py` | `Postgre_user` / `Postgre_pwd` | PostgreSQL credentials for query execution |
| `FQMA/config.py` | `Neo4j_user` / `Neo4j_pwd` | Neo4j credentials for query execution |
| `FQMA/config.py` | `MODEL_TYPE` | LLM provider (`deepseek`, `qwen`, `gpt`, etc.) |
| `FQMA/config.py` | API key inside model block | Your LLM API key for the chosen provider |
| `FQMA/config.py` | `CURRENT_DATASET` | Active benchmark: `"RODI"` or `"GMQA"` |

---

## Acknowledgement

This project is supported in part by the National Key Research and Development Program of China, the Hubei Key Research and Development Program of China, and the Major Project of Hubei Hongshan Laboratory.

---

## Contact

- GitHub: [@douerlucky](https://github.com/douerlucky)
- Email: douer_lucky@webmail.hzau.edu.cn

---

<div align="center">
  Made with care for clean, ontology-aware federated querying.
</div>
