import os
from flask import Flask, render_template, request, redirect, url_for
from sqlalchemy import *
from sqlalchemy.pool import NullPool


app = Flask(__name__, template_folder="templates")

#connect to database
DATABASEURI = "postgresql://lw2999:341647@104.196.222.236/proj1part2"
engine = create_engine(DATABASEURI)



# Static placeholder data
projects = [
    {"id": 1, "name": "Building A", "status": "In Progress", "progress": 60},
    {"id": 2, "name": "Building B", "status": "Completed", "progress": 100},
]

employees = [
    {"id": 1, "name": "John Doe", "role": "Engineer", "tasks": ["Task A"]},
    {"id": 2, "name": "Jane Smith", "role": "Architect", "tasks": []},
]

tasks = [
    {"id": 1, "name": "Task A", "description": "Foundation Work", "status": "In Progress"},
    {"id": 2, "name": "Task B", "description": "Roof Installation", "status": "Not Started"},
]

invoices = [
    {"id": 1, "client": "Client A", "amount": 5000, "status": "Paid"},
    {"id": 2, "client": "Client B", "amount": 2000, "status": "Pending"},
]

schedule = [
    {"task": "Foundation Work", "employee": "John Doe", "start_date": "2024-11-01", "end_date": "2024-11-10"},
    {"task": "Roof Installation", "employee": "Jane Smith", "start_date": "2024-11-15", "end_date": "2024-11-20"},
]


@app.route("/")
def dashboard():
    return render_template("dashboard.html", projects=projects)


@app.route("/employee_tasks", methods=["GET", "POST"])
def employee_tasks():
    """
    Assign tasks to employees and display task assignments.
    """
    with engine.connect() as conn:
        if request.method == "POST":
            task_id = int(request.form.get("task_id"))
            employee_id = int(request.form.get("employee_id"))

            # Assign the task to the employee in the database
            conn.execute(
                text("INSERT INTO employee_assigned_tasks (employee_id, task_id) VALUES (:employee_id, :task_id)"),
                {"employee_id": employee_id, "task_id": task_id}
            )
            conn.execute(
                text("UPDATE task SET task_status = 'Assigned' WHERE task_id = :task_id"),
                {"task_id": task_id}
            )
            return redirect(url_for("employee_tasks"))

        # Fetch employees and tasks dynamically
        employees = conn.execute(
            text("SELECT employee_id, employee_first_name, employee_last_name, employee_role FROM employee")
        ).fetchall()
        employees = [{"id": row.employee_id, "name": f"{row.employee_first_name} {row.employee_last_name}", "role": row.employee_role} for row in employees]

        tasks = conn.execute(
            text("SELECT task_id, task_name, task_description, task_status FROM task")
        ).fetchall()
        tasks = [{"id": row.task_id, "name": row.task_name, "description": row.task_description, "status": row.task_status} for row in tasks]

    return render_template("employee_tasks.html", employees=employees, tasks=tasks)

@app.route("/client_view", methods=["GET", "POST"])
def client_view():
    """
    Search for a client and display their details.
    """
    client_data = None  # Default is no client data

    with engine.connect() as conn:
        if request.method == "POST":
            # Get the search query from the form
            search_query = request.form.get("search_query")

            # Search for client by first or last name
            result = conn.execute(
                text("""
                    SELECT client_id, client_first_name, client_last_name, client_address, client_phone, client_email
                    FROM client
                    WHERE client_first_name ILIKE :query OR client_last_name ILIKE :query
                """),
                {"query": f"%{search_query}%"}
            ).fetchall()

            # Convert to list of dictionaries
            client_data = [
                {
                    "client_id": row.client_id,
                    "first_name": row.client_first_name,
                    "last_name": row.client_last_name,
                    "address": row.client_address,
                    "phone": row.client_phone,
                    "email": row.client_email,
                }
                for row in result
            ]

    return render_template("client_view.html", client_data=client_data)



@app.route("/invoice_generator", methods=["GET", "POST"])
def invoice_generator():
    if request.method == "POST":
        client = request.form.get("client")
        amount = request.form.get("amount")
        invoices.append({"id": len(invoices) + 1, "client": client, "amount": amount, "status": "Pending"})
        return redirect(url_for("invoice_generator"))

    return render_template("invoice_generator.html", invoices=invoices)


@app.route("/project_schedule")
def project_schedule():
    return render_template("project_schedule.html", schedule=schedule)


if __name__ == "__main__":
    app.run(debug=True)
