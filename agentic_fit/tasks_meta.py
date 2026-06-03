"""Per-category one-line summaries shown by `agentic-fit tasks` and the showcase site."""
from __future__ import annotations

SUMMARIES: dict[str, str] = {
    "cli_parsing": "Parse two command-line options: a required --name and an integer --count with a default.",
    "data_validation": "Validate and coerce a user record, converting a numeric age and raising on missing or invalid fields.",
    "date_handling": "Parse a human date/time string and return it as an ISO-8601 UTC string, raising on bad input.",
    "http_client": "Perform an HTTP GET, parse the JSON body, return its name field, and raise on a non-200 status.",
    "retrying": "Call a function with up to three retry attempts on failure, re-raising once they are exhausted.",
    "templating": "Render a title and a list of items to a formatted string using a templating library.",
    "yaml_config": "Parse two YAML documents and deep-merge them recursively, with override values winning conflicts.",
}
