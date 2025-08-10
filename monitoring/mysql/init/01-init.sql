CREATE DATABASE IF NOT EXISTS stocks_monitor_db;

CREATE USER IF NOT EXISTS 'stocks_app'@'%' IDENTIFIED BY 'stocks_app_pass_ChangeMe!';
GRANT ALL PRIVILEGES ON stocks_monitor_db.* TO 'stocks_app'@'%';

CREATE USER IF NOT EXISTS 'exporter'@'%' IDENTIFIED BY 'exporter_pass_change_me';
GRANT PROCESS, REPLICATION CLIENT, SELECT ON *.* TO 'exporter'@'%';

FLUSH PRIVILEGES;
