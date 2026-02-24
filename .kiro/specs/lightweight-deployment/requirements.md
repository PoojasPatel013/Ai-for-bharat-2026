# Requirements Document

## Introduction

The Self-Healing Documentation Engine currently runs 5 Docker containers (postgres, redis, api, and 3 separate worker processes) which is too resource-intensive for development on an 8GB RAM laptop. This feature will optimize the deployment architecture to reduce memory footprint while maintaining core functionality for local development environments.

## Glossary

- **System**: The Self-Healing Documentation Engine application
- **Lightweight_Mode**: A simplified deployment configuration optimized for low-memory environments
- **Worker_Process**: A background process that handles asynchronous tasks (webhooks, validation, healing)
- **Container**: A Docker container running a service
- **Core_Functionality**: API server and basic validation capabilities
- **Development_Environment**: A local machine setup used for development and testing
- **Memory_Footprint**: The total RAM consumed by all running services
- **SQLite**: A lightweight file-based database alternative to PostgreSQL
- **In_Memory_Queue**: A queue system that runs within the application process without external dependencies

## Requirements

### Requirement 1: Reduce Container Count

**User Story:** As a developer with an 8GB RAM laptop, I want to run the application with fewer Docker containers, so that I can develop locally without exhausting system resources.

#### Acceptance Criteria

1. WHEN running in Lightweight_Mode, THE System SHALL use a maximum of 2 Docker containers
2. WHEN combining Worker_Processes, THE System SHALL maintain the ability to process webhooks, validation, and healing tasks
3. THE System SHALL provide a single unified worker process that handles all background tasks
4. WHEN starting the application, THE System SHALL allow running the API without Docker containers

### Requirement 2: Provide Lightweight Database Option

**User Story:** As a developer, I want to use a lightweight database for local development, so that I can reduce memory consumption and simplify setup.

#### Acceptance Criteria

1. WHERE Lightweight_Mode is enabled, THE System SHALL support SQLite as a database option
2. WHEN using SQLite, THE System SHALL store the database file in a configurable local directory
3. THE System SHALL maintain database schema compatibility between PostgreSQL and SQLite
4. WHEN switching between PostgreSQL and SQLite, THE System SHALL use the same Alembic migrations

### Requirement 3: Simplify Queue Management

**User Story:** As a developer, I want to eliminate Redis dependency for local development, so that I can reduce the number of running services.

#### Acceptance Criteria

1. WHERE Lightweight_Mode is enabled, THE System SHALL support an In_Memory_Queue as an alternative to Redis
2. WHEN using In_Memory_Queue, THE System SHALL process tasks synchronously or with threading
3. THE System SHALL maintain the same task interface regardless of queue backend
4. WHEN the application restarts, THE System SHALL handle queue persistence appropriately for each backend

### Requirement 4: Provide Development Mode Configuration

**User Story:** As a developer, I want a simple command to start the application in lightweight mode, so that I can quickly begin development without complex setup.

#### Acceptance Criteria

1. THE System SHALL provide a docker-compose configuration file specifically for Lightweight_Mode
2. WHEN starting in Lightweight_Mode, THE System SHALL use environment variables to configure lightweight options
3. THE System SHALL provide a Makefile or script with a single command to start Lightweight_Mode
4. THE System SHALL document all configuration options for Lightweight_Mode in the README

### Requirement 5: Maintain Core Functionality

**User Story:** As a developer, I want core validation features to work in lightweight mode, so that I can test and develop the main application features.

#### Acceptance Criteria

1. WHEN running in Lightweight_Mode, THE System SHALL support API endpoints for webhook handling
2. WHEN running in Lightweight_Mode, THE System SHALL support code validation functionality
3. WHEN running in Lightweight_Mode, THE System SHALL support basic healing functionality
4. THE System SHALL clearly document any features that are disabled or limited in Lightweight_Mode

### Requirement 6: Optimize Memory Usage

**User Story:** As a developer with limited RAM, I want the application to consume significantly less memory, so that I can run other development tools simultaneously.

#### Acceptance Criteria

1. WHEN running in Lightweight_Mode, THE System SHALL consume no more than 2GB of total RAM
2. WHEN using SQLite and In_Memory_Queue, THE System SHALL eliminate external service memory overhead
3. THE System SHALL provide memory usage documentation comparing full mode vs Lightweight_Mode
4. WHEN monitoring resource usage, THE System SHALL log memory consumption metrics

### Requirement 7: Provide Clear Setup Instructions

**User Story:** As a new developer, I want clear instructions for setting up the lightweight deployment, so that I can start contributing quickly.

#### Acceptance Criteria

1. THE System SHALL provide step-by-step setup instructions in the README for Lightweight_Mode
2. THE System SHALL document prerequisites for Lightweight_Mode (Python, Docker optional)
3. THE System SHALL provide troubleshooting guidance for common setup issues
4. THE System SHALL include example commands for starting, stopping, and testing the application

### Requirement 8: Support Gradual Migration

**User Story:** As a developer, I want to easily switch between lightweight and full deployment modes, so that I can test in different environments.

#### Acceptance Criteria

1. THE System SHALL use environment variables to toggle between deployment modes
2. WHEN switching modes, THE System SHALL preserve database data where possible
3. THE System SHALL provide migration scripts for moving data between SQLite and PostgreSQL
4. THE System SHALL document the differences between deployment modes clearly
