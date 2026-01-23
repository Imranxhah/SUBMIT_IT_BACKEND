# Deployment Guide for PythonAnywhere

## 1. Project Setup
1.  **Upload Code:** Push your code to GitHub and clone it into PythonAnywhere.
    ```bash
    git clone https://github.com/Imranxhah/SUBMIT_IT_BACKEND.git
    ```
2.  **Virtual Environment:**
    ```bash
    mkvirtualenv --python=/usr/bin/python3.10 submitit-env
    pip install -r requirements.txt
    ```

## 2. Configuration (`settings.py`)
1.  **Copy Settings:** Open `Submit_it/settings.py` on PythonAnywhere and replace its content with the code from `settings_for_deploy.py` (which I created in your project root).
2.  **Database:** Run migrations to set up the SQLite database.
    ```bash
    python manage.py migrate
    ```
3.  **Static Files:** Run this command to collect all static files (fonts, admin styles) into one folder.
    ```bash
    python manage.py collectstatic
    ```

## 3. Environment Variables
You must set these sensitive values. You can do this in the **WSGI configuration file** (found in the "Web" tab) or by using a `.env` file if you stick with `load_dotenv()`.

**Recommended: Add to WSGI file**
In the "Web" tab, click your WSGI file link (e.g., `/var/www/submitit_pythonanywhere_com_wsgi.py`) and add this **before** `from django.core.wsgi import ...`:

```python
import os
os.environ['GROQ_API_KEY'] = 'your_actual_groq_api_key_here'
os.environ['DJANGO_SECRET_KEY'] = 'your_new_random_secret_key'
os.environ['EMAIL_HOST_USER'] = 'your_email@gmail.com'
os.environ['EMAIL_HOST_PASSWORD'] = 'your_app_password'
```

## 4. Static & Media Files (Web Tab)
Go to the **Web** tab in PythonAnywhere Dashboard and verify these settings under **"Static files"**:

| URL | Directory |
| :--- | :--- |
| `/static/` | `/home/submitit/SUBMIT_IT_BACKEND/staticfiles` |
| `/media/` | `/home/submitit/SUBMIT_IT_BACKEND/media` |

*(Note: Verify the actual path using `pwd` in your console. It might be different if your folder name is different.)*

## 5. Potential Issues & Limitations

### Tesseract OCR (Image to Text)
**Warning:** PythonAnywhere does **not** have Tesseract installed by default, and you cannot install it with `apt-get` on a standard account. 
*   **Impact:** The feature that extracts text from **Images (.png, .jpg)** in `assignments/utils.py` will fail.
*   **Behavior:** Your code has a `try-except` block, so it won't crash. It will just return an error message in the text: `[Error processing image: ...]`.
*   **Solution:** For full OCR capability, you would need a VPS (like DigitalOcean, AWS EC2) or a Docker-based host (Render, Railway) where you can install `tesseract-ocr`. For now, on PythonAnywhere, PDF and Text file extraction will work fine, but Images will not.

### WeasyPrint (PDF Generation)
`WeasyPrint` also relies on system libraries (`libcairo`, `libpango`). PythonAnywhere usually has these installed, so PDF generation **should work**. If you see errors related to `dlopen` or missing libraries, you might need to ask PythonAnywhere support if they can enable them for your image.

## 6. Restart
After making these changes, go to the **Web** tab and click the big green **Reload** button.
