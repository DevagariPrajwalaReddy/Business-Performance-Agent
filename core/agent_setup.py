import os
from dotenv import load_dotenv

#from langchain_openrouter import ChatOpenRouter
from langchain_litellm import ChatLiteLLM
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent

from core.data_loader import load_data
from core.prompt import PREFIX_TEMPLATE

load_dotenv()

# Load Data
df = load_data()

# Dataset Metadata
max_data_date = df['orderdate'].max().date()
min_data_date = df['orderdate'].min().date()

# Build Prompt
PREFIX = PREFIX_TEMPLATE.format(
    max_data_date=max_data_date,
    min_data_date=min_data_date,
    columns=', '.join(df.columns)
)

# Initialize LLM
llm = ChatLiteLLM(
    model="gemini/gemini-3.1-flash-lite",
    api_key=os.getenv("GEMINI_API_KEY"),
    n=1,
    temperature=0,
    fallbacks=[
        {
            "model": "groq/llama-3.3-70b-versatile",  # Fallback (high limit)
            "api_key": os.getenv("GROQ_API_KEY")
        }
    ]
)

_agent = None

# Create Agent (built once and reused; Streamlit re-runs this script on every message)
def get_agent():
    global _agent
    if _agent is None:
        _agent = create_pandas_dataframe_agent(
            llm=llm,
            df=df,
            verbose=True,
            allow_dangerous_code=True,
            prefix=PREFIX,
            include_df_in_prompt=False,
            engine="pandas",
            max_iterations=5,
            early_stopping_method="generate",
            agent_executor_kwargs={
                "handle_parsing_errors": "Check your output format and ensure 'Action:' is followed by 'Action Input:'"
            }
        )
    return _agent