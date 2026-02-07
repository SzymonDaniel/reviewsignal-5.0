# ═══════════════════════════════════════════════════════════════════════════════
# SINGULARITY ENGINE - Semantic Resonance Field
# Detect unexpected correlations and "prophetic" reviews
# ═══════════════════════════════════════════════════════════════════════════════

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import DBSCAN
import structlog

from .models import (
    SingularityConfig,
    ReviewData,
    SemanticResonance,
    PropheticReview,
    EmergentTheme,
    ResonanceType,
)
from .utils import (
    generate_id,
    normalize_sentiment,
    safe_mean,
    batch_iterator,
    sample_items,
    truncate_text,
    extract_keywords,
)

logger = structlog.get_logger(__name__)


class SemanticResonanceField:
    """
    Semantic Resonance Field - Detect Hidden Correlations

    Concepts:
    1. Cross-Brand Resonance: When reviews at different brands show
       similar sentiment patterns (e.g., "staff burnout" appearing
       across multiple chains simultaneously)

    2. Cross-City Resonance: When distant cities show correlated
       sentiment (could indicate macro trends)

    3. Prophetic Reviews: Reviews that predicted future events
       (e.g., reviews mentioning "supply issues" 2 weeks before
       a public shortage announcement)

    4. Emergent Themes: New topics suddenly appearing across reviews
       that weren't present before

    Uses sentence embeddings for semantic similarity comparison.
    """

    def __init__(
        self,
        reviews: List[ReviewData],
        config: Optional[SingularityConfig] = None
    ):
        self.reviews = reviews
        self.config = config or SingularityConfig()

        # Embedding model (lazy loaded)
        self._embedding_model = None
        self._embeddings_cache = {}

        # Index reviews by various dimensions
        self._reviews_by_chain = self._index_by_chain()
        self._reviews_by_city = self._index_by_city()
        self._reviews_by_date = self._index_by_date()

        logger.info(
            "semantic_resonance_initialized",
            review_count=len(reviews),
            unique_chains=len(self._reviews_by_chain),
            unique_cities=len(self._reviews_by_city)
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # INDEXING
    # ═══════════════════════════════════════════════════════════════════════════

    def _index_by_chain(self) -> Dict[str, List[ReviewData]]:
        """Index reviews by chain"""
        index = defaultdict(list)
        for r in self.reviews:
            if r.chain_id:
                index[r.chain_id.lower()].append(r)
        return dict(index)

    def _index_by_city(self) -> Dict[str, List[ReviewData]]:
        """Index reviews by city"""
        index = defaultdict(list)
        for r in self.reviews:
            if r.city:
                index[r.city.lower()].append(r)
        return dict(index)

    def _index_by_date(self) -> Dict[str, List[ReviewData]]:
        """Index reviews by date"""
        index = defaultdict(list)
        for r in self.reviews:
            if r.review_time:
                date_key = r.review_time.strftime("%Y-%m-%d")
                index[date_key].append(r)
        return dict(index)

    # ═══════════════════════════════════════════════════════════════════════════
    # EMBEDDING
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def embedding_model(self):
        """Lazy load sentence transformer model"""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer(
                    self.config.semantic_embedding_model
                )
                logger.info("embedding_model_loaded", model=self.config.semantic_embedding_model)
            except ImportError:
                logger.warning("sentence_transformers_not_available")
                self._embedding_model = "unavailable"
        return self._embedding_model

    def _get_embeddings(
        self,
        reviews: List[ReviewData],
        use_cache: bool = True
    ) -> np.ndarray:
        """
        Get embeddings for reviews

        Args:
            reviews: Reviews to embed
            use_cache: Whether to use cached embeddings

        Returns:
            numpy array of embeddings (n_reviews x embedding_dim)
        """
        if self.embedding_model == "unavailable":
            # Fallback: use simple TF-IDF-like approach
            return self._get_simple_embeddings(reviews)

        embeddings = []
        texts_to_embed = []
        indices_to_embed = []

        for i, review in enumerate(reviews):
            # Check cache
            if use_cache and review.review_id in self._embeddings_cache:
                embeddings.append(self._embeddings_cache[review.review_id])
            elif review.embedding is not None:
                embeddings.append(review.embedding)
                self._embeddings_cache[review.review_id] = review.embedding
            else:
                texts_to_embed.append(review.text)
                indices_to_embed.append(i)
                embeddings.append(None)  # Placeholder

        # Embed new texts in batches
        if texts_to_embed:
            for batch_texts, batch_indices in zip(
                batch_iterator(texts_to_embed, self.config.semantic_batch_size),
                batch_iterator(indices_to_embed, self.config.semantic_batch_size)
            ):
                batch_embeddings = self.embedding_model.encode(
                    batch_texts,
                    show_progress_bar=False
                )

                for idx, emb in zip(batch_indices, batch_embeddings):
                    embeddings[idx] = emb
                    review_id = reviews[idx].review_id
                    self._embeddings_cache[review_id] = emb

        return np.array(embeddings)

    def _get_simple_embeddings(self, reviews: List[ReviewData]) -> np.ndarray:
        """
        Fallback: Simple bag-of-words embeddings when sentence-transformers unavailable
        """
        from sklearn.feature_extraction.text import TfidfVectorizer

        texts = [r.text for r in reviews]
        if not texts:
            return np.array([])

        vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        try:
            embeddings = vectorizer.fit_transform(texts).toarray()
        except ValueError:
            embeddings = np.zeros((len(texts), 100))

        return embeddings

    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN ANALYSIS METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def find_resonances(
        self,
        reviews: Optional[List[ReviewData]] = None,
        resonance_types: Optional[List[ResonanceType]] = None
    ) -> List[SemanticResonance]:
        """
        Find all types of semantic resonance

        Args:
            reviews: Reviews to analyze (uses all if not provided)
            resonance_types: Types of resonance to look for

        Returns:
            List of SemanticResonance objects
        """
        reviews = reviews or self.reviews
        types = resonance_types or [
            ResonanceType.CROSS_BRAND,
            ResonanceType.CROSS_CITY,
            ResonanceType.EMERGENT
        ]

        resonances = []

        if ResonanceType.CROSS_BRAND in types:
            resonances.extend(self._find_cross_brand_resonance(reviews))

        if ResonanceType.CROSS_CITY in types:
            resonances.extend(self._find_cross_city_resonance(reviews))

        if ResonanceType.EMERGENT in types:
            # Emergent themes are handled separately
            pass

        logger.info(
            "resonances_found",
            total=len(resonances),
            types=[r.resonance_type.value for r in resonances[:5]]
        )

        return resonances

    def _find_cross_brand_resonance(
        self,
        reviews: List[ReviewData]
    ) -> List[SemanticResonance]:
        """Find semantic similarities across different brands"""
        resonances = []

        # Get unique chains
        chains = list(self._reviews_by_chain.keys())
        if len(chains) < 2:
            return resonances

        # Compare pairs of chains
        for i, chain_a in enumerate(chains):
            for chain_b in chains[i+1:]:
                reviews_a = self._reviews_by_chain[chain_a]
                reviews_b = self._reviews_by_chain[chain_b]

                # Sample if too many
                reviews_a = sample_items(reviews_a, self.config.semantic_max_reviews // 2)
                reviews_b = sample_items(reviews_b, self.config.semantic_max_reviews // 2)

                if len(reviews_a) < 5 or len(reviews_b) < 5:
                    continue

                # Get embeddings
                emb_a = self._get_embeddings(reviews_a)
                emb_b = self._get_embeddings(reviews_b)

                # Find similar pairs
                similarities = cosine_similarity(emb_a, emb_b)

                # Find high similarity pairs
                for idx_a, idx_b in zip(*np.where(similarities > self.config.semantic_min_similarity)):
                    review_a = reviews_a[idx_a]
                    review_b = reviews_b[idx_b]

                    # Skip if same time (might be spam)
                    if review_a.review_time and review_b.review_time:
                        time_diff = abs((review_a.review_time - review_b.review_time).days)
                    else:
                        time_diff = 0

                    resonance = SemanticResonance(
                        resonance_id=generate_id("res"),
                        resonance_type=ResonanceType.CROSS_BRAND,
                        source_review_ids=[review_a.review_id],
                        target_review_ids=[review_b.review_id],
                        cosine_similarity=float(similarities[idx_a, idx_b]),
                        temporal_lag_days=time_diff,
                        brand_a=chain_a,
                        brand_b=chain_b,
                        shared_themes=self._extract_shared_themes(review_a, review_b),
                        evidence_text_snippets=[
                            truncate_text(review_a.text, 100),
                            truncate_text(review_b.text, 100)
                        ]
                    )
                    resonances.append(resonance)

                    # Limit per chain pair
                    if len([r for r in resonances if r.brand_a == chain_a and r.brand_b == chain_b]) >= 10:
                        break

        return resonances[:50]  # Limit total

    def _find_cross_city_resonance(
        self,
        reviews: List[ReviewData]
    ) -> List[SemanticResonance]:
        """Find semantic similarities across different cities"""
        resonances = []

        # Get unique cities
        cities = list(self._reviews_by_city.keys())
        if len(cities) < 2:
            return resonances

        # Group reviews by time windows (weekly)
        time_windows = self._group_by_time_window(reviews, window_days=7)

        for window_key, window_reviews in time_windows.items():
            # Group by city within window
            by_city = defaultdict(list)
            for r in window_reviews:
                if r.city:
                    by_city[r.city.lower()].append(r)

            cities_in_window = list(by_city.keys())
            if len(cities_in_window) < 2:
                continue

            # Compare cities
            for i, city_a in enumerate(cities_in_window):
                for city_b in cities_in_window[i+1:]:
                    reviews_a = by_city[city_a]
                    reviews_b = by_city[city_b]

                    if len(reviews_a) < 3 or len(reviews_b) < 3:
                        continue

                    # Calculate aggregate similarity
                    emb_a = self._get_embeddings(reviews_a)
                    emb_b = self._get_embeddings(reviews_b)

                    # Mean embedding per city
                    mean_a = np.mean(emb_a, axis=0)
                    mean_b = np.mean(emb_b, axis=0)

                    similarity = float(cosine_similarity([mean_a], [mean_b])[0, 0])

                    if similarity > self.config.semantic_min_similarity:
                        resonance = SemanticResonance(
                            resonance_id=generate_id("res"),
                            resonance_type=ResonanceType.CROSS_CITY,
                            source_review_ids=[r.review_id for r in reviews_a[:5]],
                            target_review_ids=[r.review_id for r in reviews_b[:5]],
                            cosine_similarity=similarity,
                            temporal_lag_days=0,
                            city_a=city_a,
                            city_b=city_b,
                            shared_themes=self._extract_shared_themes_from_groups(reviews_a, reviews_b),
                            evidence_text_snippets=[
                                truncate_text(reviews_a[0].text, 100) if reviews_a else "",
                                truncate_text(reviews_b[0].text, 100) if reviews_b else ""
                            ]
                        )
                        resonances.append(resonance)

        return resonances[:30]

    def _group_by_time_window(
        self,
        reviews: List[ReviewData],
        window_days: int = 7
    ) -> Dict[str, List[ReviewData]]:
        """Group reviews by time windows"""
        windows = defaultdict(list)
        for r in reviews:
            if r.review_time:
                # Week number as key
                week_num = r.review_time.isocalendar()[1]
                year = r.review_time.year
                key = f"{year}_W{week_num:02d}"
                windows[key].append(r)
        return dict(windows)

    # ═══════════════════════════════════════════════════════════════════════════
    # PROPHETIC REVIEWS
    # ═══════════════════════════════════════════════════════════════════════════

    def find_prophetic_reviews(
        self,
        lookback_days: int = 90,
        min_lead_time: int = 7,
        events: Optional[List[Dict]] = None
    ) -> List[PropheticReview]:
        """
        Find reviews that "predicted" future events

        This looks for reviews that mentioned issues before they became
        widely recognized (e.g., supply chain complaints before announcements).

        Args:
            lookback_days: How far back to look
            min_lead_time: Minimum days before event for "prediction"
            events: Optional list of known events to match against

        Returns:
            List of PropheticReview objects
        """
        prophetic = []

        # Define patterns to look for
        predictive_patterns = {
            'supply_issues': ['shortage', 'out of stock', 'no supply', 'cant get', "can't get"],
            'staff_problems': ['understaffed', 'no staff', 'employees leaving', 'turnover'],
            'quality_decline': ['quality dropped', 'not like before', 'worse than', 'declining'],
            'price_concerns': ['too expensive', 'prices went up', 'overpriced'],
            'safety_issues': ['unsafe', 'dangerous', 'health concern', 'sick after'],
        }

        # Get reviews sorted by time
        dated_reviews = sorted(
            [r for r in self.reviews if r.review_time],
            key=lambda r: r.review_time
        )

        if not dated_reviews:
            return prophetic

        cutoff = datetime.utcnow() - timedelta(days=lookback_days)
        recent_reviews = [r for r in dated_reviews if r.review_time >= cutoff]

        # For each pattern, find early mentions
        for pattern_name, keywords in predictive_patterns.items():
            # Find reviews mentioning this pattern
            matching_reviews = []
            for r in recent_reviews:
                text_lower = r.text.lower()
                if any(kw in text_lower for kw in keywords):
                    matching_reviews.append(r)

            if len(matching_reviews) < 3:
                continue

            # Check if mentions increased over time (indicative of prediction)
            first_half = matching_reviews[:len(matching_reviews)//2]
            second_half = matching_reviews[len(matching_reviews)//2:]

            if len(first_half) > 0 and len(second_half) > len(first_half) * 1.5:
                # Early reviewers predicted a trend
                for early_review in first_half[:3]:
                    # Calculate when the spike happened
                    if second_half:
                        spike_date = second_half[0].review_time
                        lead_time = (spike_date - early_review.review_time).days

                        if lead_time >= min_lead_time:
                            prophetic.append(PropheticReview(
                                review_id=early_review.review_id,
                                review_text=early_review.text,
                                review_date=early_review.review_time,
                                predicted_event=f"{pattern_name} (volume spike)",
                                event_date=spike_date,
                                lead_time_days=lead_time,
                                prediction_accuracy=0.7,  # Estimated
                                similar_current_reviews=len(second_half),
                                chain_id=early_review.chain_id
                            ))

        logger.info("prophetic_reviews_found", count=len(prophetic))
        return prophetic[:20]

    # ═══════════════════════════════════════════════════════════════════════════
    # EMERGENT THEMES
    # ═══════════════════════════════════════════════════════════════════════════

    def detect_emergent_themes(
        self,
        min_reviews: int = 5,
        growth_threshold: float = 0.2,
        recent_days: int = 14
    ) -> List[EmergentTheme]:
        """
        Detect themes that are newly emerging in reviews

        Args:
            min_reviews: Minimum reviews for a theme
            growth_threshold: Minimum growth rate to be "emergent"
            recent_days: Define "recent" window

        Returns:
            List of EmergentTheme objects
        """
        themes = []

        # Split into recent and older
        cutoff = datetime.utcnow() - timedelta(days=recent_days)
        recent = [r for r in self.reviews if r.review_time and r.review_time >= cutoff]
        older = [r for r in self.reviews if r.review_time and r.review_time < cutoff]

        if len(recent) < min_reviews or len(older) < min_reviews:
            return themes

        # Extract keywords from both periods
        recent_keywords = self._extract_all_keywords(recent)
        older_keywords = self._extract_all_keywords(older)

        # Normalize by period length
        recent_days_actual = max(1, recent_days)
        older_days_actual = max(1, (cutoff - min(r.review_time for r in older if r.review_time)).days)

        # Find keywords with significant growth
        for keyword, recent_count in recent_keywords.items():
            older_count = older_keywords.get(keyword, 0)

            # Calculate daily rates
            recent_rate = recent_count / recent_days_actual
            older_rate = older_count / older_days_actual if older_days_actual > 0 else 0

            # Calculate growth
            if older_rate > 0:
                growth = (recent_rate - older_rate) / older_rate
            elif recent_rate > 0:
                growth = 1.0  # New keyword
            else:
                growth = 0

            if growth >= growth_threshold and recent_count >= min_reviews:
                # Find reviews with this keyword
                matching_recent = [
                    r for r in recent
                    if keyword.lower() in r.text.lower()
                ]

                # Get sentiment
                sentiments = [
                    r.sentiment_score if r.sentiment_score is not None
                    else normalize_sentiment(r.rating) if r.rating else 0
                    for r in matching_recent
                ]

                themes.append(EmergentTheme(
                    theme_id=generate_id("thm"),
                    keywords=[keyword],
                    review_count=recent_count,
                    avg_sentiment=safe_mean(sentiments),
                    growth_rate=growth,
                    representative_reviews=[r.review_id for r in matching_recent[:5]],
                    related_chains=list(set(r.chain_id for r in matching_recent if r.chain_id))[:5],
                    related_cities=list(set(r.city for r in matching_recent if r.city))[:5]
                ))

        # Sort by growth rate
        themes.sort(key=lambda t: t.growth_rate, reverse=True)

        logger.info("emergent_themes_detected", count=len(themes))
        return themes[:20]

    def _extract_all_keywords(
        self,
        reviews: List[ReviewData]
    ) -> Dict[str, int]:
        """Extract keyword frequencies from reviews"""
        all_keywords = defaultdict(int)
        for r in reviews:
            keywords = extract_keywords(r.text, top_n=10)
            for kw in keywords:
                all_keywords[kw] += 1
        return dict(all_keywords)

    # ═══════════════════════════════════════════════════════════════════════════
    # CLUSTERING
    # ═══════════════════════════════════════════════════════════════════════════

    def cluster_reviews(
        self,
        reviews: Optional[List[ReviewData]] = None,
        eps: float = 0.3,
        min_samples: int = 3
    ) -> Dict[int, List[ReviewData]]:
        """
        Cluster reviews by semantic similarity

        Args:
            reviews: Reviews to cluster
            eps: DBSCAN epsilon parameter
            min_samples: Minimum samples per cluster

        Returns:
            Dict mapping cluster_id to list of reviews
        """
        reviews = reviews or self.reviews
        reviews = sample_items(reviews, self.config.semantic_max_reviews)

        if len(reviews) < min_samples:
            return {0: reviews}

        # Get embeddings
        embeddings = self._get_embeddings(reviews)

        # Cluster with DBSCAN
        clustering = DBSCAN(eps=eps, min_samples=min_samples, metric='cosine')
        labels = clustering.fit_predict(embeddings)

        # Group by cluster
        clusters = defaultdict(list)
        for review, label in zip(reviews, labels):
            clusters[int(label)].append(review)

        logger.info(
            "reviews_clustered",
            n_clusters=len([l for l in set(labels) if l >= 0]),
            noise_points=len([l for l in labels if l == -1])
        )

        return dict(clusters)

    # ═══════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def _extract_shared_themes(
        self,
        review_a: ReviewData,
        review_b: ReviewData
    ) -> List[str]:
        """Extract shared themes between two reviews"""
        keywords_a = set(extract_keywords(review_a.text, top_n=10))
        keywords_b = set(extract_keywords(review_b.text, top_n=10))
        return list(keywords_a & keywords_b)[:5]

    def _extract_shared_themes_from_groups(
        self,
        reviews_a: List[ReviewData],
        reviews_b: List[ReviewData]
    ) -> List[str]:
        """Extract shared themes between two groups of reviews"""
        keywords_a = set()
        keywords_b = set()

        for r in reviews_a[:10]:
            keywords_a.update(extract_keywords(r.text, top_n=5))
        for r in reviews_b[:10]:
            keywords_b.update(extract_keywords(r.text, top_n=5))

        return list(keywords_a & keywords_b)[:5]

    def get_embedding_stats(self) -> Dict[str, any]:
        """Get statistics about embeddings"""
        return {
            'cached_embeddings': len(self._embeddings_cache),
            'model': self.config.semantic_embedding_model,
            'model_available': self.embedding_model != "unavailable"
        }
