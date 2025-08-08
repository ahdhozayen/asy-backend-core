# ASY Document Management System - Backend

This is the backend API for the Alexandria Shipyard Document Management System, built with Django and Django REST Framework.

## Features

- User authentication and authorization with JWT
- Document management with file uploads
- Document review workflow
- Digital signatures
- Role-based access control
- RESTful API with Swagger documentation

## Prerequisites

- Python 3.10+
- PostgreSQL 13+
- Node.js 18+ (for frontend)

## Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ASY_Document_Management/ASY_CORE
   ```

2. **Create and activate a virtual environment**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the project root with the following content:
   ```env
   DEBUG=True
   SECRET_KEY=your-secret-key
   DATABASE_URL=postgres://user:password@localhost:5432/asy_docs
   ALLOWED_HOSTS=localhost,127.0.0.1
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create a superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run the development server**
   ```bash
   python manage.py runserver
   ```

## API Documentation

Once the server is running, you can access the API documentation at:
- Swagger UI: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/

## Project Structure

```
ASY_CORE/
├── ASY_CORE/              # Project settings
├── documents/             # Documents app
│   ├── migrations/        # Database migrations
│   ├── models.py          # Data models
│   ├── serializers.py     # API serializers
│   ├── views.py           # API views
│   └── urls.py            # URL routing
├── users/                 # Users app
│   ├── migrations/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
├── manage.py              # Django management script
└── requirements.txt       # Python dependencies
```

## API Endpoints

### Authentication

- `POST /api/auth/login/` - User login
- `POST /api/auth/logout/` - User logout
- `GET /api/auth/profile/` - Get current user profile
- `PUT /api/auth/profile/` - Update current user profile
- `POST /api/auth/change-password/` - Change user password

### Users

- `GET /api/users/` - List all users (admin/CEO only)
- `POST /api/users/` - Create a new user
- `GET /api/users/{id}/` - Get user details
- `PUT /api/users/{id}/` - Update user (admin/CEO only)
- `DELETE /api/users/{id}/` - Delete user (admin only)

### Documents

- `GET /api/documents/` - List all documents
- `POST /api/documents/` - Create a new document
- `GET /api/documents/{id}/` - Get document details
- `PUT /api/documents/{id}/` - Update document
- `DELETE /api/documents/{id}/` - Delete document
- `POST /api/documents/{id}/change_status/` - Change document status

### Attachments

- `GET /api/attachments/` - List all attachments
- `POST /api/attachments/` - Upload a new attachment
- `GET /api/attachments/{id}/` - Get attachment details
- `DELETE /api/attachments/{id}/` - Delete attachment

### Signatures

- `GET /api/signatures/` - List all signatures
- `POST /api/signatures/` - Create a new signature
- `GET /api/signatures/{id}/` - Get signature details

## Testing

To run the test suite:

```bash
pytest
```

## Deployment

For production deployment, consider using:

1. **Web Server**: Nginx or Apache
2. **Application Server**: Gunicorn or uWSGI
3. **Database**: PostgreSQL
4. **Media Storage**: AWS S3 or Azure Blob Storage
5. **Caching**: Redis or Memcached

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
