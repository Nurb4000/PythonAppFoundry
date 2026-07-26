"""OpenAPI/Swagger specification generator for dynamic routes.

Generates a Swagger-compatible JSON spec from the platform's route table.
"""
import json
from datetime import datetime, timezone


def generate_openapi_spec(app, db_session):
    """Generate an OpenAPI 3.0 spec from all registered routes."""
    from app.models import Route, Module, Script
    
    routes = db_session.query(Route).all()
    modules = {m.id: m for m in db.session.query(Module).all()}
    
    paths = {}
    components = {
        'schemas': {
            'Error': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string'},
                    'status_code': {'type': 'integer'}
                }
            }
        },
        'securitySchemes': {
            'ApiKey': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-API-Key'
            }
        }
    }
    
    for route in routes:
        module = modules.get(route.module_id)
        if not module or not module.enabled:
            continue
        
        # Build path
        path = route.slug if route.slug != '/' else '/'
        if not path.startswith('/'):
            path = '/' + path
        
        # Get script info for description
        script_desc = ''
        if route.script:
            desc = route.script.description or ''
            if desc:
                script_desc = desc[:200]  # Limit description length
        
        # Build operation
        methods = [m.strip().upper() for m in route.methods.split(',')]
        
        for method in methods:
            operation = {
                'summary': route.title or f'{module.name} - {route.slug}',
                'description': script_desc or f'Route: {route.slug}\nModule: {module.name}',
                'tags': [module.name],
                'responses': {
                    '200': {
                        'description': 'Successful response',
                        'content': {
                            'text/html': {
                                'schema': {'type': 'string'}
                            }
                        }
                    }
                },
            }
            
            # Add auth requirement
            if route.auth_required:
                operation['security'] = [{'ApiKey': []}]
            
            # Add form parameters if route has a form
            if route.form:
                operation['requestBody'] = {
                    'content': {
                        'application/x-www-form-urlencoded': {
                            'schema': {
                                'type': 'object',
                                'properties': {}
                            }
                        }
                    }
                }
            
            if path not in paths:
                paths[path] = {}
            paths[path][method.lower()] = operation
    
    # Add API endpoints
    paths['/__api/modules'] = {
        'get': {
            'summary': 'List all modules',
            'tags': ['API'],
            'responses': {'200': {'description': 'Module list'}}
        }
    }
    
    paths['/__api/webhook/{slug}'] = {
        'post': {
            'summary': 'Trigger webhook',
            'tags': ['Webhooks'],
            'parameters': [
                {
                    'name': 'slug',
                    'in': 'path',
                    'required': True,
                    'schema': {'type': 'string'}
                }
            ],
            'responses': {'200': {'description': 'Webhook triggered'}}
        }
    }
    
    spec = {
        'openapi': '3.0.0',
        'info': {
            'title': f'{app.config.get("SITE_NAME", "PythonAppFoundry")} API',
            'version': '1.0.0',
            'description': 'Auto-generated OpenAPI specification for PythonAppFoundry dynamic routes.',
            'contact': {
                'name': 'Platform Admin'
            }
        },
        'servers': [
            {
                'url': f'{app.config.get("SERVER_URL", "http://localhost:5000")}',
                'description': 'Development server'
            }
        ],
        'paths': paths,
        'components': components,
        'tags': list(set(tag for path_ops in paths.values() for op in path_ops.values() for tag in op.get('tags', [])))
    }
    
    return spec


def export_openapi_json(app, db_session):
    """Export OpenAPI spec as JSON string."""
    spec = generate_openapi_spec(app, db_session)
    return json.dumps(spec, indent=2, default=str)
