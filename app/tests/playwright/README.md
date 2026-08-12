# Playwright main page tests

These tests drive the main app pages in Firefox and Chromium through Playwright.

Install the test dependencies:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m playwright install firefox chromium
```

Start the Flask app in another terminal:

```bash
cd ..
python3 run.py
```

Run the browser tests from the app directory:

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5000 pytest
```

Firefox and Chromium are the default browsers via `pytest.ini`. To run only one
browser during local development, pass it explicitly:

```bash
pytest --browser firefox
```

To include WebKit as well, install it and pass it explicitly:

```bash
python3 -m playwright install webkit
pytest --browser firefox --browser chromium --browser webkit
```
