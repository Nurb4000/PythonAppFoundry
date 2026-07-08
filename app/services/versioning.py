import difflib
import logging
from datetime import datetime, timezone

from app import db
from app.models import Module, ModuleVersion, User
from app.services.bundle import export_module

logger = logging.getLogger(__name__)


def create_version(module_id, comment='', user_id=None):
    """Create a version snapshot of the current module state."""
    module = db.session.get(Module, module_id)
    if not module:
        raise ValueError(f'Module with id {module_id} not found')

    # Generate version number
    existing_versions = ModuleVersion.query.filter_by(
        module_id=module_id
    ).order_by(ModuleVersion.id.desc()).all()

    if existing_versions:
        last_version = existing_versions[0].version_number
        try:
            parts = last_version.split('.')
            if len(parts) == 3:
                major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
                new_version = f'{major}.{minor}.{patch + 1}'
            else:
                new_version = f'{len(existing_versions) + 1}.0.0'
        except (ValueError, IndexError):
            new_version = f'{len(existing_versions) + 1}.0.0'
    else:
        new_version = '1.0.0'

    # Export current module state
    snapshot_xml = export_module(module)

    # Create version record
    version = ModuleVersion(
        module_id=module_id,
        version_number=new_version,
        snapshot_xml=snapshot_xml,
        comment=comment,
        created_by_id=user_id,
        is_current=True,
    )

    # Mark all previous versions as not current
    for v in existing_versions:
        v.is_current = False

    db.session.add(version)
    db.session.commit()

    logger.info(f'Created version {new_version} for module {module.name}')
    return version


def get_versions(module_id):
    """Get all versions for a module, ordered by creation date (newest first)."""
    return ModuleVersion.query.filter_by(
        module_id=module_id
    ).order_by(ModuleVersion.created_at.desc()).all()


def get_version(version_id):
    """Get a specific version by ID."""
    return db.session.get(ModuleVersion, version_id)


def restore_version(version_id):
    """Restore a module to a previous version."""
    version = db.session.get(ModuleVersion, version_id)
    if not version:
        raise ValueError(f'Version with id {version_id} not found')

    module = version.module

    # Import the snapshot (this will delete current children and recreate them)
    from app.services.bundle import import_module
    try:
        restored_module = import_module(version.snapshot_xml, update_existing=True, module_id=module.id)
        
        # Update the module's version to match the restored version
        restored_module.version = version.version_number
        db.session.commit()

        logger.info(f'Restored module {module.name} to version {version.version_number}')
        return restored_module
    except Exception as e:
        db.session.rollback()
        raise ValueError(f'Failed to restore version: {str(e)}')


def diff_versions(version_id_1, version_id_2):
    """Get a diff between two versions."""
    v1 = db.session.get(ModuleVersion, version_id_1)
    v2 = db.session.get(ModuleVersion, version_id_2)

    if not v1 or not v2:
        raise ValueError('One or both versions not found')

    # Split into lines for diff
    lines1 = v1.snapshot_xml.splitlines(keepends=True)
    lines2 = v2.snapshot_xml.splitlines(keepends=True)

    # Generate unified diff
    diff = difflib.unified_diff(
        lines1, lines2,
        fromfile=f'Version {v1.version_number}',
        tofile=f'Version {v2.version_number}',
        lineterm=''
    )

    return ''.join(diff)


def get_version_count(module_id):
    """Get the total number of versions for a module."""
    return ModuleVersion.query.filter_by(module_id=module_id).count()
