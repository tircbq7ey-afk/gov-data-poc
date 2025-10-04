# -*- coding: utf-8 -*-
"""
report_eval.py
answers_A.csv / answers_B.csv / logs.csv から A/B の品質を集計し、
PNG 図と XLSX レポートを出力します。

設計方針:
- ファイルの列名が多少違っても動くように "q", "question", "query" を q 列に正規化。
- "answer" 列が無い場合は空文字として扱う。
- "results" 列に JSON っぽい文字列があればパースし nDCG@k を推定（score を関連度とみなす）。
- カバレッジ(coverage_score) はクエリ語の出現率（ゆるめの正規化）。
- ログは logs.csv に "evt", "helpful" などがあれば活用（無ければスキップ）。
"""

import argparse
import json
import math
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ===== ユーティリティ =====

QUERY_COL_CANDIDATES = ["q", "question", "query", "prompt"]
ANSWER_COL_CANDIDATES = ["answer", "ans", "response", "output"]
RESULTS_COL_CANDIDATES = ["results", "search_results", "hits", "docs"]

URL_RE = re.compile(r"https?://[^\s)]+", re.IGNORECASE)

def find_col(df: pd.DataFrame, cands):
    for c in cands:
        if c in df.columns:
            return c
        # 大文字小文字ゆらぎ
        low = {col.lower(): col for col in df.columns}
        if c.lower() in low:
            return low[c.lower()]
    return None

def normalize_text(s: str) -> str:
    if not isinstance(s, str):
        return ""
    # 全角空白→半角、改行→空白、重複空白の圧縮
    s = s.replace("\u3000", " ").replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def tokenize_ja_en(s: str):
    """超簡易トークナイザ（スペース/句読点/記号で分割）。日本語はユニグラム近似。"""
    if not s:
        return []
    # URL除去してから
    s = URL_RE.sub(" ", s)
    # 記号で分割
    s = re.sub(r"[、。,.!?:;()\[\]{}\"'“”’・/\\\-|]+", " ", s)
    s = normalize_text(s)
    toks = s.split(" ")
    toks = [t for t in toks if t]
    # 日本語が続く場合はユニグラム化して数を底上げ（クエリ側に効く）
    out = []
    for t in toks:
        if re.search(r"[ぁ-んァ-ヶ一-龠]", t):
            out.extend(list(t))
        else:
            out.append(t.lower())
    return out

def per_row_metrics(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """q / answer / results を元に行単位のメトリクスを付与。"""
    df = df.copy()

    qcol = find_col(df, QUERY_COL_CANDIDATES) or "q"
    if qcol not in df.columns:
        raise ValueError(f"{name}: クエリ列が見つかりません（候補: {QUERY_COL_CANDIDATES}）")
    acol = find_col(df, ANSWER_COL_CANDIDATES) or "answer"
    if acol not in df.columns:
        df[acol] = ""

    rcol = find_col(df, RESULTS_COL_CANDIDATES)

    # 正規化版
    df["q_norm"] = df[qcol].map(normalize_text)
    df["answer_norm"] = df[acol].map(normalize_text)

    # 長さなど
    df["answer_len"] = df["answer_norm"].str.len().fillna(0)
    df["num_urls"] = df["answer_norm"].map(lambda s: 0 if not s else len(URL_RE.findall(s)))
    df["has_bullet"] = df["answer_norm"].str.contains(r"・|- |\* ", regex=True).fillna(False)

    # カバレッジ: クエリトークンが answer に何割出たか
    def cov(row):
        q_toks = set(tokenize_ja_en(row["q_norm"]))
        if not q_toks:
            return 0.0
        a = row["answer_norm"]
        if not a:
            return 0.0
        score = 0
        for t in q_toks:
            if t and t in a:
                score += 1
        return score / max(1, len(q_toks))
    df["coverage_score"] = df.apply(cov, axis=1)

    # nDCG@k: results に [{"score": x}, ...] がある前提（壊れてても頑張ってパース）
    def try_parse_results(x):
        if rcol is None:
            return None
        val = df.at[x, rcol]
        if not isinstance(val, str) or len(val) < 2:
            return None
        # JSONに見えなければ緩く抽出
        try:
            obj = json.loads(val)
            if isinstance(obj, list):
                return obj
        except Exception:
            # ; 区切り/簡易辞書風などを救出
            return None
        return None

    k = 5
    rel_col = "ndcg@5"
    ndcgs = []
    if rcol is not None:
        for i in range(len(df)):
            items = try_parse_results(i)
            if not items:
                ndcgs.append(np.nan)
                continue
            # relevance として score を使う（負値なし前提）
            scores = []
            for it in items[:k]:
                try:
                    s = float(it.get("score", 0.0))
                except Exception:
                    s = 0.0
                scores.append(max(0.0, s))
            if not scores:
                ndcgs.append(np.nan)
                continue
            # DCG
            dcg = 0.0
            for j, s in enumerate(scores, start=1):
                dcg += (s / math.log2(j + 1))
            # iDCG
            ideal = sorted(scores, reverse=True)
            idcg = 0.0
            for j, s in enumerate(ideal, start=1):
                idcg += (s / math.log2(j + 1))
            ndcgs.append(dcg / idcg if idcg > 0 else np.nan)
        df[rel_col] = ndcgs
    else:
        df[rel_col] = np.nan

    # 出力列の標準化
    std_cols = [("q", qcol), ("answer", acol)]
    for std, real in std_cols:
        if std != real:
            df.rename(columns={real: std}, inplace=True)

    df["source_file"] = name
    return df

def summary_metrics(df: pd.DataFrame) -> dict:
    ok_ratio = (df["answer"].str.len() > 0).mean()
    return {
        "count": int(len(df)),
        "answer_nonempty%": round(ok_ratio * 100, 1),
        "avg_answer_len": round(df["answer_len"].mean(), 1),
        "median_answer_len": float(df["answer_len"].median()),
        "avg_num_urls": round(df["num_urls"].mean(), 2),
        "has_bullet%": round(df["has_bullet"].mean() * 100, 1),
        "avg_coverage": round(df["coverage_score"].mean(), 3),
        "avg_ndcg@5": round(df["ndcg@5"].mean(skipna=True), 3),
    }

def load_logs(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8")
    # helpful フラグがあれば集計
    lc = {c.lower(): c for c in df.columns}
    helpful = None
    for c in ["helpful","is_helpful","good"]:
        if c in lc:
            helpful = lc[c]
            break
    if helpful:
        df["helpful"] = df[helpful].astype(str).str.lower().isin(["1","true","yes","y"])
    return df

def write_excel(summary: pd.DataFrame, A: pd.DataFrame, B: pd.DataFrame, pair: pd.DataFrame, out: Path):
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="summary", index=False)
        A.to_excel(xw, sheet_name="A_details", index=False)
        B.to_excel(xw, sheet_name="B_details", index=False)
        pair.to_excel(xw, sheet_name="pair_compare", index=False)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

# ===== メイン =====

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="answers_A.csv")
    ap.add_argument("--b", required=True, help="answers_B.csv")
    ap.add_argument("--logs", default="logs.csv")
    ap.add_argument("--out_xlsx", default="eval_report.xlsx")
    ap.add_argument("--charts_dir", default="charts")
    args = ap.parse_args()

    root = Path.cwd()
    A_path = (root / args.a).resolve()
    B_path = (root / args.b).resolve()
    logs_path = (root / args.logs).resolve()

    if not A_path.exists() or not B_path.exists():
        raise FileNotFoundError("answers_A.csv / answers_B.csv のパスを確認してください。")

    # CSV 読み込み（BOM対応）
    def read_csv_any(p: Path) -> pd.DataFrame:
        for enc in ["utf-8-sig","utf-8"]:
            try:
                return pd.read_csv(p, encoding=enc)
            except Exception:
                continue
        # 最後の手段
        return pd.read_csv(p, encoding_errors="ignore")

    A_raw = read_csv_any(A_path)
    B_raw = read_csv_any(B_path)

    A = per_row_metrics(A_raw, "A")
    B = per_row_metrics(B_raw, "B")

    # 主要KPIサマリ
    A_sum = summary_metrics(A); B_sum = summary_metrics(B)
    summary_df = pd.DataFrame([
        {"metric": k, "A": A_sum[k], "B": B_sum[k], "delta(B-A)": round(B_sum[k]-A_sum[k], 3) if isinstance(B_sum[k], (int,float)) and isinstance(A_sum[k], (int,float)) else "" }
        for k in ["count","answer_nonempty%","avg_answer_len","median_answer_len","avg_num_urls","has_bullet%","avg_coverage","avg_ndcg@5"]
    ])

    # ペア比較（q をキーに結合）
    pair_cols = ["q","answer_len","coverage_score","ndcg@5"]
    pair = pd.merge(
        A[["q","answer","answer_len","coverage_score","ndcg@5"]],
        B[["q","answer","answer_len","coverage_score","ndcg@5"]],
        on="q", suffixes=("_A","_B"), how="outer"
    )
    pair["len_delta_B-A"] = pair["answer_len_B"] - pair["answer_len_A"]
    pair["cov_delta_B-A"] = pair["coverage_score_B"] - pair["coverage_score_A"]
    pair["ndcg_delta_B-A"] = pair["ndcg@5_B"] - pair["ndcg@5_A"]

    # ログ集計（あれば）
    logs_df = load_logs(logs_path)
    if not logs_df.empty and "helpful" in logs_df.columns:
        helpful_rate = round(logs_df["helpful"].mean()*100,1)
        summary_df.loc[len(summary_df)] = {"metric":"helpful_rate%(logs)","A":"","B":"","delta(B-A)":helpful_rate}
    # 図の出力
    charts_dir = root / args.charts_dir
    ensure_dir(charts_dir)

    # 1) 概要バー
    fig = plt.figure(figsize=(8,4))
    metrics = ["answer_nonempty%","avg_coverage","avg_ndcg@5","avg_answer_len"]
    A_vals = [A_sum[m] for m in metrics]
    B_vals = [B_sum[m] for m in metrics]
    x = np.arange(len(metrics))
    w = 0.35
    plt.bar(x-w/2, A_vals, width=w, label="A")
    plt.bar(x+w/2, B_vals, width=w, label="B")
    plt.xticks(x, metrics, rotation=15)
    plt.title("A vs B summary")
    plt.legend()
    plt.tight_layout()
    (charts_dir / "summary_bar.png").unlink(missing_ok=True)
    plt.savefig(charts_dir / "summary_bar.png", dpi=150)
    plt.close(fig)

    # 2) 長さヒスト
    for name, df in [("A", A), ("B", B)]:
        fig = plt.figure(figsize=(6,4))
        plt.hist(df["answer_len"].dropna(), bins=20)
        plt.title(f"Answer length histogram ({name})")
        plt.xlabel("length")
        plt.ylabel("count")
        plt.tight_layout()
        plt.savefig(charts_dir / f"len_hist_{name}.png", dpi=150)
        plt.close(fig)

    # 3) カバレッジ vs 長さ
    fig = plt.figure(figsize=(6,4))
    plt.scatter(A["answer_len"], A["coverage_score"], alpha=0.5, label="A")
    plt.scatter(B["answer_len"], B["coverage_score"], alpha=0.5, label="B")
    plt.xlabel("answer_len"); plt.ylabel("coverage_score")
    plt.legend(); plt.tight_layout()
    plt.savefig(charts_dir / "coverage_scatter.png", dpi=150)
    plt.close(fig)

    # Excel書き出し
    out_xlsx = root / args.out_xlsx
    write_excel(summary_df, A, B, pair, out_xlsx)

    print(f"[OK] wrote: {out_xlsx}")
    print(f"[OK] charts: {charts_dir}")

if __name__ == "__main__":
    main()
