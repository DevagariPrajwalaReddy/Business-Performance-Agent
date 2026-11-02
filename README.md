# Business Performance AI Analyst

An AI chat app that answers business questions about sales data, such as quarterly performance, YoY growth and top customers.
Built with Streamlit, LangChain, LiteLLM (Gemini with a Groq fallback) and pandas.

## Run Locally

```bash
# Create virtual environment
python -m venv venv

# Activate environment
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up Environment variables
copy .env.example .env
notepad .env

# Run the app
streamlit run app/app.py
```

Open: http://localhost:8501
