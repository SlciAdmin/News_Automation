from app import app, database, scheduler

if __name__ == "__main__":
    database.init_db()
    sched = scheduler.start_scheduler()
    app.run(host='0.0.0.0', port=5000)