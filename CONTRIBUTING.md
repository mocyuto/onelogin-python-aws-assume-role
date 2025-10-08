# Contributing to onelogin-python-aws-cli-assume-role

## Development Setup

1. Install uv:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone and setup:
   ```bash
   git clone <your-fork-url>
   cd onelogin-python-aws-assume-role
   uv sync
   ```

3. Make changes and test:
   ```bash
   # Run tests
   uv run pytest

   # Check code quality
   uv run ruff check src/

   # Format code
   uv run ruff format src/
   ```

## Adding Features, Pull Requests
* Fork the repository
* Make your feature addition or bug fix
* Add tests for your new features. This is important so we don't break any features in a future version unintentionally.
* Ensure all tests pass.
* Open a pull request, you can use [this template](https://gist.github.com/Lordnibbler/11002759) as example.

## Security Guidelines

If you believe you have discovered a security vulnerability in this gem, please report it at https://www.onelogin.com/security with a description. We follow responsible disclosure guidelines, and will work with you to quickly find a resolution.
