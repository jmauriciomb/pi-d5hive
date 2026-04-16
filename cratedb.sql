DROP TABLE IF EXISTS stop_times;
DROP TABLE IF EXISTS stops;
DROP TABLE IF EXISTS routes;
DROP TABLE IF EXISTS trips;
DROP TABLE IF EXISTS shapes;
DROP TABLE IF EXISTS calendar;
DROP TABLE IF EXISTS calendar_dates;
DROP TABLE IF EXISTS agency;
DROP TABLE IF EXISTS transfers;
DROP TABLE IF EXISTS fare_attributes;
DROP TABLE IF EXISTS fare_rules;

CREATE TABLE stops (
    stop_id TEXT PRIMARY KEY,
    stop_code TEXT,
    stop_name TEXT,
    stop_desc TEXT,
    stop_lat DOUBLE PRECISION,
    stop_lon DOUBLE PRECISION,
    zone_id TEXT,
    stop_url TEXT,
    hostsource TEXT,
    tstamp TIMESTAMP
);
CREATE TABLE routes (
    route_id TEXT PRIMARY KEY,
    agency_id TEXT,
    route_short_name TEXT,
    route_long_name TEXT,
    route_desc TEXT,
    route_type INTEGER,
    route_url TEXT,
    route_color TEXT,
    route_text_color TEXT,
    hostsource TEXT,
    tstamp TIMESTAMP
);
CREATE TABLE trips (
    trip_id TEXT PRIMARY KEY,
    route_id TEXT,
    service_id TEXT,
    trip_headsign TEXT,
    direction_id INTEGER,
    block_id TEXT,
    shape_id TEXT,
    hostsource TEXT,
    tstamp TIMESTAMP
);
CREATE TABLE stop_times (
    trip_id TEXT,
    stop_sequence INTEGER,
    arrival_time TEXT,
    departure_time TEXT,
    stop_id TEXT,
    stop_headsign TEXT,
    pickup_type INTEGER,
    drop_off_type INTEGER,
    shape_dist_traveled DOUBLE PRECISION,
    hostsource TEXT,
    tstamp TIMESTAMP,
    PRIMARY KEY (trip_id, stop_sequence)
);
CREATE TABLE shapes (
    shape_id TEXT,
    shape_pt_sequence INTEGER,
    shape_pt_lat DOUBLE PRECISION,
    shape_pt_lon DOUBLE PRECISION,
    shape_dist_traveled DOUBLE PRECISION,
    hostsource TEXT,
    tstamp TIMESTAMP,
    PRIMARY KEY (shape_id, shape_pt_sequence)
);
CREATE TABLE calendar (
    service_id TEXT PRIMARY KEY,
    monday INTEGER,
    tuesday INTEGER,
    wednesday INTEGER,
    thursday INTEGER,
    friday INTEGER,
    saturday INTEGER,
    sunday INTEGER,
    start_date TEXT,
    end_date TEXT,
    hostsource TEXT,
    tstamp TIMESTAMP
);
CREATE TABLE agency (
    agency_id TEXT PRIMARY KEY,
    agency_name TEXT,
    agency_url TEXT,
    agency_timezone TEXT,
    agency_lang TEXT,
    hostsource TEXT,
    tstamp TIMESTAMP
);

