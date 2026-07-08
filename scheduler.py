from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()


def daily_sweep():
    # Sprint 2 stub: find overdue + due-soon tasks, dedupe against the
    # notifications table, and enqueue reminder email/socket notifications.
    return None


def init_scheduler():
    # Sprint 2 stub: scheduler startup is intentionally disabled until
    # notification persistence and reminder policies are defined.
    return None
