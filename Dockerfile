# Digest-pinned for reproducible sandbox builds (tag kept for readability).
FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203

# uv builds per-library venvs; pytest is needed in the base interpreter so
# stdlib cells (which run under base python, not a venv) can execute the tests.
RUN pip install --no-cache-dir uv pytest && useradd -m -u 1000 sandbox

WORKDIR /app
COPY agentic_fit /app/agentic_fit

# Create the venv-cache dir owned by the non-root user. When an empty named
# volume is first mounted here, Docker initializes it from this dir (preserving
# ownership), so the sandbox user can write venvs into the volume.
RUN mkdir -p /app/.cache/venvs && chown -R sandbox:sandbox /app

USER sandbox
ENTRYPOINT ["python", "-m", "agentic_fit.sandbox_runner"]
