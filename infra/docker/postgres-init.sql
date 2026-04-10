-- JurisIA — PostgreSQL Init Script
-- Exécuté automatiquement au premier démarrage du container PostgreSQL

-- Extensions nécessaires
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- Recherche full-text fuzzy
CREATE EXTENSION IF NOT EXISTS "unaccent";  -- Recherche sans accents (utile pour le juridique)

-- Base de données staging (créée si elle n'existe pas)
SELECT 'CREATE DATABASE jurisai_staging'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'jurisai_staging')\gexec

-- Commentaire de documentation
COMMENT ON DATABASE jurisai_dev IS 'JurisIA - Base de données développement local';
