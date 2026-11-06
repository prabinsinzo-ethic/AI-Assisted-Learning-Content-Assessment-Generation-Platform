import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Study, StudyPair, Rating, ContentItem

router = APIRouter(prefix="/studies", tags=["analysis"])


def _group_scores(ratings, attr):
    return [getattr(r, attr) for r in ratings if getattr(r, attr) is not None]


def _mean(xs):
    return float(np.mean(xs)) if xs else None


def _cohen_d(a, b):
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    if len(a) < 2 or len(b) < 2:
        return None
    na, nb = len(a), len(b)
    va, vb = np.var(a, ddof=1), np.var(b, ddof=1)
    pooled = np.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    if pooled == 0:
        return None
    return float((np.mean(a) - np.mean(b)) / pooled)


@router.get("/{study_id}/analysis")
def analyze(study_id: int, db: Session = Depends(get_db)):
    st = db.query(Study).get(study_id)
    if not st:
        raise HTTPException(404, "Study not found")
    pairs = db.query(StudyPair).filter(StudyPair.study_id == study_id).all()
    criteria = ["accuracy", "clarity", "difficulty", "distractor_quality", "bloom_alignment", "overall", "would_use"]
    paired = {c: {"ai": [], "human": []} for c in criteria}
    per_pair = []
    for p in pairs:
        ai_ratings = db.query(Rating).filter(Rating.pair_id == p.id, Rating.item_id == p.ai_item_id).all()
        human_ratings = db.query(Rating).filter(Rating.pair_id == p.id, Rating.item_id == p.human_item_id).all()
        pair_info = {"pair_id": p.id, "ai_item_id": p.ai_item_id, "human_item_id": p.human_item_id}
        for c in criteria:
            a_vals = _group_scores(ai_ratings, c)
            h_vals = _group_scores(human_ratings, c)
            pair_info[c] = {"ai_mean": _mean(a_vals), "human_mean": _mean(h_vals), "ai_n": len(a_vals), "human_n": len(h_vals)}
            if a_vals and h_vals:
                paired[c]["ai"].extend(a_vals)
                paired[c]["human"].extend(h_vals)
        per_pair.append(pair_info)

    try:
        from scipy import stats
        has_scipy = True
    except Exception:
        has_scipy = False
    comparison = {}
    for c in criteria:
        a = paired[c]["ai"]
        b = paired[c]["human"]
        entry = {
            "ai_mean": _mean(a),
            "human_mean": _mean(b),
            "ai_n": len(a),
            "human_n": len(b),
            "cohen_d": _cohen_d(a, b),
        }
        if has_scipy and len(a) > 1 and len(b) > 1 and len(a) == len(b):
            try:
                t, tp = stats.ttest_rel(a, b)
                entry["paired_t_p"] = float(tp)
            except Exception:
                entry["paired_t_p"] = None
            try:
                w, wp = stats.wilcoxon(a, b)
                entry["wilcoxon_p"] = float(wp)
            except Exception:
                entry["wilcoxon_p"] = None
        else:
            entry["paired_t_p"] = None
            entry["wilcoxon_p"] = None
        comparison[c] = entry

    icc = {}
    for c in criteria:
        items = {}
        for p in pairs:
            for item_id in (p.ai_item_id, p.human_item_id):
                items.setdefault(item_id, {})
        for r in db.query(Rating).filter(Rating.study_id == study_id).all():
            val = getattr(r, c)
            if val is not None:
                items[r.item_id][r.rater_id] = val
        subjects = [v for v in items.values() if len(v) >= 2]
        if len(subjects) < 2:
            icc[c] = None
            continue
        raters = sorted({rid for s in subjects for rid in s})
        M = np.full((len(subjects), len(raters)), np.nan)
        for i, s in enumerate(subjects):
            for j, rid in enumerate(raters):
                if rid in s:
                    M[i, j] = s[rid]
        col_mask = ~np.all(np.isnan(M), axis=0)
        M = M[:, col_mask]
        k = M.shape[1]
        if k < 2:
            icc[c] = None
            continue
        for i in range(M.shape[0]):
            row = M[i]
            m = np.nanmean(row)
            M[i] = np.where(np.isnan(row), m, row)
        grand_mean = M.mean()
        ss_between = k * np.sum((M.mean(axis=1) - grand_mean) ** 2)
        ss_within = np.sum((M - M.mean(axis=1, keepdims=True)) ** 2)
        ss_raters = M.shape[0] * np.sum((M.mean(axis=0) - grand_mean) ** 2)
        df_between = M.shape[0] - 1
        df_within = M.shape[0] * (k - 1)
        df_raters = k - 1
        MSB = ss_between / df_between if df_between else 0
        MSW = ss_within / df_within if df_within else 0
        MSR = ss_raters / df_raters if df_raters else 0
        n = M.shape[0]
        denom = MSB + (k - 1) * MSW + k * (MSR - MSW) / n
        icc_val = (MSB - MSW) / denom if denom != 0 else None
        icc[c] = float(icc_val) if icc_val is not None else None

    return {
        "study_id": study_id,
        "criteria": criteria,
        "comparison": comparison,
        "icc": icc,
        "pairs": per_pair,
    }


@router.get("/{study_id}/report")
def report(study_id: int, db: Session = Depends(get_db)):
    st = db.query(Study).get(study_id)
    if not st:
        raise HTTPException(404, "Study not found")
    a = analyze(study_id, db)
    comp = a["comparison"]
    overall_ai = comp["overall"]["ai_mean"]
    overall_human = comp["overall"]["human_mean"]
    parity = None
    if overall_ai is not None and overall_human:
        parity = overall_ai / overall_human
    icc_vals = [v for v in a["icc"].values() if v is not None]
    avg_icc = (sum(icc_vals) / len(icc_vals)) if icc_vals else None
    recs = []
    if parity is not None:
        if parity >= 0.9:
            recs.append("AI items achieved parity with human items on overall quality.")
        elif parity >= 0.8:
            recs.append("AI items approached human quality; consider prompt tuning.")
        else:
            recs.append("AI items below human quality; revisit generation prompts and QC thresholds.")
    if avg_icc is not None:
        if avg_icc < 0.7:
            recs.append("Inter-rater reliability below target (ICC<0.7); rater training needed.")
        else:
            recs.append("Inter-rater reliability acceptable.")
    for c, v in comp.items():
        if v.get("ai_mean") is not None and v.get("human_mean"):
            if v["ai_mean"] < 0.8 * v["human_mean"]:
                recs.append(f"Improve {c}: AI mean {v['ai_mean']:.2f} vs human {v['human_mean']:.2f}.")
    if not recs:
        recs.append("Insufficient data for recommendations.")
    return {
        "study_id": study_id,
        "study_name": st.name,
        "status": st.status,
        "parity_ratio_overall": parity,
        "avg_icc": avg_icc,
        "comparison": comp,
        "icc": a["icc"],
        "recommendations": recs,
    }