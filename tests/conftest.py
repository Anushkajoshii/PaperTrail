import os

# Skip iCloud Drive conflict copies such as "test_x 2.py" if they ever appear.
collect_ignore_glob = ["* [0-9].py"]

# Tests always run offline with the mock LLM, whatever a developer's local .env says
# (environment variables take priority over .env).
os.environ["PAPERTRAIL_LLM_PROVIDER"] = "mock"
os.environ["PAPERTRAIL_SEARCH_PROVIDER"] = "offline"
os.environ["PAPERTRAIL_ENV"] = "test"
for _name in ("PAPERTRAIL_SSM_SECRETS_PATH", "PAPERTRAIL_WEB_DIST_DIR"):
    os.environ.pop(_name, None)
