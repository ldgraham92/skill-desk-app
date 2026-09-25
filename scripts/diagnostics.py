"""Allowlisted local support metadata. Never include free-form user content."""
import platform
import time
from experience import VERSION
from agents import LABELS, HISTORY_AGENTS
from providers import executable


def diagnostic_report(catalog,manager,projects,provider):
    with catalog.lock,manager.lock:
        snapshot=catalog.snapshot()
        project_rows=projects.listing()
        return dict(version=VERSION,platform=platform.system(),python=platform.python_version(),generatedAt=int(time.time()),
            libraries=dict(total=len(catalog.roots),available=sum(root.is_dir() for root in catalog.roots),
                skills=len(snapshot['skills']),scanErrors=len(snapshot['errors'])),
            projects=dict(total=len(project_rows),available=sum(p['available'] for p in project_rows)),
            jobs=dict(running=bool(manager.busy),previews=len(manager.drafts),
                failed=sum(job['status']=='failed' for job in manager.jobs.values()),
                cancelled=sum(job['status']=='cancelled' for job in manager.jobs.values())),
            agents=[dict(id=name,installed=bool(executable(name)),historyReview=name in HISTORY_AGENTS,
                selected=provider.name==name,customModel=bool(provider.models.get(name))) for name in LABELS])
