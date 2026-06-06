<<<<<<< HEAD
# Personal AI OS

A local-first, lightweight multi-agent AI system acting as a user's second brain.

## Features

- **Manager Agent**: Standard intent classifier and routing coordinator.
- **Knowledge Agent**: FAISS-based semantic vector memory store backed by SQLite metadata database.
- **Planner Agent**: Personalized learning roadmaps and action plan generation utilizing user memory context.
- **Decision Agent**: Multi-criteria comparison matrices, pros/cons analysis, and recommendations utilizing user memory context.
- **Structured Logging & Rich Console UI**: Gorgeous console layout and panels using the Rich library.

## Setup Instructions

1. Ensure Python 3.12+ and `uv` are installed.
2. Initialize virtual environment:
   ```bash
   uv sync
   ```
3. Copy environment configuration and configure your LLM provider (`openai`, `gemini`, or `ollama`):
   ```bash
   cp .env.example .env
   ```
4. Run the app:
   ```bash
   uv run main.py
   ```
5. Run tests:
   ```bash
   uv run python -m unittest discover -s tests
   ```
=======
# Personalized-AI-Agent
>>>>>>> 09f6589a12ff4e5be47f3d937e050ebe6cd7aab8
