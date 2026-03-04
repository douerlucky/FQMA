<div align="center">
  <h1>FQMA v2.0</h1>
  <p><strong>Ontology-based Federated Query Multi-Agent Framework</strong></p>
  <p><em>Produced by Huazhong Agricultural University</em></p>
  <p><em>A part of Huazhong Agricultural University Agents</em></p>

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

# Overview

In many application domains, researchers often need to retrieve valuable information from massive, heterogeneous, and distributed data sources to support complex analytical or decision-making tasks. Although existing Ontology-Based Data Access (OBDA) architecture promotes automation to a certain extent, the lack of support for natural language queries and the reliance on fixed query workflows make them inconvenient and inflexible. At the same time, current Natural Language Queries (NLQs) have low performance in joint queries within specific domains due to a lack of domain knowledge. 

To address these shortcomings, we propose **FQMA**, an Ontology-based Federated Query Multi-Agent framework. It utilizes domain ontologies alongside a novel iterative semantic repair algorithm to boost query accuracy. To the best of our knowledge, it is the first work to employ a multi-agent approach to accomplish federated queries over heterogeneous data sources in the OBDA paradigm.

You can see the video below to watch the whole pipeline:


https://github.com/user-attachments/assets/edf191d5-d9ea-4ba5-8e04-0f06367b31dd

<img width="10060" height="5632" alt="FQMA" src="https://github.com/user-attachments/assets/aafccfa1-560c-4140-b185-b3cbfcfc0b95" />


FQMA employs a **Plan-and-Solve (PS)** paradigm coordinated by four specialized agents. To understand how the framework bridges the gap between natural language and heterogeneous data, let’s analyze the execution of a typical complex query:

> **Example Query:** *"Query the member IDs of the committee with ID 1000, and obtain the corresponding email addresses as well as the first and last names of these members."*

The **Query Planning and Generation Agent** serves as the orchestrator by performing task decomposition on the natural language input. It recognizes that the request involves a dependency chain where member IDs must be extracted before retrieving personal details. Consequently, it translates the user's intent into a structured plan comprising:

Sub-query 1: Retrieve `memberID` from the committee with ID 1000 through the `conf:has_members` predicate.

Sub-query 2: Obtain the `firstName`, `lastName`, and `email` for the corresponding member IDs.

The **Semantic Query Repair Agent** ensures the validity of the generated SPARQL by applying an iterative repair algorithm. It cross-references the candidate queries with the domain ontology using predefined formal logic rules to identify and fix semantic inconsistencies. For instance, if the planner mistakenly generates an incorrect predicate not defined in the ontology, this agent automatically identifies the violation and substitutes it with the standardized term from the RODI or GMQA schema to ensure execution success.

The **Query Routing and Adaptation Agent** manages the interaction with heterogeneous backends by leveraging ontology mappings and transformation tools. It identifies that the committee relationship data and individual member attributes reside in different data sources, such as Neo4j for graph relationships and MySQL or PostgreSQL for relational data. By invoking specialized adapters, it transforms the ontology-level SPARQL into native query languages like Cypher or SQL while managing the physical connection routing to each distributed database.

The **Result Aggregation Agent** performs the final synthesis by collecting intermediate data streams from all involved backends. It executes a semantic join to align the results based on the shared member IDs, ensuring that the disparate information from graph and relational sources is accurately unified. Finally, the agent provides the user with a comprehensive response in two formats: a structured table for data analysis and an LLM-generated natural language summary for easier comprehension.

---

# Key Contributions

Our framework introduces three main contributions to the field:

* **Multi-Agent Architecture:** An ontology-based federated query multi-agent framework specifically designed for natural language queries over heterogeneous data sources. 
* **Semantic Repair Algorithm:** An ontology-driven iterative semantic query repair algorithm based on formal first-order logic validation rules combined with LLM evaluation, which further improves the execution accuracy of generated SPARQL queries. 
* **New Benchmarks:** The introduction of two ontology-based federated query benchmarks, including a reconstructed RODI-C question set (237 NLQs) and a newly constructed Gut Microbiota Question-Answer (GMQA) dataset (320 NLQs), on which FQMA achieves state-of-the-art FEX performance.


---

# Datasets
This repository provides two high-quality ontology-based federated query benchmarks (RODI-C, GMQA) and corresponding ontology/mapping resources for heterogeneous data source federated query research. All datasets support natural language query (NLQ) and dependency-aware multi-step federated query execution across relational (MySQL/PostgreSQL) and graph (Neo4j) databases.

## RODI-C
RODI-C is a **reconstructed heterogeneous federated benchmark** derived from the *Conference-native* scenario of the original RODI benchmark (a classic OBDA benchmark for relational-to-ontology mapping). The original RODI is a centralized PostgreSQL dataset; we re-distribute its data across **MySQL, PostgreSQL, and Neo4j** to simulate real-world heterogeneous federated data environments, and construct **237 natural language queries** for the reconstructed dataset.

### RODI-C Data Distribution Rule
- Text/attribute-centric content (abstracts, reviews) → MySQL
- Integrity-critical structured entities/core relations → PostgreSQL
- Relationship-centric information (authorship, committee membership) → Neo4j

### RODI-C Query Statistics
All queries are decomposed into 2–3 interdependent subqueries spanning multiple backends. Detailed statistics by query category are shown below (integrated with GMQA for comparison):

| Dataset | Category | Questions | Tables | Triples | Table Rows (Mean) | Table Rows (Range) | Table Columns (Range) |
| :------ | :------- | :-------- | :----- | :-----: | :---------------: | :----------------- | :------------------- |
| **RODI-C** | Paper metadata retrieval | 25 | 3 | 5 | 2.32 | 2–6 | 4–4 |
| | Paper abstract retrieval | 85 | 5 | 7 | 5.36 | 2–162 | 3–6 |
| | Review comment retrieval | 94 | 5 | 9 | 39.74 | 3–385 | 5–11 |
| | Author statistics retrieval | 2 | 3 | 3 | 268.50 | 252–285 | 7–7 |
| | Committee membership retrieval | 7 | 5 | 7 | 12.86 | 9–16 | 10–10 |
| | Committee contact retrieval | 17 | 4 | 7 | 18.47 | 8–73 | 5–10 |
| | Person profile retrieval | 7 | 4 | 7 | 279.71 | 214–362 | 7–7 |
| | **Total** | **237** | **27** | **147** | **30.16** | **2–385** | **3–11** |
| **GMQA** | Swine feeding efficiency | 99 | 7 | 15 | 19.87 | 2–80 | 5–8 |
| | Disease effects (human / murine) | 88 | 7 | 17 | 47.00 | 3–170 | 5–5 |
| | Food effects (human / murine) | 67 | 7 | 17 | 45.06 | 3–168 | 5–5 |
| | Drug effects (human / murine) | 66 | 7 | 17 | 42.14 | 13–144 | 5–5 |
| | **Total** | **320** | **86** | **179** | **37.20** | **2–170** | **5–8** |

## GMQA
GMQA (**Gut Microbiota Question-Answer**) is a **self-constructed domain-specific benchmark** for ontology-based federated querying in the gut microbiota field, addressing the lack of public federated query datasets for this domain. The dataset integrates multiple real-world biological resources deployed on heterogeneous backends and contains **320 complex natural language queries** decomposed into 3 interdependent subqueries.

### GMQA Data Sources
GMQA unifies heterogeneous biological databases with a custom gut microbiota ontology, covering the following core data sources:
- **GutMDisorder/GutMGene** (Relational): Microbiota-phenotype & microbiota-gene associations
- **PGMKG** (Graph): Swine gut microbiota and feeding efficiency relationships
- **KEGG** (Pathway KB): Gene-metabolic pathway knowledge

### GMQA Query Categories & Representative Examples
GMQA queries cover four typical research directions in gut microbiota studies, each corresponding to a specific combination of data sources and multi-step information needs:

| Query Category | Qty | Representative Natural Language Query | Corresponding Data Sources |
| :------------- | :-: | :----------------------------------- | :------------------------ |
| Disease effects (human / murine) | 88 | Which gut microbiota that show increased abundance in constipation can be reduced through host gene expression regulation, and what are the key metabolic pathways involved? | GutMDisorder, GutMGene, KEGG |
| Food effects (human / murine) | 67 | Which host genes can enhance the proliferation of specific gut microbiota induced by soluble corn fiber, and through which metabolic pathways do these genes exert their effects? | GutMDisorder, GutMGene, KEGG |
| Drug effects (human / murine) | 66 | Which host genes can upregulate the proliferation of specific gut microbiota induced by Metformin, and which glucose metabolism–microbiota co-regulatory pathways are activated? | GutMDisorder, GutMGene, KEGG |
| Swine feeding efficiency | 99 | (Domain-specific) Gut microbiota species associated with improved feed conversion ratio in swine, and their regulatory host genes/pathways | PGMKG, GutMGene, KEGG |

## Ontology & Mapping Resources
We provide complete ontology files (for RODI-C/GMQA) and **R2RML/ R2RML-style mapping rules** (TTL format) for all backend data sources, which are the core of the OBDA-based federated query framework. Mapping rules are generated via AI-assisted methods and manually refined for semantic correctness.

---

# Installation and Setup

The installation and display video are available here:

https://github.com/user-attachments/assets/35296116-0364-4c31-b310-2454760cacd1

The setup process has **two stages**:

1. **Import the datasets** — run the import scripts inside `Datasets/`
2. **Configure and launch the FQMA application** — configure `FQMA/config.py` and run the start script inside `FQMA/`

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




## Stage 1 — Import Datasets

### Step 1.1 — Clone the repository

```bash
git clone https://github.com/douerlucky/FQMA.git
cd FQMA
```

### Step 1.2 — Open the `Datasets` folder

<div align="center">
<img width="40%" alt="image1" src="https://github.com/user-attachments/assets/43ae2c6d-ec63-4ea0-9128-a595c0ab092e" />
<img width="40%" alt="image2" src="https://github.com/user-attachments/assets/28b06b62-9053-4185-8579-d22e321beed2" />
</div>

Navigate into the `Datasets/` directory. You will find:


### Step 1.3 — Configure database credentials in both import scripts

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

### Step 1.4 — Run the import scripts

<div align="center">
  <img width="50%" alt="image" src="https://github.com/user-attachments/assets/f4fbd3c7-1d66-40bf-b946-783a0faa9684" />
</div>



Open a terminal **inside the `Datasets/` directory** and run:

```bash
python import_GMQA.py
python import_RODI.py
```

Each script will automatically create the required databases and import all tables/nodes. You will see a summary at the end showing which imports succeeded (✅) or failed (❌).

### Step 1.5 — Verify the imported databases

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


## Stage 2 — Configure and Launch FQMA

### Step 2.1 — Open `FQMA/config.py`

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

### Step 2.2 — Launch the application

<div align="center">
<img width="50%" alt="image" src="https://github.com/user-attachments/assets/463b065e-57fc-4fdb-bcd3-eca3898e0b82" />
</div>

Open a terminal **inside the `FQMA/` directory** and follow the instructions for your operating system.

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


## Acknowledgement

This project is supported in part by the National Key Research and Development Program of China, the Hubei Key Research and Development Program of China, and the Major Project of Hubei Hongshan Laboratory.

## Contact

- GitHub: [@douerlucky](https://github.com/douerlucky)
- Email: douer_lucky@webmail.hzau.edu.cn


<div align="center">
  Made with care for clean, ontology-aware federated querying.
</div>
