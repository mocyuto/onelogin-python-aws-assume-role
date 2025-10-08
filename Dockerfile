FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy project configuration files
COPY pyproject.toml .python-version ./

# Copy source code
COPY src ./src

# Install the project and its dependencies
RUN uv sync --frozen --no-dev

# Install AWS CLI
RUN uv pip install awscli

# Create directory for config files
RUN mkdir -p /root/.onelogin

# Set the entrypoint to use uv run
ENTRYPOINT ["uv", "run"]
CMD ["onelogin-aws-assume-role", "--help"]
