-- Schema for the seismic-risk project (Supabase / PostgreSQL)

create extension if not exists "pgcrypto";

create table if not exists public.earthquakes (
    event_id      text primary key,
    time          timestamptz not null,
    latitude      double precision not null,
    longitude     double precision not null,
    depth_km      double precision,
    magnitude     double precision not null,
    mag_type      text,
    place         text,
    status        text,
    url           text,
    created_at    timestamptz not null default now()
);

create table if not exists public.risk_zones (
    cell_id                 text primary key,
    cell_lat                double precision not null,
    cell_lon                double precision not null,
    n_events                integer not null default 0,
    max_magnitude           double precision not null default 0,
    mean_magnitude          double precision not null default 0,
    mean_depth_km           double precision not null default 0,
    log_energy              double precision not null default 0,
    events_per_year         double precision not null default 0,
    risk_level              text not null check (risk_level in ('Low', 'Medium', 'High')),
    dist_to_mesa_km         double precision,
    dist_to_seismic_nest_km double precision,
    updated_at              timestamptz not null default now()
);

create table if not exists public.predictions (
    id            uuid primary key default gen_random_uuid(),
    created_at    timestamptz not null default now(),
    latitude      double precision not null,
    longitude     double precision not null,
    radius_deg    double precision not null,
    predicted_risk text not null,
    probabilities jsonb,
    features      jsonb
);

create table if not exists public.model_runs (
    id          uuid primary key default gen_random_uuid(),
    created_at  timestamptz not null default now(),
    model_name  text not null,
    metrics     jsonb
);

create index if not exists idx_earthquakes_time on public.earthquakes (time);
create index if not exists idx_earthquakes_mag on public.earthquakes (magnitude);
create index if not exists idx_risk_zones_level on public.risk_zones (risk_level);
create index if not exists idx_predictions_created on public.predictions (created_at);
