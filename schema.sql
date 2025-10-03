-- Database schema for receipts bot
-- This file is executed on bot startup if tables don't exist

CREATE SCHEMA app_receipts_bot;

SET search_path TO 'app_receipts_bot';

CREATE TABLE version(version text primary key);

INSERT INTO version VALUES ('0.0');
