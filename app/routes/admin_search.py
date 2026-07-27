from flask import Blueprint, request, redirect, url_for, flash, jsonify
from app.services.csrf import csrf_protect
from app.services.admin_utils import admin_required, render_admin
from app.services.audit import log_audit

search_bp = Blueprint('search', __name__)


@search_bp.route('/')
@admin_required
def search_page():
    """Global search page."""
    query = request.args.get('q', '').strip()
    results = {}
    
    if query:
        from app.services.search import search_all
        results = search_all(query)
    
    total_results = sum(len(v) for v in results.values())
    
    return render_admin('Search', 'admin/search/index.html', 
                       query=query, results=results, total_results=total_results)


@search_bp.route('/api')
@admin_required
def search_api():
    """API endpoint for AJAX search."""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'error': 'No search query provided'}), 400
    
    from app.services.search import search_all
    results = search_all(query, limit=20)
    
    # Flatten results for API response
    flat_results = []
    for entity_type, items in results.items():
        for item in items:
            item['entity_type'] = entity_type
            flat_results.append(item)
    
    return jsonify({
        'query': query,
        'total_results': len(flat_results),
        'results': flat_results[:50],  # Limit to 50 total
    })
