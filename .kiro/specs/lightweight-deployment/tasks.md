# Implementation Plan: Lightweight Deployment

## Overview

This implementation plan transforms the Self-Healing Documentation Engine from a resource-intensive 5-container architecture into a flexible deployment system supporting both full production mode and lightweight development mode. The implementation follows a layered approach: first establishing configuration and abstraction layers, then implementing backend alternatives, and finally integrating everything with deployment configurations.

## Tasks

- [ ] 1. Create configuration system and settings management
  - [x] 1.1 Implement configuration models with deployment modes
    - Create `src/doc_healing/config.py` with Settings class
    - Define DeploymentMode, DatabaseBackend, and QueueBackend enums
    - Add environment variable loading with pydantic-settings
    - _Requirements: 4.2, 8.1_
  
  - [ ]* 1.2 Write property test for environment variable configuration
    - **Property 7: Environment Variable Configuration**
    - **Validates: Requirements 4.2, 8.1**
  
  - [ ]* 1.3 Write unit tests for configuration validation
    - Test invalid configuration combinations
    - Test default values
    - Test environment variable precedence
    - _Requirements: 4.2_

- [ ] 2. Implement database abstraction layer
  - [x] 2.1 Create database connection factory with backend support
    - Implement `get_database_url()` function in `src/doc_healing/db/connection.py`
    - Add SQLite-specific configuration (check_same_thread=False)
    - Add PostgreSQL-specific configuration (connection pooling)
    - Update `get_db()` dependency to use factory
    - _Requirements: 2.1, 2.2_
  
  - [x] 2.2 Update database models for cross-database compatibility
    - Review existing models in `src/doc_healing/db/models.py`
    - Replace PostgreSQL-specific types with generic SQLAlchemy types
    - Ensure all models work with both PostgreSQL and SQLite
    - _Requirements: 2.3_
  
  - [ ]* 2.3 Write property test for database file location configuration
    - **Property 2: Database File Location Configuration**
    - **Validates: Requirements 2.2**
  
  - [ ]* 2.4 Write property test for migration compatibility
    - **Property 3: Migration Compatibility Across Databases**
    - **Validates: Requirements 2.3, 2.4**
  
  - [ ]* 2.5 Write unit tests for database connection errors
    - Test SQLite file permission errors
    - Test PostgreSQL connection failures
    - Test database URL parsing
    - _Requirements: 2.1, 2.2_

- [x] 3. Checkpoint - Ensure database abstraction tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement queue abstraction layer
  - [x] 4.1 Create queue backend interface
    - Create `src/doc_healing/queue/base.py` with QueueBackend abstract class
    - Define Task dataclass
    - Define abstract methods: enqueue, get_task, mark_complete, mark_failed
    - _Requirements: 3.3_
  
  - [x] 4.2 Implement Redis queue backend
    - Create `src/doc_healing/queue/redis_backend.py`
    - Implement RedisQueueBackend using existing RQ integration
    - Wrap existing RQ functionality with new interface
    - _Requirements: 3.3_
  
  - [x] 4.3 Implement in-memory queue backend
    - Create `src/doc_healing/queue/memory_backend.py`
    - Implement MemoryQueueBackend with threading.Queue
    - Add synchronous execution mode support
    - Add worker thread pool for async mode
    - _Requirements: 3.1, 3.2_
  
  - [x] 4.4 Create queue backend factory
    - Create `src/doc_healing/queue/factory.py`
    - Implement `get_queue_backend()` function
    - Add backend selection based on configuration
    - _Requirements: 3.1_
  
  - [ ]* 4.5 Write property test for task execution mode consistency
    - **Property 4: Task Execution Mode Consistency**
    - **Validates: Requirements 3.2**
  
  - [ ]* 4.6 Write property test for queue interface consistency
    - **Property 5: Queue Interface Consistency**
    - **Validates: Requirements 3.3**
  
  - [ ]* 4.7 Write property test for queue persistence behavior
    - **Property 6: Queue Persistence Behavior**
    - **Validates: Requirements 3.4**
  
  - [ ]* 4.8 Write unit tests for memory queue edge cases
    - Test queue full scenarios
    - Test thread exhaustion
    - Test empty queue behavior
    - _Requirements: 3.1, 3.2_

- [x] 5. Checkpoint - Ensure queue abstraction tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement unified worker process
  - [x] 6.1 Create unified worker implementation
    - Create `src/doc_healing/workers/unified.py`
    - Implement UnifiedWorker class that handles all queue types
    - Add support for sync and async processing modes
    - Add graceful shutdown handling
    - _Requirements: 1.2, 1.3_
  
  - [x] 6.2 Update existing worker tasks to use queue abstraction
    - Update webhook processing tasks in `src/doc_healing/workers/tasks.py`
    - Update validation tasks to use queue backend interface
    - Update healing tasks to use queue backend interface
    - _Requirements: 1.2_
  
  - [ ]* 6.3 Write property test for task processing across all types
    - **Property 1: Task Processing Across All Types**
    - **Validates: Requirements 1.2**
  
  - [ ]* 6.4 Write unit tests for unified worker
    - Test worker startup and shutdown
    - Test task routing to correct handlers
    - Test error handling in worker
    - _Requirements: 1.3_

- [ ] 7. Update API to use abstraction layers
  - [x] 7.1 Update API startup to initialize correct backends
    - Modify `src/doc_healing/api/main.py` startup event
    - Add logging for deployment mode and backend configuration
    - Initialize database with create_all for SQLite support
    - _Requirements: 5.1_
  
  - [x] 7.2 Update API endpoints to use queue factory
    - Replace direct RQ usage with `get_queue_backend()`
    - Update webhook endpoints
    - Update validation endpoints
    - Update healing endpoints
    - _Requirements: 5.1, 5.2, 5.3_
  
  - [ ]* 7.3 Write property test for webhook endpoint availability
    - **Property 8: Webhook Endpoint Availability**
    - **Validates: Requirements 5.1**
  
  - [ ]* 7.4 Write property test for validation functionality
    - **Property 9: Validation Functionality**
    - **Validates: Requirements 5.2**
  
  - [ ]* 7.5 Write property test for healing functionality
    - **Property 10: Healing Functionality**
    - **Validates: Requirements 5.3**
  
  - [ ]* 7.6 Write unit tests for API in lightweight mode
    - Test API starts without external dependencies
    - Test health check endpoint
    - Test error responses
    - _Requirements: 1.4, 5.1_

- [x] 8. Checkpoint - Ensure API integration tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Create deployment configurations
  - [x] 9.1 Create lightweight docker-compose configuration
    - Create `docker-compose.lightweight.yml`
    - Configure with SQLite and memory queue
    - Use single unified worker container
    - Minimize resource limits
    - _Requirements: 1.1, 4.1_
  
  - [ ] 9.2 Create environment configuration templates
    - Create `.env.lightweight` template
    - Create `.env.full` template
    - Document all configuration options
    - _Requirements: 4.2_
  
  - [ ] 9.3 Create Makefile commands for deployment modes
    - Add `make dev-lightweight` command
    - Add `make dev-full` command
    - Add `make dev-native` command (no Docker)
    - Add `make switch-mode` command
    - _Requirements: 4.3_
  
  - [ ]* 9.4 Write unit tests for deployment configurations
    - Test docker-compose.lightweight.yml is valid
    - Test environment templates are complete
    - Test Makefile commands execute successfully
    - _Requirements: 4.1, 4.3_

- [ ] 10. Implement monitoring and logging
  - [ ] 10.1 Add memory usage monitoring
    - Create `src/doc_healing/monitoring/memory.py`
    - Implement memory tracking using psutil
    - Add periodic logging of memory metrics
    - _Requirements: 6.4_
  
  - [ ] 10.2 Add deployment mode logging
    - Log active deployment mode on startup
    - Log backend configurations (database, queue)
    - Log resource usage periodically
    - _Requirements: 6.4_
  
  - [ ]* 10.3 Write property test for memory metrics logging
    - **Property 11: Memory Metrics Logging**
    - **Validates: Requirements 6.4**

- [ ] 11. Create data migration utilities
  - [ ] 11.1 Implement SQLite to PostgreSQL migration script
    - Create `scripts/migrate_sqlite_to_postgres.py`
    - Export data from SQLite
    - Import data to PostgreSQL
    - Verify data integrity
    - _Requirements: 8.3_
  
  - [ ] 11.2 Implement PostgreSQL to SQLite migration script
    - Create `scripts/migrate_postgres_to_sqlite.py`
    - Export data from PostgreSQL
    - Import data to SQLite
    - Handle data type conversions
    - _Requirements: 8.3_
  
  - [ ]* 11.3 Write unit tests for migration scripts
    - Test data preservation during migration
    - Test error handling
    - Test rollback procedures
    - _Requirements: 8.3_

- [ ] 12. Update documentation
  - [ ] 12.1 Update README with lightweight deployment instructions
    - Add "Lightweight Development Mode" section
    - Document prerequisites (Python 3.11+, optional Docker)
    - Add quick start commands for lightweight mode
    - Document configuration options
    - _Requirements: 7.1, 7.2, 7.4_
  
  - [ ] 12.2 Document deployment mode differences
    - Create comparison table (full vs lightweight vs hybrid)
    - Document memory usage expectations
    - Document feature availability in each mode
    - Add troubleshooting section
    - _Requirements: 7.3, 8.4_
  
  - [ ] 12.3 Add configuration reference documentation
    - Document all environment variables
    - Provide configuration examples
    - Document mode switching procedures
    - _Requirements: 4.4, 8.4_

- [ ] 13. Final integration testing
  - [ ]* 13.1 Run full integration test suite
    - Test complete workflow in lightweight mode
    - Test mode switching (full → lightweight → full)
    - Test data migration between databases
    - Test concurrent operations with memory queue
    - _Requirements: 1.1, 1.2, 5.1, 5.2, 5.3, 8.1, 8.2_
  
  - [ ]* 13.2 Perform memory usage validation
    - Measure baseline memory in full mode
    - Measure memory in lightweight mode
    - Verify lightweight mode uses < 50% of full mode
    - Document actual memory usage
    - _Requirements: 6.1, 6.2_

- [ ] 14. Final checkpoint - Verify all requirements met
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. LLM Integration (The "Healing" Engine)
  - [ ] 15.1 Set up AWS Bedrock Access
    - Navigate to Amazon Bedrock in the AWS Console
    - Request model access for **Anthropic Claude 3.5 Sonnet** (best for code) and **Claude 3 Haiku** (faster/cheaper fallback)
  - [ ] 15.2 Implement LLM Client Layer
    - Install `boto3` (AWS SDK for Python)
    - Create `src/doc_healing/llm/bedrock_client.py`
    - Implement a function to send a prompt to Claude via Bedrock and parse the returned code
  - [ ] 15.3 Create Healing Prompts
    - Create `src/doc_healing/llm/prompts.py`
    - Draft system prompts that instruct the LLM: "You are a documentation auto-fixer. Given this broken code snippet and this error log, output only the corrected code snippet."
  - [ ] 15.4 Integrate LLM into Unified Worker
    - Update the healing task in `src/doc_healing/workers/tasks.py` to call the `bedrock_client` when validation fails
    - Ensure the worker handles API rate limits or timeout errors gracefully

- [ ] 16. AWS Cloud Deployment (Production Infrastructure)
  - [ ] 16.1 Container Registry Setup (AWS ECR)
    - Create an Amazon Elastic Container Registry (ECR) repository
    - Authenticate Docker with ECR
    - Build and push your `full` production Docker image to ECR
  - [ ] 16.2 Database & Queue Setup
    - Provision an **Amazon RDS** instance (PostgreSQL) for production data
    - Provision an **Amazon ElastiCache** instance (Redis) for the production task queue
    - Store the connection URLs in AWS Systems Manager Parameter Store or Secrets Manager
  - [ ] 16.3 Compute Setup (AWS ECS Fargate)
    - Create an Amazon ECS Cluster
    - Create a Task Definition for the **API Server** (mapping port 80/443 to FastAPI)
    - Create a Task Definition for the **Unified Worker** (running the queue listener)
    - Set environment variables in the Task Definitions to use the `.env.full` equivalents (pointing to RDS and ElastiCache)
  - [ ] 16.4 Network & Webhook Exposure
    - Set up an Application Load Balancer (ALB) to route internet traffic to your API Service
    - Test the live URL with a mock GitHub webhook payload

- [ ] 17. Security & CI/CD
  - [ ] 17.1 Implement Secrets Management
    - Move GitHub Webhook secrets, Bedrock credentials, and DB passwords to AWS Secrets Manager
    - Update `config.py` to fetch from AWS Secrets Manager in production mode
  - [ ] 17.2 GitHub Actions Pipeline
    - Create `.github/workflows/deploy.yml`
    - Add steps to: run tests -> build docker image -> push to ECR -> update ECS service
