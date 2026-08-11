# Retrieval Holdout

Legacy cases have been inspected during development, so they are regression evidence rather than a blind quality test. Holdout v2 is a separate frozen set of 40 public fictional queries, labelled from the curated Corpus before retrieval is run. Its manifest records the dataset hash and Corpus hash. If a label is disputed, record `LABEL_REVIEW_REQUIRED`; do not rewrite the dataset after observing scores.
