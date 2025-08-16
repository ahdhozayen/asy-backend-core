# API Response Format Documentation

## Overview

This document outlines the standardized API response format used across all endpoints in the ASY Document Management System. Maintaining a consistent response format simplifies frontend integration, improves error handling, and provides a better developer experience.

## Standard Response Format

All API endpoints return responses in the following standardized format:

```json
{
  "count": 1,
  "next": "http://example.com/api/resource/?page=2",
  "previous": null,
  "results": [
    {
      // Resource data
    }
  ]
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `count` | integer | Total number of items available (regardless of pagination) |
| `next` | string or null | URL to the next page of results (null if on last page) |
| `previous` | string or null | URL to the previous page of results (null if on first page) |
| `results` | array | Array containing the requested resources |

## Response Types

### List Responses

When retrieving multiple resources, the `results` array contains all items for the current page:

```json
{
  "count": 42,
  "next": "http://example.com/api/documents/?page=2",
  "previous": null,
  "results": [
    { "id": 1, "title": "Document 1", ... },
    { "id": 2, "title": "Document 2", ... },
    ...
  ]
}
```

### Single Resource Responses

When retrieving a single resource (e.g., GET /api/documents/1/), the resource is still wrapped in the standard format with the resource object inside the `results` array:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    { "id": 1, "title": "Document 1", ... }
  ]
}
```

### Create/Update Responses

When creating or updating a resource, the response follows the same format with the newly created or updated resource in the `results` array:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    { "id": 1, "title": "New Document", ... }
  ]
}
```

### Delete Responses

When deleting a resource, the response includes a success message:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    { "message": "Resource with ID 1 deleted successfully" }
  ]
}
```

### Error Responses

Error responses maintain the same structure but include an additional `errors` field:

```json
{
  "count": 0,
  "next": null,
  "previous": null,
  "results": [],
  "errors": {
    "field_name": ["Error message"],
    "non_field_errors": ["General error message"]
  }
}
```

## Implementation

The standardized response format is implemented using:

1. A custom pagination class (`StandardResultsSetPagination` in `ASY_CORE/pagination.py`)
2. Consistent response formatting in all viewsets and API views
3. Wrapper methods for non-paginated responses to maintain format consistency

## Benefits

- **Consistency**: All endpoints return the same structure, simplifying frontend integration
- **Pagination Support**: Built-in pagination information for all responses
- **Predictable Error Handling**: Errors follow the same format as successful responses
- **Frontend Compatibility**: Frontend can use the same parsing logic for all API responses

## Usage in Frontend

Frontend applications should:

1. Always expect the standardized format with `count`, `next`, `previous`, and `results` fields
2. Extract data from the `results` array, even for single-resource responses
3. Check for the presence of an `errors` field to handle error cases
4. Use the `count` field to display total items available
5. Use `next` and `previous` URLs for pagination controls

## Supported Endpoints

All API endpoints in the system follow this standardized format, including:

- Document-related endpoints (`/api/documents/`)
- Department-related endpoints (`/api/departments/`)
- User-related endpoints (`/api/users/`)
- Authentication endpoints (`/api/auth/`)
- Statistics endpoints (`/api/documents/stats/`)
