import chardet
import pandas as pd
import csv


def detect_encoding(filepath):

    with open(filepath,"rb") as f:

        raw=f.read(50000)

    result=chardet.detect(raw)

    encoding=result.get("encoding") or "utf-8"

    if encoding.lower()=="ascii":

        encoding="utf-8"

    return encoding



def detect_delimiter(filepath,encoding):

    with open(filepath,"r",encoding=encoding,errors="replace") as f:

        sample=f.read(4000)

    try:

        dialect=csv.Sniffer().sniff(sample,delimiters=",;\t|")

        return dialect.delimiter

    except:

        return ","


def load_csv(filepath):

    try:
        encoding = detect_encoding(filepath)
        delimiter = detect_delimiter(filepath, encoding)

        df = pd.read_csv(
            filepath,
            encoding=encoding,
            encoding_errors="replace",
            sep=delimiter,
            skip_blank_lines=True,
            on_bad_lines="warn",
        )

        df.columns = [str(c).strip() for c in df.columns]

        unnamed = [c for c in df.columns if c.startswith("Unnamed:")]
        if unnamed:
            df = df.drop(columns=unnamed)

        meta = {
            "encoding": encoding,
            "delimiter": delimiter,
            "original_rows": len(df),
            "original_cols": len(df.columns),
        }

        return {"success": True, "df": df, "meta": meta, "error": None}

    except Exception as exc:
        return {"success": False, "df": None, "meta": {}, "error": str(exc)}