# src/core/reporter.py
"""
Reporter
--------
Responsibility: Format and assemble the final analysis report from pipeline outputs.
                Imports scoring logic from quality_scorer — never redefines it.
                Returns structured data only. No printing. No side effects.
"""

import html
from datetime import datetime
from pathlib import Path

import pandas as pd
from src.config import REPORT_CONFIG


def generate_report(
    df_original: pd.DataFrame,
    df_cleaned:  pd.DataFrame,
    profile:     dict,
    quality:     dict,
    score:       dict,
    suggestions: dict,
    clean:       dict,
    coercion:    dict,
    config:      dict = None,
) -> dict:
    """
    Assemble all pipeline outputs into a unified report dict.

    Returns:
        {
            "overview":           dict,
            "quality_score":      dict,
            "column_profiles":    list[dict],
            "quality_issues":     list[dict],
            "suggestions":        list[dict],
            "cleaning_summary":   dict,
            "coercion_summary":   dict,
        }
    """
    cfg = config or REPORT_CONFIG

    issues_list = _build_issues_section(quality)
    critical_count = sum(
        1 for i in issues_list if (i.get("severity") or "").lower() == "critical"
    )

    report = {
        "overview":         _build_overview(df_original, df_cleaned),
        "quality_score":    _build_score_section(score, critical_count),
        "column_profiles":  _build_column_profiles(profile, cfg),
        "quality_issues":   issues_list,
        "suggestions":      _build_suggestions_section(suggestions),
        "cleaning_summary": _build_cleaning_summary(clean) if cfg.get("show_cleaning_summary") else {},
        "coercion_summary": _build_coercion_summary(coercion),
    }

    return report


# ─────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────

def _build_overview(df_original: pd.DataFrame, df_cleaned: pd.DataFrame) -> dict:
    return {
        "original_shape":  {"rows": len(df_original), "columns": len(df_original.columns)},
        "cleaned_shape":   {"rows": len(df_cleaned),  "columns": len(df_cleaned.columns)},
        "rows_removed":    len(df_original) - len(df_cleaned),
        "cols_removed":    len(df_original.columns) - len(df_cleaned.columns),
        "original_columns": df_original.columns.tolist(),
        "final_columns":    df_cleaned.columns.tolist(),
    }


def _compute_grade(score, critical_count: int = 0) -> str:
    """Map numeric score and critical issue count to a report grade."""
    if critical_count > 0:
        return "CRITICAL"
    try:
        score_num = float(score)
    except (TypeError, ValueError):
        return "—"
    if score_num >= 95:
        return "A+ (Excellent)"
    if score_num >= 90:
        return "A (Very Good)"
    if score_num >= 80:
        return "B (Good)"
    if score_num >= 70:
        return "C (Fair)"
    if score_num >= 60:
        return "D (Poor)"
    return "F (Critical)"


def _compute_status(score, critical_count: int = 0) -> str:
    """Map numeric score and critical issue count to a report status."""
    if critical_count > 0:
        return "ACTION REQUIRED"
    try:
        score_num = float(score)
    except (TypeError, ValueError):
        score_num = 0.0
    if score_num >= 90:
        return "HEALTHY"
    if score_num >= 80:
        return "REVIEW"
    return "NEEDS ATTENTION"


def _build_score_section(score: dict, critical_count: int = 0) -> dict:
    """Pass-through score/breakdown; grade accounts for critical issues."""
    raw_score = score.get("score")
    return {
        "score":      raw_score,
        "grade":      _compute_grade(raw_score, critical_count),
        "breakdown":  score.get("breakdown", {}),
    }


def _build_column_profiles(profile: dict, cfg: dict) -> list:
    max_samples = cfg.get("max_sample_values", 5)
    result = []

    for col, stats in profile.items():   # profile IS the columns dict
        entry = {
            "column":       col,
            "dtype":        stats.get("dtype"),
            "null_count":   stats.get("null_count"),
            "null_ratio":   stats.get("null_pct", 0) / 100,  # convert % to ratio
            "unique_count": stats.get("unique"),
            "sample_values": [],
        }
        numeric_stats = stats.get("stats", {})
        if numeric_stats:
            entry.update({
                "mean":   numeric_stats.get("mean"),
                "median": numeric_stats.get("median"),
                "min":    numeric_stats.get("min"),
                "max":    numeric_stats.get("max"),
            })
        result.append(entry)

    return result


def _build_issues_section(quality) -> list:
    if isinstance(quality, list):
        return quality
    if isinstance(quality, dict):
        return quality.get("issues", [])
    return []


def _build_suggestions_section(suggestions) -> list:
    if isinstance(suggestions, list):
        return suggestions
    if isinstance(suggestions, dict):
        return suggestions.get("suggestions", [])
    return []


def _build_cleaning_summary(clean: dict) -> dict:
    filter_res  = clean.get("filter_result", {})
    missing_res = clean.get("missing_result", {})

    dropped_cols = filter_res.get("dropped_columns", [])
    missing_actions = missing_res.get("actions", [])

    # Bucket missing value actions by type
    filled_cols = [a for a in missing_actions if "filled" in a.get("action", "")]
    dropped_row_actions = [a for a in missing_actions if a.get("action") == "drop_rows"]
    flagged_cols = [a for a in missing_actions if a.get("action") == "flagged"]
    skipped_cols = [a for a in missing_actions if a.get("action") == "skipped"]

    return {
        "columns_dropped": {
            "count": len(dropped_cols),
            "detail": dropped_cols,
        },
        "columns_retained": {
            "count": len(filter_res.get("retained_columns", [])),
            "names": filter_res.get("retained_columns", []),
        },
        "missing_values": {
            "columns_filled":  len(filled_cols),
            "columns_flagged": len(flagged_cols),
            "columns_skipped": len(skipped_cols),
            "rows_dropped":    missing_res.get("rows_dropped", 0),
            "detail":          missing_actions,
        },
    }


def _build_coercion_summary(coercion: dict) -> dict:
    changes = coercion.get("changes", [])
    errors  = coercion.get("errors", [])

    by_type = {}
    for c in changes:
        cast_type = c.get("cast_type", "unknown")
        by_type.setdefault(cast_type, []).append(c["column"])

    return {
        "columns_cast":   len(changes),
        "cast_errors":    len(errors),
        "by_type":        by_type,     # {"numeric": [...], "datetime": [...], "bool": [...]}
        "detail_changes": changes,
        "detail_errors":  errors,
    }


def _h(s) -> str:
    return html.escape("" if s is None else str(s))


def _severity_class(sev: str) -> str:
    s = (sev or "").lower()
    if s == "critical":
        return "sev-crit"
    if s == "warning":
        return "sev-warn"
    if s == "high":
        return "sev-warn"
    if s == "medium":
        return "sev-med"
    if s == "low":
        return "sev-low"
    return "sev-info"


def _table(headers: list[str], rows: list[list]) -> str:
    th = "".join(f"<th>{_h(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        tds = "".join(f"<td>{_h(c)}</td>" for c in row)
        body_rows.append(f"<tr>{tds}</tr>")
    return (
        '<table class="data"><thead><tr>'
        f"{th}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
    )


def _section(title: str, inner: str) -> str:
    return f'<section class="block"><h2>{_h(title)}</h2>{inner}</section>'


def _render_overview(ov: dict) -> str:
    if not ov:
        return "<p class=\"muted\">No overview data.</p>"
    og = ov.get("original_shape") or {}
    cl = ov.get("cleaned_shape") or {}
    cards = f"""
    <div class="cards">
      <div class="card"><span class="lab">Original rows</span><span class="num">{_h(og.get('rows'))}</span></div>
      <div class="card"><span class="lab">Original columns</span><span class="num">{_h(og.get('columns'))}</span></div>
      <div class="card"><span class="lab">Final rows</span><span class="num">{_h(cl.get('rows'))}</span></div>
      <div class="card"><span class="lab">Final columns</span><span class="num">{_h(cl.get('columns'))}</span></div>
      <div class="card"><span class="lab">Rows removed</span><span class="num">{_h(ov.get('rows_removed'))}</span></div>
      <div class="card"><span class="lab">Columns removed</span><span class="num">{_h(ov.get('cols_removed'))}</span></div>
    </div>
    """
    orig_cols = ", ".join(str(c) for c in (ov.get("original_columns") or []))
    fin_cols = ", ".join(str(c) for c in (ov.get("final_columns") or []))
    lists = f"""
    <p class="cols"><strong>Original columns:</strong> {_h(orig_cols)}</p>
    <p class="cols"><strong>Final columns:</strong> {_h(fin_cols)}</p>
    """
    return cards + lists


def _render_profiles(profiles: list) -> str:
    if not profiles:
        return "<p class=\"muted\">No column profiles.</p>"
    headers = [
        "Column",
        "dtype",
        "Null count",
        "Null %",
        "Unique",
        "Mean",
        "Median",
        "Min",
        "Max",
    ]
    rows = []
    for p in profiles:
        nr = p.get("null_ratio")
        null_pct = f"{float(nr) * 100:.2f}" if nr is not None else "—"
        rows.append(
            [
                p.get("column"),
                p.get("dtype"),
                p.get("null_count"),
                null_pct,
                p.get("unique_count"),
                p.get("mean"),
                p.get("median"),
                p.get("min"),
                p.get("max"),
            ]
        )
    return _table(headers, rows)


def _render_issues(issues: list) -> str:
    if not issues:
        return "<p class=\"muted\">No quality issues reported.</p>"
    parts = []
    for iss in issues:
        sev = iss.get("severity", "info")
        cls = _severity_class(sev)
        col = iss.get("column", "—")
        msg = iss.get("message", "")
        chk = iss.get("check", "")
        aff = iss.get("affected", "")
        aff_html = ""
        if aff != "" and aff is not None:
            aff_html = f'<br/><span class="aff">Affected: {_h(aff)}</span>'
        parts.append(
            f'<div class="issue"><span class="pill {cls}">{_h(sev)}</span> '
            f'<strong>{_h(col)}</strong> <span class="chk">({_h(chk)})</span><br/>'
            f'<span class="msg">{_h(msg)}</span>{aff_html}</div>'
        )
    return '<div class="issues">' + "".join(parts) + "</div>"


def _render_suggestions(items: list) -> str:
    if not items:
        return "<p class=\"muted\">No suggestions.</p>"
    parts = []
    for s in items:
        sev = s.get("severity", "info")
        cls = _severity_class(sev)
        parts.append(
            f'<div class="sug">'
            f'<span class="pill {cls}">{_h(sev)}</span> '
            f'<strong>{_h(s.get("type", ""))}</strong> · <em>{_h(s.get("scope", ""))}</em><br/>'
            f'<p class="msg">{_h(s.get("message", ""))}</p>'
            f'<p class="action"><strong>Action:</strong> {_h(s.get("action", ""))}</p>'
            f"</div>"
        )
    return '<div class="suggestions">' + "".join(parts) + "</div>"


def _render_cleaning(cs: dict) -> str:
    if not cs:
        return "<p class=\"muted\">Cleaning summary not included.</p>"
    cd = cs.get("columns_dropped") or {}
    cr = cs.get("columns_retained") or {}
    mv = cs.get("missing_values") or {}
    dropped = cd.get("detail") or []
    drop_rows = "".join(
        f"<li>{_h(d.get('column'))}: {_h(d.get('reason', ''))}</li>" for d in dropped
    )
    if not drop_rows:
        drop_rows = "<li>None</li>"
    actions = mv.get("detail") or []
    act_rows = "".join(
        f"<li>{_h(a.get('column'))} — {_h(a.get('action', ''))}</li>" for a in actions
    )
    if not act_rows:
        act_rows = "<li>None</li>"
    return f"""
    <ul class="kv">
      <li><strong>Columns dropped:</strong> {_h(cd.get('count'))}</li>
      <li><strong>Columns retained:</strong> {_h(cr.get('count'))}</li>
      <li><strong>Missing: columns filled / flagged / skipped:</strong>
          {_h(mv.get('columns_filled'))} / {_h(mv.get('columns_flagged'))} / {_h(mv.get('columns_skipped'))}</li>
      <li><strong>Rows dropped (missing handling):</strong> {_h(mv.get('rows_dropped'))}</li>
    </ul>
    <h3>Dropped columns</h3><ul class="detail">{drop_rows}</ul>
    <h3>Missing-value actions</h3><ul class="detail">{act_rows}</ul>
    """


def _render_coercion(co: dict) -> str:
    if not co:
        return "<p class=\"muted\">No coercion data.</p>"
    by_type = co.get("by_type") or {}
    type_bits = "".join(
        f"<li><strong>{_h(k)}:</strong> {_h(', '.join(v))}</li>"
        for k, v in by_type.items()
    )
    if not type_bits:
        type_bits = "<li>None</li>"
    changes = co.get("detail_changes") or []
    ch_rows = [
        [
            c.get("column"),
            c.get("cast_type"),
            c.get("from_dtype"),
            c.get("to_dtype"),
            f"{float(c['success_rate']):.0%}" if c.get("success_rate") is not None else "—",
        ]
        for c in changes
    ]
    tbl = (
        _table(["Column", "Cast type", "From", "To", "Success rate"], ch_rows)
        if ch_rows
        else "<p class=\"muted\">No columns were coerced.</p>"
    )
    errs = co.get("detail_errors") or []
    err_html = ""
    if errs:
        err_html = "<h3>Coercion errors</h3><ul>" + "".join(
            f"<li>{_h(e.get('column'))}: {_h(e.get('reason', ''))}</li>" for e in errs
        ) + "</ul>"
    return f"""
    <ul class="kv">
      <li><strong>Columns cast:</strong> {_h(co.get('columns_cast'))}</li>
      <li><strong>Cast errors:</strong> {_h(co.get('cast_errors'))}</li>
    </ul>
    <h3>By type</h3><ul class="detail">{type_bits}</ul>
    <h3>Type changes</h3>{tbl}{err_html}
    """


def write_html_report(report: dict, output_path: str, source_name: str = "") -> None:
    """
    Write a self-contained HTML report (overview, tables, issues, suggestions).
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    qs = report.get("quality_score") or {}
    score = qs.get("score", "—")
    breakdown = qs.get("breakdown") or {}
    label = source_name or path.name
    title = f"DataForge Audit Report — {label}"
    generated_at = datetime.now().strftime("%Y-%m-%d %I:%M %p")

    # ── Status badge ──────────────────────────────────────────────────────────
    issues_list    = report.get("quality_issues") or []
    critical_count = sum(1 for i in issues_list if (i.get("severity") or "").lower() == "critical")
    warning_count  = sum(1 for i in issues_list if (i.get("severity") or "").lower() in ("warning", "high"))
    info_count     = sum(1 for i in issues_list if (i.get("severity") or "").lower() in ("info", "low", "medium"))
    total_count    = len(issues_list)

    grade = _compute_grade(score, critical_count)

    badge_label = _compute_status(score, critical_count)
    if badge_label == "ACTION REQUIRED":
        badge_class = "badge-action"
    elif badge_label == "HEALTHY":
        badge_class = "badge-healthy"
    else:
        badge_class = "badge-review"

    bd_html = ""
    if breakdown:
        bd_html = "<ul class=\"kv\">" + "".join(
            f"<li><strong>{_h(k)}:</strong> {_h(v)}</li>" for k, v in breakdown.items()
        ) + "</ul>"

    severity_strip = f"""
    <div class="sev-cards">
      <div class="sev-card sev-card-crit"><span class="lab">Critical</span><span class="num">{critical_count}</span></div>
      <div class="sev-card sev-card-warn"><span class="lab">Warnings</span><span class="num">{warning_count}</span></div>
      <div class="sev-card sev-card-info"><span class="lab">Info</span><span class="num">{info_count}</span></div>
      <div class="sev-card sev-card-total"><span class="lab">Total</span><span class="num">{total_count}</span></div>
    </div>
    """

    score_strip = f"""
    <div class="hero">
      <div class="hero-score"><span class="big">{_h(score)}</span><span class="sub">/ 100</span></div>
      <div class="hero-grade"><span class="lab">Grade</span><span class="val">{_h(grade)}</span></div>
      <div class="hero-badge"><span class="badge {badge_class}">{badge_label}</span></div>
      {bd_html}
    </div>
    """

    body = "".join(
        [
            score_strip,
            severity_strip,
            _section("Dataset overview", _render_overview(report.get("overview") or {})),
            _section("Column profiles", _render_profiles(report.get("column_profiles") or [])),
            _section("Quality issues", _render_issues(report.get("quality_issues") or [])),
            _section("Suggestions", _render_suggestions(report.get("suggestions") or [])),
            _section("Cleaning", _render_cleaning(report.get("cleaning_summary") or {})),
            _section("Type coercion", _render_coercion(report.get("coercion_summary") or {})),
        ]
    )

    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{_h(title)}</title>
  <style>
    :root {{
      --bg: #f6f5f2;
      --card: #fff;
      --border: #e2e0d9;
      --text: #1a1916;
      --muted: #6b6560;
      --crit: #a32929;
      --warn: #b8860b;
      --info: #2a6f97;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: "Segoe UI", system-ui, sans-serif;
      margin: 0;
      padding: 0 1.5rem 3rem;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    header {{
      padding: 2rem 0 1rem;
      border-bottom: 1px solid var(--border);
      margin-bottom: 1.5rem;
    }}
    h1 {{ font-size: 1.75rem; font-weight: 600; margin: 0; }}
    h2 {{ font-size: 1.15rem; margin: 0 0 0.75rem; }}
    h3 {{ font-size: 0.95rem; margin: 1rem 0 0.5rem; color: var(--muted); }}
    .hero {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 1.5rem 2rem;
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .hero-score .big {{ font-size: 2.5rem; font-weight: 700; }}
    .hero-score .sub {{ color: var(--muted); margin-left: 0.25rem; }}
    .hero-grade .lab {{ display: block; font-size: 0.75rem; color: var(--muted); text-transform: uppercase; }}
    .hero-grade .val {{ font-size: 1.35rem; font-weight: 600; }}
    .block {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.25rem;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 0.75rem;
      margin-bottom: 1rem;
    }}
    .card {{
      background: var(--bg);
      border-radius: 8px;
      padding: 0.65rem 0.85rem;
    }}
    .card .lab {{ display: block; font-size: 0.7rem; color: var(--muted); text-transform: uppercase; }}
    .card .num {{ font-size: 1.25rem; font-weight: 600; }}
    .cols {{ font-size: 0.9rem; word-break: break-word; }}
    table.data {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }}
    table.data th, table.data td {{
      border: 1px solid var(--border);
      padding: 0.45rem 0.6rem;
      text-align: left;
    }}
    table.data th {{ background: var(--bg); font-weight: 600; }}
    table.data tr:nth-child(even) td {{ background: #fafaf8; }}
    .muted {{ color: var(--muted); }}
    ul.kv {{ list-style: none; padding: 0; margin: 0 0 0.5rem; }}
    ul.kv li {{ margin: 0.35rem 0; }}
    ul.detail {{ font-size: 0.88rem; }}
    .issues .issue, .suggestions .sug {{
      border-left: 3px solid var(--border);
      padding: 0.65rem 0 0.65rem 0.85rem;
      margin-bottom: 0.75rem;
      background: var(--bg);
      border-radius: 0 6px 6px 0;
    }}
    .pill {{
      display: inline-block;
      font-size: 0.68rem;
      font-weight: 600;
      text-transform: uppercase;
      padding: 0.15rem 0.45rem;
      border-radius: 4px;
      margin-right: 0.35rem;
    }}
    .sev-crit {{ background: #fde8e8; color: var(--crit); }}
    .sev-warn {{ background: #fff8e6; color: var(--warn); }}
    .sev-med {{ background: #fff4e0; color: #a65f00; }}
    .sev-low {{ background: #eef6fb; color: var(--info); }}
    .sev-info {{ background: #eef6fb; color: var(--info); }}
    .chk {{ color: var(--muted); font-size: 0.85rem; }}
    .msg {{ display: inline-block; margin-top: 0.25rem; }}
    .action {{ margin: 0.5rem 0 0; font-size: 0.9rem; }}
    /* ── Branding ── */
    .subtitle {{ margin: 0.35rem 0 0; color: var(--muted); font-size: 0.95rem; font-style: italic; }}
    .ts {{ margin: 0.2rem 0 0; font-size: 0.75rem; color: var(--muted); }}
    /* ── Status badge ── */
    .hero-badge {{ display: flex; align-items: center; }}
    .badge {{
      display: inline-block;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      padding: 0.3rem 0.8rem;
      border-radius: 6px;
    }}
    .badge-healthy {{ background: #d4edda; color: #155724; border: 1px solid #b3ddbf; }}
    .badge-review  {{ background: #fff3cd; color: #856404; border: 1px solid #fde8a0; }}
    .badge-action  {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6c6; }}
    /* ── Severity cards ── */
    .sev-cards {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 0.75rem;
      margin-bottom: 1.25rem;
    }}
    .sev-card {{
      border-radius: 10px;
      padding: 0.85rem 1rem;
      border: 1px solid var(--border);
    }}
    .sev-card .lab {{ display: block; font-size: 0.68rem; color: var(--muted); text-transform: uppercase; margin-bottom: 0.3rem; }}
    .sev-card .num {{ font-size: 1.6rem; font-weight: 700; }}
    .sev-card-crit {{ background: #fde8e8; border-color: #f5c6c6; }}
    .sev-card-crit .num {{ color: var(--crit); }}
    .sev-card-warn {{ background: #fff8e6; border-color: #fde8a0; }}
    .sev-card-warn .num {{ color: var(--warn); }}
    .sev-card-info {{ background: #eef6fb; border-color: #b8d9ef; }}
    .sev-card-info .num {{ color: var(--info); }}
    .sev-card-total {{ background: var(--card); border-color: var(--border); }}
    .sev-card-total .num {{ color: var(--text); }}
  </style>
</head>
<body>
  <header>
    <h1>{_h(title)}</h1>
    <p class="subtitle">Transform Raw Data into Trusted Data</p>
    <p class="ts">Generated: {_h(generated_at)}</p>
  </header>
  {body}
</body>
</html>
"""
    path.write_text(content, encoding="utf-8")
