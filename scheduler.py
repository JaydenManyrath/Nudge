from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()


def daily_sweep():
    # find overdue + due-soon tasks, dedupe against notifications table
    pass


def init_scheduler():
    pass
