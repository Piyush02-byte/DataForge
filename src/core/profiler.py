import pandas as pd
import numpy as np


def infer_type(series):

    non_null=series.dropna()

    if len(non_null)==0:

        return "empty"


    if pd.api.types.is_numeric_dtype(series):

        return "numeric"


    unique_ratio=series.nunique()/max(len(non_null),1)

    if unique_ratio>0.9:

        return "identifier"

    if series.nunique()<=20:

        return "categorical"

    return "freetext"



def numeric_stats(series):

    desc=series.describe()

    return {

        "mean":float(desc["mean"]),

        "median":float(series.median()),

        "min":float(desc["min"]),

        "max":float(desc["max"])

    }



def profile_dataframe(df):

    profile={}

    for col in df.columns:

        series=df[col]

        col_type=infer_type(series)

        entry={

            "dtype":str(series.dtype),

            "inferred_type":col_type,

            "total":len(series),

            "non_null":int(series.notna().sum()),

            "null_count":int(series.isna().sum()),

            "null_pct":round(series.isna().mean()*100,2),

            "unique":int(series.nunique())

        }


        if col_type=="numeric":

            entry["stats"]=numeric_stats(series.dropna())

        else:

            entry["stats"]={}

        profile[col]=entry


    return profile