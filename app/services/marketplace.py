"""Module marketplace for sharing and discovering modules."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

MARKETPLACE_DIR = Path(__file__).parent.parent.parent / 'marketplace'


def ensure_marketplace_dir():
    """Ensure the marketplace directory exists."""
    MARKETPLACE_DIR.mkdir(parents=True, exist_ok=True)


def list_available_modules():
    """List all available modules in the marketplace."""
    ensure_marketplace_dir()
    modules = []
    
    for json_file in MARKETPLACE_DIR.glob('*.json'):
        try:
            with open(json_file) as f:
                module_info = json.load(f)
                module_info['file'] = json_file.name
                module_info['path'] = str(json_file)
                modules.append(module_info)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f'Failed to read marketplace entry {json_file}: {e}')
    
    return sorted(modules, key=lambda m: m.get('name', ''))


def get_module_info(slug):
    """Get info about a specific marketplace module."""
    json_file = MARKETPLACE_DIR / f'{slug}.json'
    if not json_file.exists():
        return None
    
    try:
        with open(json_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f'Failed to read marketplace entry {json_file}: {e}')
        return None


def publish_module(slug, name, description, version, author, xml_path, tags=None):
    """Publish a module to the marketplace."""
    ensure_marketplace_dir()
    
    marketplace_entry = {
        'slug': slug,
        'name': name,
        'description': description,
        'version': version,
        'author': author,
        'tags': tags or [],
        'published_at': datetime.now(timezone.utc).isoformat(),
        'xml_source': xml_path,
    }
    
    json_file = MARKETPLACE_DIR / f'{slug}.json'
    with open(json_file, 'w') as f:
        json.dump(marketplace_entry, f, indent=2)
    
    logger.info(f'Published module to marketplace: {slug}')
    return marketplace_entry


def remove_module(slug):
    """Remove a module from the marketplace."""
    json_file = MARKETPLACE_DIR / f'{slug}.json'
    if json_file.exists():
        json_file.unlink()
        logger.info(f'Removed module from marketplace: {slug}')
        return True
    return False
