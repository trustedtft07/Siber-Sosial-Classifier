import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class FactCheckRAG:
    def __init__(self, data_path: Path | None = None):
        if data_path is None:
            data_path = Path(__file__).resolve().parent.parent / "data" / "fact_checks.json"

        with open(data_path, "r", encoding="utf-8") as f:
            self.fact_checks = json.load(f)

        self.claims = [item["claim"] for item in self.fact_checks]
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            analyzer="word",
            sublinear_tf=True,
            min_df=1
        )
        self.claim_vectors = self.vectorizer.fit_transform(self.claims)

    def search_evidence(self, query: str, top_k: int = 3) -> list[dict]:
        clean_query = query.strip()
        if not clean_query or not self.claims:
            return []

        query_vec = self.vectorizer.transform([clean_query])
        similarities = cosine_similarity(query_vec, self.claim_vectors).flatten()

        ranked_indices = similarities.argsort()[::-1][:top_k]
        results = []

        for idx in ranked_indices:
            score = float(similarities[idx])
            item = dict(self.fact_checks[idx])
            item["similarity_score"] = round(score, 3)
            results.append(item)

        return results

    def add_fact_check(self, entry: dict) -> None:
        self.fact_checks.append(entry)
        self.claims.append(entry["claim"])
        self.claim_vectors = self.vectorizer.fit_transform(self.claims)
