CREATE EXTENSION IF NOT EXISTS vector;

-- Plus petite unité citable ; le jeu d'évaluation référence ces identifiants.
CREATE TABLE passages (
    id             text PRIMARY KEY,
    document_id    text NOT NULL,
    kind           text NOT NULL,
    citation_label text NOT NULL,
    text           text NOT NULL,
    url            text NOT NULL,
    position       integer NOT NULL,
    chapter        text,
    section        text,
    article        text,
    paragraph      text,
    point          text,
    heading        text,
    amended_by     text[] NOT NULL DEFAULT '{}',
    version_date   text
);

-- Unité de recherche. passage_ids relie chaque chunk aux passages qu'il recouvre.
CREATE TABLE chunks (
    id          text PRIMARY KEY,
    strategy    text NOT NULL,
    text        text NOT NULL,
    text_sha256 text NOT NULL,
    passage_ids text[] NOT NULL,
    position    integer NOT NULL,
    -- Recherche lexicale (Phase 3).
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('french', text)) STORED
);
CREATE INDEX chunks_strategy_idx ON chunks (strategy);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);

-- Cache d'embeddings : un texte n'est encodé qu'une fois par modèle.
-- Dimension libre pour faire cohabiter plusieurs modèles ; recherche exacte
-- (quelques milliers de lignes), un index HNSW sera évalué en Phase 3.
CREATE TABLE embeddings (
    model       text NOT NULL,
    text_sha256 text NOT NULL,
    embedding   vector NOT NULL,
    PRIMARY KEY (model, text_sha256)
);
