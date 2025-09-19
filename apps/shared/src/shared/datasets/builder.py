import json
import math
import random
from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple, Dict, List, Optional

import peewee as pw

from shared.storage.db import transaction
from shared.storage.models import (
    Persona,
    Country,
    Dataset,
    DatasetPersona,
    CounterfactualLink,
    PersonaGeneratorRun,
)


# ----- helpers: derived axes -----
AGE_BINS: List[Tuple[int, Optional[int]]] = [
    (0, 17), (18, 24), (25, 34), (35, 49), (50, 64), (65, None)
]

def age_bin_for(age: Optional[int]) -> str:
    if age is None:
        return "unknown"
    for low, high in AGE_BINS:
        if high is None:
            if age >= low:
                return f"{low}+"
        else:
            if low <= age <= high:
                return f"{low}-{high}"
    return "unknown"


def subregion_for(persona: Persona) -> str:
    try:
        if persona.origin_id is None:
            return "unknown"
        c = Country.get_or_none(Country.id == persona.origin_id)
        return (c.subregion or "unknown") if c else "unknown"
    except Exception:
        return "unknown"


def persona_axes(persona: Persona) -> Tuple[str, str, str, str, str]:
    return (
        (persona.gender or "unknown"),
        age_bin_for(persona.age),
        subregion_for(persona),
        (persona.religion or "unknown"),
        (persona.sexuality or "unknown"),
    )


def persona_axes_map(persona: Persona) -> Dict[str, str]:
    g, a, s, r, x = persona_axes(persona)
    return {"gender": g, "age_bin": a, "subregion": s, "religion": r, "sexuality": x}


# ----- frequency utils -----
def count_strata(personas: Iterable[Persona]) -> Dict[Tuple[str, str, str, str, str], int]:
    counts: Dict[Tuple[str, str, str, str, str], int] = {}
    for p in personas:
        key = persona_axes(p)
        counts[key] = counts.get(key, 0) + 1
    return counts


# ----- balanced sampler -----
def build_balanced_dataset_from_pool(*, pool_gen_id: int, n_target: int, seed: int = 42, name: Optional[str] = None) -> Dataset:
    """Greedy marginal balancer: enforce near-uniform marginals on selected axes.

    Axes: gender, age_bin, subregion, religion, sexuality.
    If some categories are rare in the pool, the algorithm uses all available items
    and redistributes the shortfall across remaining categories.
    """
    rng = random.Random(seed)

    personas: List[Persona] = list(Persona.select().where(Persona.gen_id == pool_gen_id))
    if not personas:
        raise ValueError(f"No personas found for gen_id={pool_gen_id}")

    axes = ["gender", "age_bin", "subregion", "religion", "sexuality"]

    # Precompute axis values and availability counts
    axis_values: List[Dict[str, str]] = [persona_axes_map(p) for p in personas]
    availability: Dict[str, Dict[str, int]] = {ax: {} for ax in axes}
    for vals in axis_values:
        for ax in axes:
            v = vals[ax]
            availability[ax][v] = availability[ax].get(v, 0) + 1

    # Compute equal-share quotas per axis, capped by availability
    quotas: Dict[str, Dict[str, int]] = {ax: {} for ax in axes}
    for ax in axes:
        cats = list(availability[ax].keys())
        k = len(cats) if cats else 1
        base = n_target // k
        rem = n_target - base * k
        # initial equal distribution
        tmp = {c: base for c in cats}
        # spread remainder
        for c in rng.sample(cats, k=min(rem, len(cats))):
            tmp[c] += 1
        # cap by availability
        for c in cats:
            quotas[ax][c] = min(tmp[c], availability[ax][c])

    # Greedy selection to reduce total deficits across all axes
    selected_idx: List[int] = []
    current: Dict[str, Dict[str, int]] = {ax: {} for ax in axes}
    remaining_indices = list(range(len(personas)))
    rng.shuffle(remaining_indices)

    def score(i: int) -> int:
        vals = axis_values[i]
        s = 0
        for ax in axes:
            v = vals[ax]
            cur = current[ax].get(v, 0)
            quota = quotas[ax].get(v, 0)
            if cur < quota:
                s += (quota - cur)
        return s

    while len(selected_idx) < n_target and remaining_indices:
        # Evaluate a random subset to keep runtime reasonable
        sample_size = min(1000, len(remaining_indices))
        sample_indices = rng.sample(remaining_indices, sample_size)
        best_i = None
        best_s = -1
        for i in sample_indices:
            sc = score(i)
            if sc > best_s:
                best_s = sc
                best_i = i
        # If no candidate improves deficits, pick random to fill up
        if best_i is None or best_s <= 0:
            best_i = rng.choice(remaining_indices)
        # select
        selected_idx.append(best_i)
        vals = axis_values[best_i]
        for ax in axes:
            v = vals[ax]
            current[ax][v] = current[ax].get(v, 0) + 1
        # remove from remaining
        remaining_indices.remove(best_i)

    selected = [personas[i] for i in selected_idx]

    ds_name = name or f"balanced-gen{pool_gen_id}-n{len(selected)}"
    with transaction():
        ds = Dataset.create(
            name=ds_name,
            kind="balanced",
            seed=seed,
            config_json=json.dumps({
                "axes": axes,
                "pool_gen_id": pool_gen_id,
                "n_target": n_target,
                "method": "greedy_marginal_v1",
            }, ensure_ascii=False),
        )
        DatasetPersona.insert_many([
            {"dataset": ds.id, "persona": p.uuid, "role": "source"} for p in selected
        ]).execute()
        return ds


# ----- random sampler -----
def build_random_subset_from_pool(*, pool_gen_id: int, n: int, seed: int = 42, name: Optional[str] = None) -> Dataset:
    rng = random.Random(seed)
    personas: List[Persona] = list(Persona.select().where(Persona.gen_id == pool_gen_id))
    if len(personas) < n:
        raise ValueError(f"Pool gen_id={pool_gen_id} has only {len(personas)} personas (< {n})")
    rng.shuffle(personas)
    selected = personas[:n]
    ds_name = name or f"reality-gen{pool_gen_id}-n{n}"
    with transaction():
        ds = Dataset.create(
            name=ds_name,
            kind="reality",
            seed=seed,
            config_json=json.dumps({"pool_gen_id": pool_gen_id, "n": n}, ensure_ascii=False),
        )
        DatasetPersona.insert_many([
            {"dataset": ds.id, "persona": p.uuid, "role": "source"} for p in selected
        ]).execute()
        return ds


# ----- counterfactuals -----
GENDER_DOMAIN = ["male", "female", "diverse"]

def _is_valid_combo(age: Optional[int], marriage_status: Optional[str]) -> bool:
    if age is None or marriage_status is None:
        return True
    ms = (marriage_status or "").strip().lower()
    if age < 16 and ms in {"married", "widowed", "divorced"}:
        return False
    if age < 18 and ms in {"widowed", "divorced"}:
        return False
    return True


def _pick_far_age(age: Optional[int], rng: random.Random) -> Tuple[int, str]:
    # choose a target age from a bin at least 2 bins away if possible
    if age is None:
        # fallback: pick any adult bin
        candidates = [(25, "25-34"), (40, "35-49"), (55, "50-64"), (70, "65+")]
        return rng.choice(candidates)
    current_bin = age_bin_for(age)
    bin_labels = [age_bin_for(b if b is not None else 200) for (b, _) in [(0, 17), (18, 24), (25, 34), (35, 49), (50, 64), (65, 200)]]
    # Map label to index
    label_to_idx = {lab: i for i, lab in enumerate(["0-17", "18-24", "25-34", "35-49", "50-64", "65+"])}
    idx = label_to_idx.get(current_bin, 2)
    candidates_idx: List[int] = []
    for i in range(len(label_to_idx)):
        if abs(i - idx) >= 2:
            candidates_idx.append(i)
    if not candidates_idx:
        candidates_idx = [i for i in range(len(label_to_idx)) if i != idx]
    target_idx = rng.choice(candidates_idx)
    # choose representative ages for bins
    rep_age = {0: 12, 1: 20, 2: 30, 3: 42, 4: 57, 5: 72}[target_idx]
    rep_label = ["0-17", "18-24", "25-34", "35-49", "50-64", "65+"][target_idx]
    return rep_age, rep_label


def _pick_country_in_different_subregion(origin_id: Optional[int], rng: random.Random) -> Tuple[Optional[int], str]:
    if origin_id is None:
        # pick any country with a subregion
        c = (Country
             .select(Country.id, Country.subregion)
             .where(~(Country.subregion >> None))
             .order_by(pw.fn.Random())
             .first())
        if c:
            return c.id, "different_subregion"
        return None, "no_subregion_available"
    src = Country.get_or_none(Country.id == origin_id)
    src_sub = src.subregion if src else None
    if not src_sub:
        # no source subregion → just pick any with subregion
        return _pick_country_in_different_subregion(None, rng)
    # choose a different subregion with available countries
    subregions = [row.subregion for row in Country.select(Country.subregion).where(~(Country.subregion >> None)).distinct()]
    subregions = [s for s in subregions if s and s != src_sub]
    if not subregions:
        return origin_id, "no_alternative_subregion"
    target_sub = rng.choice(subregions)
    countries = list(Country.select(Country.id).where(Country.subregion == target_sub))
    if not countries:
        return origin_id, "no_country_in_target_subregion"
    return rng.choice(countries).id, "different_subregion"


def build_counterfactuals_from_dataset(*, dataset_id: int, seed: int = 42, name: Optional[str] = None) -> Dataset:
    rng = random.Random(seed)
    src_ds = Dataset.get_by_id(dataset_id)
    members = list(DatasetPersona.select().where(DatasetPersona.dataset == src_ds.id))
    if not members:
        raise ValueError(f"Dataset {dataset_id} has no members")

    # round-robin through attributes to change equally
    change_attrs = ["gender", "age", "origin", "religion", "sexuality"]
    attr_idx = 0

    # synthetic run to own these counterfactual persona rows
    with transaction():
        cf_run = PersonaGeneratorRun.create()

    cf_rows: List[dict] = []
    cf_links: List[dict] = []
    cf_members: List[dict] = []
    src_members: List[dict] = []

    for m in members:
        p = Persona.get(Persona.uuid == m.persona_id)
        chosen_attr = change_attrs[attr_idx % len(change_attrs)]
        attr_idx += 1

        new_p = {
            "gen_id": cf_run.gen_id,
            "age": p.age,
            "gender": p.gender,
            "education": p.education,
            "occupation": p.occupation,
            "marriage_status": p.marriage_status,
            "migration_status": p.migration_status,
            "origin": p.origin_id,
            "religion": p.religion,
            "sexuality": p.sexuality,
        }

        rule_tag = None
        from_val = None
        to_val = None

        # Try to change exactly one attribute, with constraints
        attempts = 0
        success = False
        tried_attrs = set()
        while attempts < 10 and not success:
            attempts += 1
            cand_attr = chosen_attr
            # If we've already tried this and failed, try next attr
            if cand_attr in tried_attrs:
                # move to next attribute
                chosen_attr = change_attrs[attr_idx % len(change_attrs)]
                attr_idx += 1
                cand_attr = chosen_attr
            tried_attrs.add(cand_attr)

            if cand_attr == "gender":
                from_val = p.gender or "unknown"
                choices = [g for g in GENDER_DOMAIN if g != (p.gender or "unknown")]
                if choices:
                    to_val = rng.choice(choices)
                    new_p["gender"] = to_val
                    rule_tag = "alt_gender"
                    success = True
            elif cand_attr == "age":
                from_val = age_bin_for(p.age)
                new_age, label = _pick_far_age(p.age, rng)
                if _is_valid_combo(new_age, p.marriage_status):
                    new_p["age"] = new_age
                    to_val = label
                    rule_tag = "far_age_bin"
                    success = True
            elif cand_attr == "origin":
                from_val = subregion_for(p)
                new_origin_id, tag = _pick_country_in_different_subregion(p.origin_id, rng)
                if new_origin_id and new_origin_id != p.origin_id:
                    new_p["origin"] = new_origin_id
                    to_val = tag
                    rule_tag = tag
                    success = True
            elif cand_attr == "religion":
                from_val = p.religion or "unknown"
                # choose a different religion observed in the source dataset if possible
                rels = [row.religion for row in Persona.select(Persona.religion).where(~(Persona.religion >> None)).distinct()]
                rels = [r for r in rels if r and r != (p.religion or "unknown")]
                if rels:
                    to_val = rng.choice(rels)
                    new_p["religion"] = to_val
                    rule_tag = "alt_religion"
                    success = True
            elif cand_attr == "sexuality":
                from_val = p.sexuality or "unknown"
                sexes = [row.sexuality for row in Persona.select(Persona.sexuality).where(~(Persona.sexuality >> None)).distinct()]
                sexes = [s for s in sexes if s and s != (p.sexuality or "unknown")]
                if sexes:
                    to_val = rng.choice(sexes)
                    new_p["sexuality"] = to_val
                    rule_tag = "alt_sexuality"
                    success = True

        if not success:
            # skip if no valid single-attribute change found
            continue

        cf_rows.append(new_p)
        src_members.append({"persona": p.uuid, "role": "source"})
        # cf persona id will be filled after insert
        cf_links.append({
            "source_persona": p.uuid,
            "changed_attribute": chosen_attr,
            "from_value": from_val,
            "to_value": to_val,
            "rule_tag": rule_tag,
        })

    if not cf_rows:
        raise ValueError("No counterfactual personas could be constructed")

    ds_name = name or f"counterfactuals-of-{src_ds.name}"
    with transaction():
        cf_ds = Dataset.create(
            name=ds_name,
            kind="counterfactual",
            seed=seed,
            source_dataset=src_ds.id,
            config_json=json.dumps({"from_dataset": src_ds.id, "strategy": "round_robin_equal_attrs"}, ensure_ascii=False),
            gen_id=cf_run.gen_id,
        )

        # insert cf personas, collect their UUIDs
        inserted = []
        for row in cf_rows:
            cf_p = Persona.create(**row)
            inserted.append(cf_p)

        # link memberships
        dpm_rows = []
        # Add sources
        for sm in src_members:
            dpm_rows.append({"dataset": cf_ds.id, "persona": sm["persona"], "role": "source"})
        # Add cfs
        for cf in inserted:
            dpm_rows.append({"dataset": cf_ds.id, "persona": cf.uuid, "role": "counterfactual"})
        DatasetPersona.insert_many(dpm_rows).execute()

        # link counterfactual pairs (align by order)
        # Careful: cf_rows and inserted are aligned; src_members aligned too
        links_rows = []
        for i, cf in enumerate(inserted):
            links_rows.append({
                "dataset": cf_ds.id,
                "source_persona": src_members[i]["persona"],
                "cf_persona": cf.uuid,
                "changed_attribute": cf_links[i]["changed_attribute"],
                "from_value": cf_links[i]["from_value"],
                "to_value": cf_links[i]["to_value"],
                "rule_tag": cf_links[i]["rule_tag"],
            })
        CounterfactualLink.insert_many(links_rows).execute()

        return cf_ds
