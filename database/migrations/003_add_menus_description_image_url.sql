-- ========================================
-- Add description, image_url to menus
-- Kitchmatic Database
-- ========================================
--
-- Backend/db_server get_menus API and Main Server handle_get_menus expect
-- description and image_url. This migration adds them to existing menus table.
--
-- Run (pinky_robot_store):
--   psql -h 192.168.0.27 -p 5432 -U deepdive -d pinky_robot_store -f database/migrations/003_add_menus_description_image_url.sql
--

ALTER TABLE menus
ADD COLUMN IF NOT EXISTS description TEXT DEFAULT '',
ADD COLUMN IF NOT EXISTS image_url VARCHAR(500) DEFAULT '';
