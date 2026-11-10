# Contributing to Pi-hole Social Control

Thank you for considering contributing! We welcome bug fixes, documentation improvements, and new features.

## Getting Started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/<your-username>/social-block.git
   cd social-block
   ```
3. **Create a virtual environment** and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. **Copy the example environment configuration**:
   ```bash
   cp .env.example .env
   ```

## Running Tests

Run the test suite using `unittest`:
```bash
python -m unittest discover tests
```

Or via Docker:
```bash
docker build -t pihole-social-control:test .
docker run --rm pihole-social-control:test python -m unittest discover tests
```

## Pull Request Guidelines

1. Create a new branch with a meaningful name (`git checkout -b feat/schedule-blocking`).
2. Make your changes and commit with clear, descriptive commit messages.
3. Ensure all tests pass.
4. Push your branch to GitHub and open a Pull Request against `main`.
5. Provide a summary of changes in the PR description using the template.
