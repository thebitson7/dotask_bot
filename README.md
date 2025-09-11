# 🚀 DoTask Bot

A modern, fast, and **legendary** task management bot built with [Aiogram 3](https://docs.aiogram.dev) and [PostgreSQL/SQLite + SQLAlchemy](https://www.sqlalchemy.org).  
Easily create, manage, and complete your tasks directly in **Telegram** with a beautiful, card-based UX.  

---

## ✨ Features

- **User management**
  - Automatic user registration on first `/start`.
  - Tracks name, username, language, and updates automatically.

- **Task lifecycle**
  - ➕ Create new tasks with content, due date, and priority.
  - 📋 List tasks with filters (open/done, priority, due date).
  - ✅ Mark tasks as done / ↩️ Undo.
  - ✏️ Edit task content inline.
  - 🔁 Snooze tasks (15m, 1h, 1d, 3d, 1w).
  - 🗑 Delete tasks with **two-step confirmation**.

- **Smart UX**
  - Task list displayed as **separate interactive cards**.
  - Each card shows:
    - Status (⏳ pending / ✅ done),
    - Priority (🔴 High / 🟡 Medium / 🟢 Low),
    - Due date (Today, This Week, Overdue, etc.).
  - Inline keyboards for per-task actions.
  - Sticky header with filters + pagination.

- **Main menu (reply keyboard)**
  - ➕ Add Task  
  - 📋 My Tasks  
  - ⚙️ Settings  
  - ℹ️ Help  

- **Database layer**
  - Models with constraints, indexes, and hybrid properties.
  - Async CRUD operations with **transactional sessions**.
  - Portable: works with SQLite (dev) or PostgreSQL/MySQL (prod).

- **Infrastructure**
  - Logging with Rich (colorful output).
  - Optional Sentry integration for error tracking.
  - Flexible FSM storage (in-memory or Redis).
  - Supports both **Polling** and **Webhook** modes.

---

## 🖼 Screenshots

<p align="center">
  <img src="docs/screenshot_list.png" width="320" alt="Task list with cards" />
  <img src="docs/screenshot_add.png" width="320" alt="Adding a new task" />
</p>

---

## ⚙️ Tech Stack

- **Python 3.11+**
- [Aiogram 3](https://aiogram.dev) – modern Telegram framework
- [SQLAlchemy](https://www.sqlalchemy.org) (async) – ORM & DB layer
- [PostgreSQL](https://www.postgresql.org) / SQLite – database
- [Redis](https://redis.io) (optional) – FSM storage
- [Sentry](https://sentry.io) (optional) – error tracking
- [Rich](https://github.com/Textualize/rich) – logging & tracebacks

---

## 🚀 Getting Started

### 1. Clone the repo
```bash
git clone https://github.com/your-username/dotask-bot.git
cd dotask-bot
