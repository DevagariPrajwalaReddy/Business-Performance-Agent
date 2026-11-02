import pandas as pd


def load_data():

    df = pd.read_csv(
        "data/sales_data_sample.csv",
        encoding="latin1"
    )

    # Clean column names
    df.columns = [
        c.lower().replace(" ", "_")
        for c in df.columns
    ]

    # Convert dates
    if 'orderdate' in df.columns:
        df['orderdate'] = pd.to_datetime(df['orderdate'])

    return df