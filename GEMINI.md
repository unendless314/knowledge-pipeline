# GEMINI.md - Knowledge Pipeline Context

This file provides instructional context for the Knowledge Pipeline project, used by Gemini CLI for development and maintenance.

## Project Overview

**Knowledge Pipeline** is an automation tool that bridges **YouTube Transcriber** (upstream) and **Open Notebook** (downstream). It processes raw transcripts, performs semantic analysis using LLMs, and uploads the structured knowledge to a local Open Notebook instance.

### Core Technologies
- **Language**: Python 3.10+
- **LLM Provider**: Google Gemini CLI (via `gemini` command)
- **API**: Open Notebook REST API (localhost:5055)
- **Data Format**: Markdown with YAML frontmatter
- **Configuration**: YAML (`config/*.yaml`)

### Key Components
- **Discovery**: Scans for new transcripts in the transcriber output directory.
- **Analyzer**: Sends content to Gemini CLI to extract summaries, topics, and entities.
- **Uploader**: Sends the analyzed Markdown to Open Notebook.
- **State Management**: Tracks file status (e.g., `pending`, `uploaded`) within the file's frontmatter.

---

## Building and Running

### Environment Setup
1. **Python Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configuration**:
   Copy example configs if they don't exist:
   ```bash
   cp config/config.yaml.example config/config.yaml
   cp config/topics.yaml.example config/topics.yaml
   ```

### Execution Commands
The main entry point is `run.py`.

### Environment Variables
- `OPEN_NOTEBOOK_PASSWORD`: Password for Open Notebook API authentication.
- `TRANSCRIBER_OUTPUT_PATH`: (Optional) Override for input transcript path.
- `INTERMEDIATE_PATH`: (Optional) Override for intermediate storage path.

- **Run Full Pipeline**:
  ```bash
  python run.py run
  ```
- **Test Mode (Dry Run)**:
  ```bash
  python run.py run --dry-run
  ```
- **Process Specific Channel**:
  ```bash
  python run.py run --channel "Bankless"
  ```
- **Sub-commands**:
  - `python run.py discover`: Only scan for new files.
  - `python run.py analyze`: Only perform AI analysis on pending files.
  - `python run.py upload`: Only upload analyzed files.

---

## Development Conventions

### Code Structure
- `src/`: Core logic and service implementations.
  - `llm/`: LLM provider abstraction layer.
  - `models.py`: Type-safe data structures (dataclasses).
- `prompts/analysis/`: Markdown templates for LLM instructions.
- `intermediate/`: Directory for files in various stages of processing.
- `docs/interfaces/`: Interface definitions and unit tests.

### Coding Style
- **Type Hinting**: Required for all function signatures and class members.
- **Docstrings**: Google-style docstrings (in Traditional Chinese, as per current codebase).
- **Error Handling**: Custom exceptions defined in `src/llm/exceptions.py` and module-specific classes.

### Testing
Tests are located in `docs/interfaces/tests/`. Run them using `pytest`:
```bash
pytest docs/interfaces/tests/
```

### State Management
The system relies on the `status` field in the Markdown frontmatter:
- `discovered`: Found but not yet analyzed.
- `pending`: Analyzed by LLM, stored in `intermediate/pending/`.
- `uploaded`: Successfully pushed to Open Notebook, moved to `intermediate/approved/`.

---

## Key Files Reference
- `src/main.py`: CLI implementation and pipeline orchestration.
- `src/llm/gemini_cli.py`: Integration with the `gemini` command.
- `config/topics.yaml`: Routing logic from channels/topics to specific Notebooks.
- `docs/architecture.md`: Detailed system design and data flow.
