DROP TABLE IF EXISTS stcp_stop_times;
DROP TABLE IF EXISTS stcp_stops;
DROP TABLE IF EXISTS stcp_routes;
DROP TABLE IF EXISTS stcp_trips;
DROP TABLE IF EXISTS stcp_shapes;
DROP TABLE IF EXISTS stcp_calendar_dates;
DROP TABLE IF EXISTS stcp_agency;
DROP TABLE IF EXISTS stcp_feed_info;



DROP TABLE IF EXISTS metro_stop_times;
DROP TABLE IF EXISTS metro_stops;
DROP TABLE IF EXISTS metro_routes;
DROP TABLE IF EXISTS metro_trips;
DROP TABLE IF EXISTS metro_shapes;
DROP TABLE IF EXISTS metro_calendar;
DROP TABLE IF EXISTS metro_calendar_dates;
DROP TABLE IF EXISTS metro_agency;
DROP TABLE IF EXISTS metro_fare_attributes;
DROP TABLE IF EXISTS metro_fare_rules;

CREATE TABLE stcp_stops (
    stop_id TEXT PRIMARY KEY,
    stop_code TEXT,
    stop_name TEXT,
    stop_lat DOUBLE PRECISION,
    stop_lon DOUBLE PRECISION,
    zone_id TEXT,
    stop_url TEXT,
    hostsource TEXT,
    tstamp TIMESTAMP
);

CREATE TABLE stcp_routes (
    route_id TEXT PRIMARY KEY,
    agency_id TEXT,
    route_short_name TEXT,
    route_long_name TEXT,
    route_type INTEGER,
    route_url TEXT,
    route_color TEXT,
    route_text_color TEXT,
    route_sort_order INTEGER,
    hostsource TEXT,
    tstamp TIMESTAMP
);

CREATE TABLE stcp_trips (
    trip_id TEXT PRIMARY KEY,
    route_id TEXT,
    service_id TEXT,
    trip_headsign TEXT,
    wheelchair_accessible INTEGER,
    block_id TEXT,
    direction_id INTEGER,
    shape_id TEXT,
    hostsource TEXT,
    tstamp TIMESTAMP
);

CREATE TABLE stcp_stop_times (
    trip_id TEXT,
    stop_sequence INTEGER,
    arrival_time TEXT,
    departure_time TEXT,
    stop_id TEXT,
    shape_dist_traveled DOUBLE PRECISION,
    timepoint INTEGER,
    hostsource TEXT,
    tstamp TIMESTAMP,
    PRIMARY KEY (trip_id, stop_sequence)
);

CREATE TABLE stcp_shapes (
    shape_id TEXT,
    shape_pt_sequence INTEGER,
    shape_pt_lat DOUBLE PRECISION,
    shape_pt_lon DOUBLE PRECISION,
    shape_dist_traveled DOUBLE PRECISION,
    hostsource TEXT,
    tstamp TIMESTAMP,
    PRIMARY KEY (shape_id, shape_pt_sequence)
);


CREATE TABLE stcp_calendar_dates (
    service_id TEXT,
    date TEXT,
    exception_type INTEGER,
    hostsource TEXT,
    tstamp TIMESTAMP,
    PRIMARY KEY (service_id, date)
);

CREATE TABLE stcp_feed_info (
    feed_publisher_name TEXT,
    feed_publisher_url TEXT,
    feed_lang TEXT,
    feed_start_date TEXT,
    feed_end_date TEXT,
    feed_contact_email TEXT,
    feed_contact_url TEXT,
    feed_version TEXT,
    hostsource TEXT,
    tstamp TIMESTAMP
);

CREATE TABLE stcp_agency (
    agency_id TEXT PRIMARY KEY,
    agency_name TEXT,
    agency_url TEXT,
    agency_timezone TEXT,
    agency_phone TEXT,
    agency_lang TEXT,
    hostsource TEXT,
    tstamp TIMESTAMP
);

CREATE TABLE metro_stops (
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

CREATE TABLE metro_routes (
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

CREATE TABLE metro_trips (
    trip_id TEXT PRIMARY KEY,
    route_id TEXT,
    service_id TEXT,
    trip_headsign TEXT,
    wheelchair_accessible INTEGER,
    direction_id INTEGER,
    block_id TEXT,
    shape_id TEXT,
    hostsource TEXT,
    tstamp TIMESTAMP
);

CREATE TABLE metro_stop_times (
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

CREATE TABLE metro_shapes (
    shape_id TEXT,
    shape_pt_sequence INTEGER,
    shape_pt_lat DOUBLE PRECISION,
    shape_pt_lon DOUBLE PRECISION,
    shape_dist_traveled DOUBLE PRECISION,
    hostsource TEXT,
    tstamp TIMESTAMP,
    PRIMARY KEY (shape_id, shape_pt_sequence)
);

CREATE TABLE metro_calendar (
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


CREATE TABLE metro_calendar_dates (
    service_id TEXT,
    date TEXT,
    exception_type INTEGER,
    hostsource TEXT,
    tstamp TIMESTAMP,
    PRIMARY KEY (service_id, date)
);

CREATE TABLE metro_fare_attributes (
    fare_id TEXT PRIMARY KEY,
    price DOUBLE PRECISION,
    currency_type TEXT,
    payment_method INTEGER,
    transfers INTEGER,
    transfer_duration INTEGER,
    hostsource TEXT,
    tstamp TIMESTAMP
);

CREATE TABLE metro_fare_rules (
    fare_id TEXT,
    route_id TEXT,
    origin_id TEXT,
    destination_id TEXT,
    hostsource TEXT,
    tstamp TIMESTAMP
);

CREATE TABLE metro_agency (
    agency_id TEXT PRIMARY KEY,
    agency_name TEXT,
    agency_url TEXT,
    agency_timezone TEXT,
    agency_lang TEXT,
    hostsource TEXT,
    tstamp TIMESTAMP
);