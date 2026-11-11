"""Meaning-based matching (the "RAG" step) with a local Ollama embedding model.

Every job and the profile are turned into vectors once; cosine similarity then ranks thousands of jobs in
milliseconds. The slower AI scoring only runs on the best-ranked jobs. Vectors are cached in
runs/embeddings.npz, so each job is embedded only once.
"""
import hashlib
import os
import re

import numpy as np
import requests

OLLAMA = "http://localhost:11434"
MODEL = "nomic-embed-text"
# nomic-embed-text expects task prefixes; other models ignore them harmlessly.
Q, D = "search_query: ", "search_document: "
# Resume-vs-job cosine similarities from this model sit roughly between these values (measured on 527 real
# jobs: 10th percentile 0.51, best 0.66); they map to 0-100%.
LOW, HIGH = 0.50, 0.67


def available():
    try:
        r = requests.get(f"{OLLAMA}/api/tags", timeout=3)
        return any(m["name"].split(":")[0] == MODEL for m in r.json().get("models", []))
    except (requests.RequestException, ValueError):
        return False


def _embed(texts):
    out = []
    for i in range(0, len(texts), 32):
        r = requests.post(f"{OLLAMA}/api/embed", json={"model": MODEL, "input": texts[i:i + 32], "truncate": True},
                          timeout=300)
        r.raise_for_status()
        out += r.json()["embeddings"]
    v = np.asarray(out, dtype=np.float32)
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)


def job_text(job, description=""):
    return (f"{job.get('title', '')} at {job.get('company', '')}. {job.get('location', '')}. "
            f"{job.get('level', '')} {job.get('type', '')}. {description[:1800]}")


def profile_text(profile):
    """What the person can do: the resume part only. Preferences ("Target: AI roles") would make every AI job
    look like a match, and the "gaps" section lists skills the person does NOT have."""
    text = re.split(r"#+\s*gaps", profile, flags=re.I)[0]
    m = re.search(r"^#+\s*(resume|experience|skills)", text, flags=re.I | re.M)
    return (text[m.start():] if m else text)[:6000]


class Matcher:
    def __init__(self, store):
        self.store = store
        self.path = os.path.join(store.runs, "embeddings.npz")
        self.ids, self.vecs = [], np.zeros((0, 768), dtype=np.float32)
        self.profile_hash, self.pvec = "", None
        if os.path.exists(self.path):
            try:
                d = np.load(self.path, allow_pickle=False)
                self.ids, self.vecs = list(d["ids"]), d["vecs"]
                self.profile_hash, self.pvec = str(d["phash"]), d["pvec"]
            except (OSError, KeyError, ValueError):
                pass

    def _save(self):
        tmp = self.path + ".tmp.npz"
        np.savez_compressed(tmp, ids=np.asarray(self.ids), vecs=self.vecs, phash=np.asarray(self.profile_hash),
                            pvec=self.pvec if self.pvec is not None else np.zeros(self.vecs.shape[1], np.float32))
        os.replace(tmp, self.path)

    def ensure_profile(self, profile):
        h = hashlib.sha1(profile.encode("utf-8")).hexdigest()
        if h != self.profile_hash or self.pvec is None or not self.pvec.any():
            self.pvec = _embed([Q + profile_text(profile)])[0]
            self.profile_hash = h
            self._save()
        return self.pvec

    def ensure_jobs(self, jobs, descriptions):
        known = set(self.ids)
        todo = [j for j in jobs if j["id"] not in known]
        if todo:
            v = _embed([D + job_text(j, descriptions.get(j["id"], j.get("description", ""))) for j in todo])
            self.ids += [j["id"] for j in todo]
            self.vecs = v if not len(self.vecs) else np.vstack([self.vecs, v])
            self._save()
        return len(todo)

    def scores(self, profile, ids=None):
        """{job_id: semantic match 0-100} for the given ids (default: every embedded job)."""
        p = self.ensure_profile(profile)
        if not len(self.vecs):
            return {}
        sims = self.vecs @ p
        pct = np.clip((sims - LOW) / (HIGH - LOW), 0, 1) * 100
        wanted = set(ids) if ids is not None else None
        return {i: int(round(s)) for i, s in zip(self.ids, pct) if wanted is None or i in wanted}


def blended(fit, semantic):
    """One "match %" for the UI: AI fit when we have it, weighted with the meaning-based score."""
    if fit in (None, ""):
        return semantic
    if semantic in (None, ""):
        return int(fit) * 10
    return int(round(0.65 * int(fit) * 10 + 0.35 * semantic))
